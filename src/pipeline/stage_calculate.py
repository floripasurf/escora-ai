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
from src.engine.slab_builder import derive_slabs_from_beams, detect_cantilever_slabs
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
BEAM_PILLAR_PROXIMITY = 0.30

# Beam endpoint proximity for cantilever detection (m)
BEAM_ENDPOINT_PROXIMITY = 0.30

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
    # The beam distributor only knows about support positions along the axis.
    # A shore may still be placed on a beam axis that passes near a pillar
    # in the perpendicular direction. Remove those here.
    import math
    from src.utils.constants import DISTANCIA_PILAR_MIN

    for br in beam_results:
        filtered_shores = []
        for s in br.shores:
            too_close = False
            for p in pillars:
                if not p.geometry:
                    continue
                px, py = p.geometry[0]
                pw = (p.section_width_m or 0.20) / 2
                pd = (p.section_height_m or 0.20) / 2
                # Distance from shore to pillar face (not center)
                dx = max(0, abs(s.x - px) - pw)
                dy = max(0, abs(s.y - py) - pd)
                dist = math.hypot(dx, dy)
                if dist < DISTANCIA_PILAR_MIN:
                    too_close = True
                    break
            if not too_close:
                filtered_shores.append(s)
        if len(filtered_shores) < len(br.shores):
            br.shores = filtered_shores
            br.shore_count = len(filtered_shores)

    # === SLAB SHORING ===
    slab_polygons = derive_slabs_from_beams(valid_beams)
    cantilever_flags = detect_cantilever_slabs(slab_polygons, pillars)

    pillar_exclusions = _build_pillar_exclusions(pillars)
    beam_exclusions = _build_beam_exclusions(valid_beams)
    all_exclusions = pillar_exclusions + beam_exclusions

    slab_results: List[SlabShoringResult] = []

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

    # === NERVURA (WAFFLE/RIBBED) SLAB SHORING ===
    # For nervura slabs, shores go on the rib lines (borders between caixões),
    # not on a uniform grid over the slab surface.
    # Try nervura detection regardless of slab_type classification —
    # the classifier may misidentify nervura as solid. If nervura regions
    # are found from the rect geometry, use them.
    if nervura_rects:
        nervura_regions = detect_nervura_regions(nervura_rects, valid_beams)
        if nervura_regions:
            warnings.append(
                f"Laje nervurada detectada — {len(nervura_regions)} região(ões), "
                f"escoras posicionadas nas nervuras"
            )
        for region in nervura_regions:
            # Shore selection for nervura region
            nervura_shore_height = pe_direito_m - thickness
            if nervura_shore_height <= 0:
                continue

            estimated_shores = max(1, int(region.area_m2 / (ESPACAMENTO_MAX_DEFAULT ** 2)))
            nerv_load_total = (
                region.area_m2
                * (Q_SOBRECARGA_DEFAULT + thickness * 25.0)  # kN/m²
                * GAMMA_F
            )
            nerv_load_per_shore = nerv_load_total / estimated_shores

            nerv_support_type, nerv_reasons = decide_support_type(
                required_height_m=nervura_shore_height,
                load_per_point_kn=nerv_load_per_shore,
                slab_thickness_m=thickness,
                slab_type=slab_type,
            )

            nerv_tower = None
            if nerv_support_type == SupportType.TOWER and tower_catalog:
                nerv_tower = select_tower(tower_catalog, nervura_shore_height, nerv_load_per_shore)

            nerv_shore = select_shore(catalog, nervura_shore_height, nerv_load_per_shore) if catalog else None
            if not nerv_shore and nerv_tower:
                from src.models.shore import ShoreCatalogEntry
                nerv_shore = ShoreCatalogEntry(
                    id=nerv_tower.id,
                    manufacturer=nerv_tower.manufacturer,
                    model=f"Torre {nerv_tower.model}",
                    type="tower",
                    height_min_m=0.0,
                    height_max_m=nerv_tower.max_height_m,
                    load_capacity_kn=nerv_tower.load_capacity_kn,
                    weight_kg=nerv_tower.total_weight_kg(nervura_shore_height),
                    tube_external_mm=0,
                    tube_internal_mm=0,
                    base_plate_mm=nerv_tower.base_dimension_m * 1000,
                    price_reference_brl=nerv_tower.total_price_brl(nervura_shore_height),
                )
            if not nerv_shore:
                warnings.append(
                    f"Laje nervurada (área {region.area_m2:.1f}m²) — "
                    f"nenhuma escora compatível"
                )
                continue

            # Place shores on rib lines
            pillar_pos = [(p.geometry[0][0], p.geometry[0][1])
                          for p in pillars if p.geometry]
            rib_shores = distribute_nervura_shores(
                region=region,
                max_spacing=_max_spacing_for_slab(thickness),
                pillar_positions=pillar_pos,
            )

            if not rib_shores:
                continue

            # Convert to PositionedShore objects
            from src.models.shore import PositionedShore
            load_per = nerv_load_total / len(rib_shores)
            util = load_per / nerv_shore.load_capacity_kn

            positioned = []
            for rs in rib_shores:
                positioned.append(PositionedShore(
                    x=round(rs.x, 3),
                    y=round(rs.y, 3),
                    shore=nerv_shore,
                    load_applied_kn=round(load_per, 2),
                    utilization_ratio=round(min(util, 1.0), 4),
                ))

            slab_results.append(SlabShoringResult(
                polygon=region.polygon,
                thickness_m=thickness,
                thickness_is_default=thickness_is_default,
                area_m2=region.area_m2,
                is_cantilever=False,
                total_load_kn=round(nerv_load_total, 2),
                shores=positioned,
                grid_nx=len(region.v_rib_lines),
                grid_ny=len(region.h_rib_lines),
                spacing_x_m=round((region.x_max - region.x_min) / max(len(region.v_rib_lines), 1), 2),
                spacing_y_m=round((region.y_max - region.y_min) / max(len(region.h_rib_lines), 1), 2),
                selected_shore=nerv_shore,
                exclusions=all_exclusions,
            ))

            warnings.append(
                f"Laje nervurada: {len(positioned)} escoras em "
                f"{len(region.h_rib_lines)} nervuras H + {len(region.v_rib_lines)} nervuras V"
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

    return CalculationResult(
        beam_results=beam_results,
        slab_results=slab_results,
        shore_catalog_used=list(shore_models_used.values()),
        total_shores=all_shores_count,
        total_load_kn=round(all_load, 2),
        pe_direito_m=pe_direito_m,
        pe_direito_is_default=pe_direito_is_default,
        warnings=warnings,
        validation_errors=validation_errors,
        is_valid=len(validation_errors) == 0,
    )
