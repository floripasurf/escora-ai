"""Stage 5: Calculation Pipeline Bridge.

Bridges classified elements (beams, pillars) from the interpretation pipeline
to the shoring engine. Builds a structural model, derives slabs, and runs
load + shore calculations.
"""

import logging
from typing import List, Dict, Any, Optional
from shapely.geometry import LineString, Point

from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.calculation_models import (
    BeamShoringResult, SlabShoringResult, CalculationResult,
)
from src.models.slab import Slab
from src.engine.slab_builder import (
    derive_slabs_from_beams, derive_slabs_from_axes, detect_cantilever_slabs,
    derive_slabs_from_boundaries, merge_slab_sources,
)
from src.engine.load_calculator import calculate_total_load
from src.engine.beam_calculator import (
    calculate_beam_total_linear_load,
    distribute_beam_shores,
    estimate_beam_shore_height,
)
from src.engine.grid_distributor import distribute_shores, PillarExclusion
from src.engine.shore_selector import load_catalog, select_shore
from src.engine.tower_selector import (
    load_tower_catalog, decide_support_type, select_tower,
    select_distribution_beam, SupportType,
)
from src.engine.validator import validate_result
from src.engine.nervura_detector import detect_nervura_regions, distribute_nervura_shores
from src.ml.predictor import ShoringPredictor
from src.utils.constants import (
    GAMMA_F, Q_SOBRECARGA_DEFAULT, ESPESSURA_DEFAULT, ALTURA_DEFAULT,
    ESPACAMENTO_MAX_DEFAULT, ESPACAMENTO_MAX_VIGA, ESPACAMENTO_POR_ALTURA,
    CONTRA_FLECHA,
)

logger = logging.getLogger(__name__)

# Beam-pillar association proximity threshold (m)
# Must be generous: pillar labels are offset from beam axis, SOLID fills sit
# at pillar face (not centerline), and pillar sections can be 0.20-0.60m wide.
# A pillar center within 1.0m of the beam axis is structurally supporting it.
BEAM_PILLAR_PROXIMITY = 1.00

# Beam endpoint proximity for cantilever detection (m)
# Pillar within this distance of beam endpoint = beam is supported there.
# In DXF, beams end at pillar face, pillar center can be 0.30-0.50m beyond.
# Text labels add another ~0.30m offset. Total realistic gap: ~1.0m.
BEAM_ENDPOINT_PROXIMITY = 1.00

# Minimum confidence to include in calculations
MIN_CONFIDENCE = 0.50

# Minimum confidence for pillars — filters only rects where nearby beam text
# actively contradicts pillar classification (score drops via CONTRADICT_PENALTY)
MIN_PILLAR_CONFIDENCE = 0.50

# Low confidence threshold for warnings
LOW_CONFIDENCE = 0.70

# Default beam section height estimation: width * ratio, capped
BEAM_HEIGHT_RATIO = 2.5
BEAM_HEIGHT_MIN = 0.30
BEAM_HEIGHT_MAX = 0.60

# Beam exclusion zone width for slab shore distribution (m)
# Must be wider than beam width + margin so slab shores don't cluster at beam edges
BEAM_EXCLUSION_WIDTH = 0.60

# Minimum distance between a slab shore and any beam shore (m)
# Slab shores closer than this to an existing beam shore are redundant
MIN_SLAB_BEAM_SHORE_DIST = 0.50

# Cantilever slab spacing reduction factor
CANTILEVER_SPACING_FACTOR = 0.7


def _max_spacing_for_slab(thickness_m: float) -> float:
    """Get maximum shore spacing based on slab thickness (practical recommendation).

    Manual Lajes Martins table:
    - 10-16cm: 1.30m
    - 17-24cm: 1.20m
    - 25-30cm: 1.10m
    - >30cm:   1.00m
    """
    thickness_cm = round(thickness_m * 100)
    for (min_cm, max_cm), spacing in ESPACAMENTO_POR_ALTURA.items():
        if min_cm <= thickness_cm <= max_cm:
            return spacing
    return ESPACAMENTO_MAX_DEFAULT


def _contra_flecha_warnings(beam_length_m: float, beam_name: str) -> list:
    """Generate contra-flecha recommendation for spans > 2m."""
    warnings = []
    for (vao_min, vao_max), flecha_m in CONTRA_FLECHA.items():
        if vao_min <= beam_length_m < vao_max:
            flecha_cm = flecha_m * 100
            warnings.append(
                f"Viga {beam_name} (vão {beam_length_m:.1f}m) — "
                f"contra-flecha recomendada: {flecha_cm:.1f} cm na escora central"
            )
            break
    if beam_length_m >= 6.0:
        warnings.append(
            f"Viga {beam_name} (vão {beam_length_m:.1f}m) — "
            f"contra-flecha recomendada: ≥2.0 cm (vão grande, consultar projetista)"
        )
    return warnings


def associate_beams_pillars(
    beams: List[ClassifiedElement],
    pillars: List[ClassifiedElement],
) -> List[Dict[str, Any]]:
    """Associate beams with supporting pillars by proximity.

    For each beam, finds which pillars are within BEAM_PILLAR_PROXIMITY of
    the beam's axis line. Classifies each endpoint as supported or cantilever.

    Returns list of dicts with keys:
        - beam: ClassifiedElement
        - support_positions: List[float] — distances along beam axis
        - is_cantilever_start: bool
        - is_cantilever_end: bool
    """
    results = []

    for beam in beams:
        if beam.element_type != ElementType.BEAM or len(beam.geometry) < 2:
            continue

        start_pt = beam.geometry[0]
        end_pt = beam.geometry[1]
        beam_line = LineString([start_pt, end_pt])
        beam_length = beam_line.length

        if beam_length == 0:
            continue

        support_positions = []
        has_start_support = False
        has_end_support = False

        for pillar in pillars:
            if pillar.element_type != ElementType.PILLAR or not pillar.geometry:
                continue

            pillar_center = Point(pillar.geometry[0])
            dist_to_axis = beam_line.distance(pillar_center)

            if dist_to_axis <= BEAM_PILLAR_PROXIMITY:
                # Project pillar onto beam axis to get position along beam
                proj = beam_line.project(pillar_center)
                support_positions.append(round(proj, 4))

                # Check if near endpoints
                dist_to_start = pillar_center.distance(Point(start_pt))
                dist_to_end = pillar_center.distance(Point(end_pt))

                if dist_to_start <= BEAM_ENDPOINT_PROXIMITY:
                    has_start_support = True
                if dist_to_end <= BEAM_ENDPOINT_PROXIMITY:
                    has_end_support = True

        support_positions.sort()

        results.append({
            "beam": beam,
            "support_positions": support_positions,
            "is_cantilever_start": not has_start_support,
            "is_cantilever_end": not has_end_support,
        })

    return results


def _build_pillar_exclusions(
    pillars: List[ClassifiedElement],
) -> List[PillarExclusion]:
    """Build PillarExclusion zones from pillar elements."""
    exclusions = []
    for p in pillars:
        if p.element_type != ElementType.PILLAR or not p.geometry:
            continue
        cx, cy = p.geometry[0]
        w = p.section_width_m or 0.20
        d = p.section_height_m or 0.20
        exclusions.append(PillarExclusion(cx=cx, cy=cy, width_m=w, depth_m=d))
    return exclusions


def _build_beam_exclusions(
    beams: List[ClassifiedElement],
) -> List[PillarExclusion]:
    """Build rectangular exclusion zones along beam axes.

    Models each beam as a rectangular PillarExclusion to prevent slab shores
    from being placed on top of beams.
    """
    exclusions = []
    for beam in beams:
        if beam.element_type != ElementType.BEAM or len(beam.geometry) < 2:
            continue
        start = beam.geometry[0]
        end = beam.geometry[1]
        cx = (start[0] + end[0]) / 2
        cy = (start[1] + end[1]) / 2
        dx = abs(end[0] - start[0])
        dy = abs(end[1] - start[1])
        width = max(dx, BEAM_EXCLUSION_WIDTH)
        depth = max(dy, BEAM_EXCLUSION_WIDTH)
        exclusions.append(PillarExclusion(
            cx=cx, cy=cy, width_m=width, depth_m=depth, margin=0.0,
        ))
    return exclusions


def run_calculation(
    elements: List[ClassifiedElement],
    pe_direito_m: float = ALTURA_DEFAULT,
    pe_direito_is_default: bool = False,
    slab_thickness_m: Optional[float] = None,
    learned_section_height_m: Optional[float] = None,
    slab_type: str = "solid",
    nervura_rects: Optional[List[Dict[str, Any]]] = None,
    beam_layer_segments: Optional[List[Dict[str, Any]]] = None,
    slab_hatches: Optional[List[Dict[str, Any]]] = None,
    slab_polylines: Optional[List[Dict[str, Any]]] = None,
) -> CalculationResult:
    """Run the full calculation pipeline.

    Args:
        elements: Classified beams and pillars with geometry populated.
        pe_direito_m: Floor-to-ceiling height in meters.
        pe_direito_is_default: True if pe_direito was not found in DXF.
        slab_thickness_m: Slab thickness override. None = use default.
        slab_type: Detected slab type (solid, ribbed, waffle, etc.)

    Returns:
        CalculationResult with beam/slab shoring results.
    """
    warnings: List[str] = []
    validation_errors: List[str] = []

    if pe_direito_is_default:
        warnings.append(
            f"Pé-direito usando valor padrão {pe_direito_m:.2f}m — "
            "confirme no preview antes de aprovar"
        )

    # Separate beams and pillars
    beams = [e for e in elements if e.element_type == ElementType.BEAM]
    all_pillars = [e for e in elements if e.element_type == ElementType.PILLAR]

    # Filter pillars by confidence (removes false positives from rects near beam text)
    pillars = []
    for p in all_pillars:
        if p.score_final < MIN_PILLAR_CONFIDENCE:
            continue
        pillars.append(p)

    # Filter beams by confidence
    valid_beams = []
    for b in beams:
        if b.score_final < MIN_CONFIDENCE:
            warnings.append(
                f"Viga {b.name or 'sem nome'} ignorada — confiança {b.score_final:.0%} < 50%"
            )
            continue
        if b.score_final < LOW_CONFIDENCE:
            warnings.append(
                f"Viga {b.name or 'sem nome'} com baixa confiança ({b.score_final:.0%}) — revisar"
            )
        valid_beams.append(b)

    # Load shore catalog
    try:
        catalog = load_catalog()
    except FileNotFoundError:
        warnings.append("Catálogo de escoras não encontrado — usando valores padrão")
        catalog = []

    # Load tower and distribution beam catalog
    try:
        tower_catalog, dist_beam_catalog = load_tower_catalog()
    except FileNotFoundError:
        warnings.append("Catálogo de torres não encontrado")
        tower_catalog, dist_beam_catalog = [], []

    # Load ML predictor (advisory — augments rule-based decisions)
    try:
        ml_predictor = ShoringPredictor.load()
        if ml_predictor.is_loaded:
            logger.info("ML predictor loaded — predictions will augment rule-based decisions")
    except Exception:
        ml_predictor = ShoringPredictor()  # Unloaded, returns None for all predictions

    # Slab thickness
    thickness = slab_thickness_m or ESPESSURA_DEFAULT
    thickness_is_default = slab_thickness_m is None
    if thickness_is_default:
        warnings.append(
            f"Espessura da laje usando valor padrão {thickness:.2f}m — "
            "confirme no preview"
        )

    # === BEAM SHORING ===
    beam_associations = associate_beams_pillars(valid_beams, pillars)
    beam_results: List[BeamShoringResult] = []

    for assoc in beam_associations:
        beam = assoc["beam"]

        beam_width = beam.section_width_m or 0.14
        if beam.section_height_m:
            beam_height = beam.section_height_m
        elif learned_section_height_m:
            # Use learned default from historical runs
            beam_height = learned_section_height_m
            warnings.append(
                f"Viga {beam.name or 'sem nome'} — altura {learned_section_height_m:.2f}m "
                f"(padrão aprendido de execuções anteriores)"
            )
        else:
            # Estimate section height from width using typical beam proportions
            estimated = min(max(beam_width * BEAM_HEIGHT_RATIO, BEAM_HEIGHT_MIN), BEAM_HEIGHT_MAX)
            beam_height = estimated
            warnings.append(
                f"Viga {beam.name or 'sem nome'} — altura estimada {estimated:.2f}m "
                f"(seção não encontrada no DXF)"
            )
        beam_length = beam.length_m or 1.0

        total_linear_load = calculate_beam_total_linear_load(
            width_m=beam_width,
            height_m=beam_height,
            slab_thickness_m=thickness,
        )

        shore_height = estimate_beam_shore_height(pe_direito_m, beam_height)
        if shore_height <= 0:
            warnings.append(
                f"Viga {beam.name or 'sem nome'} — altura da escora negativa "
                f"(pé-direito {pe_direito_m}m < altura viga {beam_height}m)"
            )
            continue

        load_per_shore_estimate = total_linear_load * 1.0

        # Decide: telescopic shore or tower?
        support_type, decision_reasons = decide_support_type(
            required_height_m=shore_height,
            load_per_point_kn=load_per_shore_estimate,
            slab_thickness_m=thickness,
            span_m=beam_length,
            slab_type=slab_type,
        )

        # --- ML advisory prediction ---
        if ml_predictor.is_loaded:
            try:
                import math as _math
                # Compute beam angle
                if len(beam.geometry) >= 2:
                    _dx = beam.geometry[1][0] - beam.geometry[0][0]
                    _dy = beam.geometry[1][1] - beam.geometry[0][1]
                    beam_angle = abs(_math.degrees(_math.atan2(_dy, _dx)))
                else:
                    beam_angle = 0.0

                # Nearest pillar distance
                beam_cx = beam.geometry[0][0] if beam.geometry else 0.0
                beam_cy = beam.geometry[0][1] if beam.geometry else 0.0
                nearest_pillar = 99.0
                pillar_count_3m = 0
                for p in pillars:
                    if not p.geometry:
                        continue
                    px, py = p.geometry[0]
                    d = _math.hypot(beam_cx - px, beam_cy - py)
                    if d < nearest_pillar:
                        nearest_pillar = d
                    if d <= 3.0:
                        pillar_count_3m += 1

                # Nearby beam context
                nearby_beams = []
                for other_assoc in beam_associations:
                    ob = other_assoc["beam"]
                    if ob is beam:
                        continue
                    if ob.geometry:
                        ox, oy = ob.geometry[0]
                        if _math.hypot(beam_cx - ox, beam_cy - oy) <= 3.0:
                            nearby_beams.append(ob.length_m or 1.0)

                is_perimeter = nearest_pillar > 2.0 and pillar_count_3m <= 1

                ml_pred = ml_predictor.predict(
                    beam_length_m=beam_length,
                    beam_angle_deg=beam_angle,
                    nearest_pillar_dist_m=nearest_pillar,
                    pillar_count_3m=pillar_count_3m,
                    nearby_beam_count=len(nearby_beams),
                    nearby_beam_avg_length_m=(
                        sum(nearby_beams) / len(nearby_beams) if nearby_beams else 0.0
                    ),
                    is_perimeter=is_perimeter,
                )

                if ml_pred and ml_pred.is_confident:
                    beam_name = beam.name or "sem nome"
                    # Compare ML vs rule-based
                    rule_type = "tower" if support_type == SupportType.TOWER else "telescopic"
                    if ml_pred.support_type != rule_type and ml_pred.support_type != "none":
                        warnings.append(
                            f"ML: Viga {beam_name} — modelo sugere "
                            f"'{ml_pred.support_type}' "
                            f"(confiança {ml_pred.support_confidence:.0%}) "
                            f"vs regra '{rule_type}'"
                        )
                    # Spacing suggestion
                    if ml_pred.recommended_spacing_m:
                        warnings.append(
                            f"ML: Viga {beam_name} — espaçamento sugerido "
                            f"{ml_pred.recommended_spacing_m:.2f}m"
                        )
                    # Equipment suggestion
                    if ml_pred.recommended_equipment:
                        warnings.append(
                            f"ML: Viga {beam_name} — equipamento sugerido "
                            f"'{ml_pred.recommended_equipment}' "
                            f"(confiança {ml_pred.equipment_confidence:.0%})"
                        )
            except Exception as e:
                logger.debug(f"ML prediction failed for beam: {e}")

        selected_tower = None
        selected_dist_beam = None

        if support_type == SupportType.TOWER and tower_catalog:
            selected_tower = select_tower(tower_catalog, shore_height, load_per_shore_estimate)
            if selected_tower:
                warnings.append(
                    f"Viga {beam.name or 'sem nome'} — torre {selected_tower.model} "
                    f"({selected_tower.manufacturer}): {'; '.join(decision_reasons)}"
                )
                # Select distribution beam if available
                if dist_beam_catalog:
                    selected_dist_beam = select_distribution_beam(
                        dist_beam_catalog, span_m=1.0, load_kn_m=total_linear_load,
                    )

        selected_shore = select_shore(catalog, shore_height, load_per_shore_estimate) if catalog else None

        if not selected_shore:
            if selected_tower:
                # Create a synthetic ShoreCatalogEntry from tower for compatibility
                from src.models.shore import ShoreCatalogEntry
                selected_shore = ShoreCatalogEntry(
                    id=selected_tower.id,
                    manufacturer=selected_tower.manufacturer,
                    model=f"Torre {selected_tower.model}",
                    type="tower",
                    height_min_m=0.0,
                    height_max_m=selected_tower.max_height_m,
                    load_capacity_kn=selected_tower.load_capacity_kn,
                    weight_kg=selected_tower.total_weight_kg(shore_height),
                    tube_external_mm=0,
                    tube_internal_mm=0,
                    base_plate_mm=selected_tower.base_dimension_m * 1000,
                    price_reference_brl=selected_tower.total_price_brl(shore_height),
                )
            else:
                warnings.append(
                    f"Viga {beam.name or 'sem nome'} — nenhuma escora/torre compatível "
                    f"(altura {shore_height:.2f}m, carga {load_per_shore_estimate:.1f} kN)"
                )
                continue

        start_pt = beam.geometry[0] if len(beam.geometry) >= 2 else (0, 0)
        end_pt = beam.geometry[1] if len(beam.geometry) >= 2 else (beam_length, 0)

        dx = abs(end_pt[0] - start_pt[0])
        dy = abs(end_pt[1] - start_pt[1])
        direction = "x" if dx >= dy else "y"

        shores, n_shores, spacing = distribute_beam_shores(
            beam_length_m=beam_length,
            beam_width_m=beam_width,
            beam_height_m=beam_height,
            shore=selected_shore,
            total_linear_load_kn_m=total_linear_load,
            max_spacing=ESPACAMENTO_MAX_VIGA,
            start_x=start_pt[0],
            start_y=start_pt[1],
            direction=direction,
            support_positions=assoc["support_positions"],
            is_cantilever_start=assoc["is_cantilever_start"],
            is_cantilever_end=assoc["is_cantilever_end"],
        )

        is_valid, errors = validate_result(shores, spacing, spacing)
        validation_errors.extend(errors)

        beam_results.append(BeamShoringResult(
            beam=beam,
            support_positions=assoc["support_positions"],
            is_cantilever_start=assoc["is_cantilever_start"],
            is_cantilever_end=assoc["is_cantilever_end"],
            total_linear_load_kn_m=total_linear_load,
            shores=shores,
            shore_count=n_shores,
            spacing_m=spacing,
            selected_shore=selected_shore,
            shore_height_m=shore_height,
        ))

        # Contra-flecha recommendation for spans > 2m
        beam_name = beam.name or "sem nome"
        warnings.extend(_contra_flecha_warnings(beam_length, beam_name))

    # === PILLAR PROXIMITY FILTER FOR BEAM SHORES ===
    # Removed — shore_reviewer.py now handles this with the same threshold
    # (DISTANCIA_PILAR_MIN = 0.70m). Having two filters with different thresholds
    # caused shores placed at 0.70-1.00m to be incorrectly removed.

    # === NERVURA DETECTION (disabled — requires more learning from executed files) ===
    # TODO: re-enable once we have reference projects with correct nervura shoring
    nervura_regions = []

    # === SLAB SHORING ===
    # Strategy: 3-tier slab detection with merge
    # Tier 1: Beam grid polygonize (most precise, aligned to beams)
    # Tier 2: Beam axes with extended tolerance (fallback for sparse grids)
    # Tier 3: Direct boundary extraction from DXF hatches/polylines

    # Tier 1: Beam grid
    slab_polygons = derive_slabs_from_beams(valid_beams)

    # Tier 2: Extended beam axes (when beam grid produces too few slabs)
    MIN_SLAB_PANELS = 3
    beams_vs_slabs_mismatch = (
        len(valid_beams) >= 5 and len(slab_polygons) < len(valid_beams) * 0.3
    )
    if (len(slab_polygons) < MIN_SLAB_PANELS or beams_vs_slabs_mismatch) and beam_layer_segments:
        from src.parser.segment_classifier import find_beam_candidates
        all_candidates = find_beam_candidates(beam_layer_segments)
        if all_candidates:
            h_axes = [
                (bc.axis_coord, bc.start, bc.end)
                for bc in all_candidates if bc.direction == "x"
            ]
            v_axes = [
                (bc.axis_coord, bc.start, bc.end)
                for bc in all_candidates if bc.direction == "y"
            ]
            axes_slabs = derive_slabs_from_axes(h_axes, v_axes)
            if axes_slabs:
                slab_polygons = merge_slab_sources(slab_polygons, axes_slabs)
                total_area = sum(p.area for p in axes_slabs)
                warnings.append(
                    f"Lajes derivadas de {len(all_candidates)} eixos de viga "
                    f"(tolerância estendida) — {len(axes_slabs)} painéis, "
                    f"área total {total_area:.0f}m²"
                )

    # Tier 3: Direct boundary extraction from DXF hatches/polylines
    # Catches slabs that beam grid misses entirely (e.g., when beams
    # don't form closed polygons, or slab boundaries are explicit in DXF)
    if slab_hatches or slab_polylines:
        boundary_slabs = derive_slabs_from_boundaries(
            hatches=slab_hatches or [],
            polylines=slab_polylines or [],
            scale=1.0,  # Already in real coordinates
        )
        if boundary_slabs:
            before = len(slab_polygons)
            slab_polygons = merge_slab_sources(slab_polygons, boundary_slabs)
            added = len(slab_polygons) - before
            if added > 0:
                total_area = sum(p.area for p in boundary_slabs)
                warnings.append(
                    f"Lajes detectadas em hatches/polylines do DXF — "
                    f"{added} painel(éis) adicionais, "
                    f"área total {total_area:.0f}m²"
                )

    cantilever_flags = detect_cantilever_slabs(slab_polygons, pillars)

    pillar_exclusions = _build_pillar_exclusions(pillars)
    beam_exclusions = _build_beam_exclusions(valid_beams)
    all_exclusions = pillar_exclusions + beam_exclusions

    slab_results: List[SlabShoringResult] = []

    # Check which slab panels overlap nervura regions
    def _panel_is_nervura(polygon) -> bool:
        """Check if a slab panel overlaps a detected nervura region."""
        for region in nervura_regions:
            if polygon.intersects(region.polygon):
                overlap = polygon.intersection(region.polygon).area
                if overlap / polygon.area > 0.5:  # >50% overlap = nervura panel
                    return True
        return False

    # Find rib lines that pass through a specific slab panel
    def _ribs_in_panel(polygon):
        """Get H/V rib lines that intersect this slab panel."""
        bounds = polygon.bounds  # (minx, miny, maxx, maxy)
        h_ribs = []
        v_ribs = []
        for region in nervura_regions:
            if not polygon.intersects(region.polygon):
                continue
            for y in region.h_rib_lines:
                if bounds[1] - 0.5 <= y <= bounds[3] + 0.5:
                    h_ribs.append(y)
            for x in region.v_rib_lines:
                if bounds[0] - 0.5 <= x <= bounds[2] + 0.5:
                    v_ribs.append(x)
        return sorted(set(h_ribs)), sorted(set(v_ribs))

    nervura_panel_count = 0
    solid_panel_count = 0

    for i, polygon in enumerate(slab_polygons):
        is_cantilever = cantilever_flags[i] if i < len(cantilever_flags) else False

        slab = Slab.from_polygon(
            polygon=polygon,
            layer_name="derived",
            thickness_m=thickness,
        )

        total_load = calculate_total_load(slab)

        slab_shore_height = pe_direito_m - thickness
        if slab_shore_height <= 0:
            warnings.append(
                f"Laje (área {slab.area_m2:.1f}m²) — altura da escora negativa"
            )
            continue

        estimated_shores = max(1, int(slab.area_m2 / (ESPACAMENTO_MAX_DEFAULT ** 2)))
        load_per_shore_estimate = total_load / estimated_shores

        # Decide: telescopic shore or tower?
        slab_support_type, slab_decision_reasons = decide_support_type(
            required_height_m=slab_shore_height,
            load_per_point_kn=load_per_shore_estimate,
            slab_thickness_m=thickness,
            slab_type=slab_type,
        )

        slab_tower = None
        if slab_support_type == SupportType.TOWER and tower_catalog:
            slab_tower = select_tower(tower_catalog, slab_shore_height, load_per_shore_estimate)
            if slab_tower:
                warnings.append(
                    f"Laje (área {slab.area_m2:.1f}m²) — torre {slab_tower.model}: "
                    f"{'; '.join(slab_decision_reasons)}"
                )

        selected_shore = select_shore(catalog, slab_shore_height, load_per_shore_estimate) if catalog else None

        if not selected_shore:
            if slab_tower:
                from src.models.shore import ShoreCatalogEntry
                selected_shore = ShoreCatalogEntry(
                    id=slab_tower.id,
                    manufacturer=slab_tower.manufacturer,
                    model=f"Torre {slab_tower.model}",
                    type="tower",
                    height_min_m=0.0,
                    height_max_m=slab_tower.max_height_m,
                    load_capacity_kn=slab_tower.load_capacity_kn,
                    weight_kg=slab_tower.total_weight_kg(slab_shore_height),
                    tube_external_mm=0,
                    tube_internal_mm=0,
                    base_plate_mm=slab_tower.base_dimension_m * 1000,
                    price_reference_brl=slab_tower.total_price_brl(slab_shore_height),
                )
            else:
                warnings.append(
                    f"Laje (área {slab.area_m2:.1f}m²) — nenhuma escora/torre compatível "
                    f"(altura {slab_shore_height:.2f}m, carga {load_per_shore_estimate:.1f} kN)"
                )
            slab_results.append(SlabShoringResult(
                polygon=polygon,
                thickness_m=thickness,
                thickness_is_default=thickness_is_default,
                area_m2=slab.area_m2,
                is_cantilever=is_cantilever,
                total_load_kn=total_load,
                shores=[],
                exclusions=all_exclusions,
            ))
            continue

        max_spacing = _max_spacing_for_slab(thickness)
        if is_cantilever:
            max_spacing *= CANTILEVER_SPACING_FACTOR

        # Check if this panel is a nervura slab — use rib-based shore placement
        is_nervura_panel = nervura_regions and _panel_is_nervura(polygon)

        if is_nervura_panel:
            # Place shores at rib intersections and along ribs WITHIN this panel
            from src.engine.nervura_detector import NervuraRegion, distribute_nervura_shores
            from src.models.shore import PositionedShore
            h_ribs, v_ribs = _ribs_in_panel(polygon)

            # Check if ribs provide adequate coverage — if average rib spacing
            # exceeds 2x max_spacing in either direction, fall back to uniform grid
            panel_w = polygon.bounds[2] - polygon.bounds[0]
            panel_h = polygon.bounds[3] - polygon.bounds[1]
            avg_sx = panel_w / max(len(v_ribs), 1) if v_ribs else panel_w
            avg_sy = panel_h / max(len(h_ribs), 1) if h_ribs else panel_h

            if h_ribs and v_ribs and avg_sx <= max_spacing * 2 and avg_sy <= max_spacing * 2:
                panel_region = NervuraRegion(
                    x_min=polygon.bounds[0],
                    x_max=polygon.bounds[2],
                    y_min=polygon.bounds[1],
                    y_max=polygon.bounds[3],
                    h_rib_lines=h_ribs,
                    v_rib_lines=v_ribs,
                    area_m2=slab.area_m2,
                )
                pillar_pos = [(p.geometry[0][0], p.geometry[0][1])
                              for p in pillars if p.geometry]
                rib_shores = distribute_nervura_shores(
                    region=panel_region,
                    max_spacing=max_spacing,
                    pillar_positions=pillar_pos,
                )

                if rib_shores:
                    load_per = total_load / len(rib_shores)
                    util = load_per / selected_shore.load_capacity_kn

                    positioned = []
                    for rs in rib_shores:
                        # Only keep shores inside the polygon
                        from shapely.geometry import Point as ShapelyPoint
                        if not polygon.contains(ShapelyPoint(rs.x, rs.y)):
                            continue
                        positioned.append(PositionedShore(
                            x=round(rs.x, 3),
                            y=round(rs.y, 3),
                            shore=selected_shore,
                            load_applied_kn=round(load_per, 2),
                            utilization_ratio=round(min(util, 1.0), 4),
                        ))

                    if positioned:
                        # Recalculate load per shore after filtering
                        load_per = total_load / len(positioned)
                        util = load_per / selected_shore.load_capacity_kn
                        for s in positioned:
                            s.load_applied_kn = round(load_per, 2)
                            s.utilization_ratio = round(min(util, 1.0), 4)

                        slab_results.append(SlabShoringResult(
                            polygon=polygon,
                            thickness_m=thickness,
                            thickness_is_default=thickness_is_default,
                            area_m2=slab.area_m2,
                            is_cantilever=is_cantilever,
                            total_load_kn=total_load,
                            shores=positioned,
                            grid_nx=len(v_ribs),
                            grid_ny=len(h_ribs),
                            spacing_x_m=round((polygon.bounds[2] - polygon.bounds[0]) / max(len(v_ribs), 1), 2),
                            spacing_y_m=round((polygon.bounds[3] - polygon.bounds[1]) / max(len(h_ribs), 1), 2),
                            selected_shore=selected_shore,
                            exclusions=all_exclusions,
                        ))
                        nervura_panel_count += 1
                        continue

            # Fallback: no ribs found in this nervura panel — use uniform grid
            is_nervura_panel = False

        # Solid slab — uniform grid shore placement
        shores, nx, ny, sx, sy = distribute_shores(
            slab=slab,
            shore=selected_shore,
            total_load_kn=total_load,
            max_spacing=max_spacing,
            exclusions=all_exclusions,
        )

        is_valid, errors = validate_result(shores, sx, sy)
        validation_errors.extend(errors)

        slab_results.append(SlabShoringResult(
            polygon=polygon,
            thickness_m=thickness,
            thickness_is_default=thickness_is_default,
            area_m2=slab.area_m2,
            is_cantilever=is_cantilever,
            total_load_kn=total_load,
            shores=shores,
            grid_nx=nx,
            grid_ny=ny,
            spacing_x_m=sx,
            spacing_y_m=sy,
            selected_shore=selected_shore,
            exclusions=all_exclusions,
        ))
        solid_panel_count += 1

    if nervura_panel_count > 0:
        warnings.append(
            f"Laje nervurada: {nervura_panel_count} painel(éis) com escoras nas nervuras"
        )
    if solid_panel_count > 0:
        warnings.append(
            f"Laje maciça: {solid_panel_count} painel(éis) com escoras em grid uniforme"
        )

    # === SLAB-BEAM SHORE PROXIMITY FILTER ===
    # Remove slab shores that are too close to any beam shore.
    # The beam already has its own shore at that position — a slab shore
    # within MIN_SLAB_BEAM_SHORE_DIST is redundant and clutters the drawing.
    import math

    beam_shore_positions = []
    for br in beam_results:
        for s in br.shores:
            beam_shore_positions.append((s.x, s.y))

    for sr in slab_results:
        if not beam_shore_positions:
            break
        filtered = []
        for ss in sr.shores:
            too_close = False
            for bx, by in beam_shore_positions:
                if math.hypot(ss.x - bx, ss.y - by) < MIN_SLAB_BEAM_SHORE_DIST:
                    too_close = True
                    break
            if not too_close:
                filtered.append(ss)
        if len(filtered) < len(sr.shores):
            removed = len(sr.shores) - len(filtered)
            sr.shores = filtered
            # Recalculate load per shore
            if sr.shores and sr.total_load_kn > 0:
                load_per = sr.total_load_kn / len(sr.shores)
                util = load_per / (sr.selected_shore.load_capacity_kn if sr.selected_shore else 1)
                for s in sr.shores:
                    s.load_applied_kn = round(load_per, 2)
                    s.utilization_ratio = round(util, 4)

    # === CROSS-BEAM DEDUPLICATION ===
    # At beam intersections, shores from different beams cluster together.
    # Remove redundant shores that are too close to each other.
    # Uses a global set of all shore positions; for each close pair,
    # removes the one with lower load (keeps the structurally important one).
    MIN_CROSS_BEAM_DIST = 0.35  # m — minimum distance between shores of different beams

    # Build global index: (beam_idx, shore_idx) -> (x, y, load)
    all_shore_refs = []
    for bi, br in enumerate(beam_results):
        for si, s in enumerate(br.shores):
            all_shore_refs.append((bi, si, s.x, s.y, s.load_applied_kn))

    # Find all close pairs and mark the weaker shore for removal
    to_remove = set()  # (beam_idx, shore_idx)
    for i, (bi, si, x1, y1, l1) in enumerate(all_shore_refs):
        if (bi, si) in to_remove:
            continue
        for j, (bj, sj, x2, y2, l2) in enumerate(all_shore_refs):
            if j <= i or bi == bj:  # skip same beam (already handled internally)
                continue
            if (bj, sj) in to_remove:
                continue
            dist = math.hypot(x2 - x1, y2 - y1)
            if dist < MIN_CROSS_BEAM_DIST:
                # Remove the shore with lower load
                if l1 >= l2:
                    to_remove.add((bj, sj))
                else:
                    to_remove.add((bi, si))

    # Apply removals
    if to_remove:
        for bi, br in enumerate(beam_results):
            indices_to_remove = {si for (b, si) in to_remove if b == bi}
            if indices_to_remove:
                br.shores = [s for idx, s in enumerate(br.shores) if idx not in indices_to_remove]
                br.shore_count = len(br.shores)

    # === POST-PROCESSING REVIEW ===
    # Final quality check: catches overlapping shores, shores on pillars,
    # shores on beam axes, and shores outside polygon boundaries.
    from src.engine.shore_reviewer import review_and_fix

    calc_result = CalculationResult(
        beam_results=beam_results,
        slab_results=slab_results,
        shore_catalog_used=[],
        total_shores=0,
        total_load_kn=0.0,
        pe_direito_m=pe_direito_m,
        pe_direito_is_default=pe_direito_is_default,
        warnings=warnings,
        validation_errors=validation_errors,
        is_valid=True,
    )

    review_corrections = review_and_fix(calc_result, pillars, valid_beams)
    warnings.extend(review_corrections)

    # === AGGREGATE RESULTS ===
    all_shores_count = (
        sum(r.shore_count for r in beam_results)
        + sum(len(r.shores) for r in slab_results)
    )
    all_load = (
        sum(r.total_linear_load_kn_m * (r.beam.length_m or 0) for r in beam_results)
        + sum(r.total_load_kn for r in slab_results)
    )

    shore_models_used = {}
    for r in beam_results:
        shore_models_used[r.selected_shore.id] = r.selected_shore
    for r in slab_results:
        if r.selected_shore:
            shore_models_used[r.selected_shore.id] = r.selected_shore

    calc_result.shore_catalog_used = list(shore_models_used.values())
    calc_result.total_shores = all_shores_count
    calc_result.total_load_kn = round(all_load, 2)
    calc_result.is_valid = len(validation_errors) == 0

    return calc_result
