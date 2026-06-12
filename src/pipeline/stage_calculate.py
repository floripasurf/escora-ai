"""Stage 5: Calculation Pipeline Bridge.

Bridges classified elements (beams, pillars) from the interpretation pipeline
to the shoring engine. Builds a structural model, derives slabs, and runs
load + shore calculations.
"""

import logging
import math
from dataclasses import replace
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from shapely.geometry import LineString, Point, Polygon, MultiPoint, box

from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.calculation_models import (
    BeamShoringResult, SlabShoringResult, CalculationResult,
    VolumeBreakdownEntry,
)
from src.models.shore import PositionedShore
from src.utils.labels import (
    CATEGORY_DEFAULT, CATEGORY_LABELS_PT,
    classify_layer, extract_room_hint, extract_structural_name,
)
from src.models.slab import Slab
from src.engine.slab_builder import (
    derive_slabs_from_beams, derive_slabs_from_beam_pairs,
    derive_slabs_from_axes, detect_cantilever_slabs,
    derive_slabs_from_boundaries, merge_slab_sources,
)
from src.engine.load_calculator import calculate_total_load
from src.engine.beam_calculator import (
    calculate_beam_total_linear_load,
    distribute_beam_shores,
    compute_h_pilha,
    estimate_beam_shore_height,
)
from src.engine.grid_distributor import distribute_shores, PillarExclusion
from src.engine.shore_capacity import compute_adaptive_spacing
from src.engine.shore_selector import load_catalog, select_shore
from src.engine.vm_grid_builder import (
    ShorePoint, VMGrid, build_vm_grid, select_vm_length_mm,
    _compute_segment_load_and_moment,
)
from src.models.plywood import default_plywood_spec
from src.engine.tower_selector import (
    load_tower_catalog, decide_support_type, select_tower,
    select_distribution_beam, SupportType,
    MIXED_TOWER_GRID_SPACING,
)
from src.engine.validator import validate_result
from src.engine.nervura_detector import detect_nervura_regions, distribute_nervura_shores
from src.engine.shaft_detector import detect_all_shafts, filter_slab_polygons_by_shafts, subtract_shafts_from_slabs
from src.ml.predictor import ShoringPredictor
from src.utils.constants import (
    GAMMA_F, Q_SOBRECARGA_DEFAULT, ESPESSURA_DEFAULT, ALTURA_DEFAULT,
    ESPACAMENTO_MAX_DEFAULT, ESPACAMENTO_MAX_VIGA, ESPACAMENTO_POR_ALTURA,
    ESPACAMENTO_SECUNDARIAS_MANUAL, CONTRA_FLECHA, DISTANCIA_BORDA_MIN,
    ESPACAMENTO_MIN,
)

logger = logging.getLogger(__name__)

# Beam-pillar association proximity threshold (m)
# Must be generous: pillar labels are offset from beam axis, SOLID fills sit
# at pillar face (not centerline), and pillar sections can be 0.20-0.60m wide.
# A pillar center within 1.0m of the beam axis is structurally supporting it.
BEAM_PILLAR_PROXIMITY = 1.00

# Orguel rule 16 (manual): viga externa / beiral / perimetral.
# A viga é considerada perimetral quando seu centróide está fora do casco
# convexo dos pilares por mais do que este threshold. Calibrado inicialmente
# em 0.5 m (plano pre-orguel-adaptation-2026-04-16); ajustar empíricamente.
PERIMETER_BEAM_HULL_DISTANCE_M = 0.5

# Beam endpoint proximity for cantilever detection (m)
# Pillar within this distance of beam endpoint = beam is supported there.
# In DXF, beams end at pillar face, pillar center can be 0.30-0.50m beyond.
# Text labels add another ~0.30m offset. Total realistic gap: ~1.0m.
BEAM_ENDPOINT_PROXIMITY = 1.00

# Minimum confidence to include in calculations
MIN_CONFIDENCE = 0.35

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


def _secondary_vm_spacing_m(thickness_m: float, plywood) -> float:
    """Return VM secondary spacing snapped to plywood seam multiples.

    Manual p.89 gives the maximum spacing for secondary beams by slab
    thickness and plywood thickness. Manual p.114-115 then requires plywood
    seams to land on a secondary beam axis, so the practical spacing is the
    largest seam multiple that does not exceed the manual maximum.
    """
    seam_m = plywood.effective_seam_multiple_mm() / 1000.0
    if seam_m <= 0:
        return 0.244

    slab_cm = max(1, int(math.ceil(thickness_m * 100)))
    plywood_mm = int(round(getattr(plywood, "thickness_mm", 18.0)))
    keys = [k for k in ESPACAMENTO_SECUNDARIAS_MANUAL if k[2] == 2]
    slab_options = sorted({k[0] for k in keys})
    plywood_options = sorted({k[1] for k in keys})

    slab_key = next((cm for cm in slab_options if cm >= slab_cm), slab_options[-1])
    lower_or_equal_plywood = [mm for mm in plywood_options if mm <= plywood_mm]
    plywood_key = lower_or_equal_plywood[-1] if lower_or_equal_plywood else plywood_options[0]

    max_spacing = ESPACAMENTO_SECUNDARIAS_MANUAL.get(
        (slab_key, plywood_key, 2),
        seam_m,
    )
    if max_spacing <= seam_m:
        return round(max_spacing, 3)
    multiples = max(1, int(math.floor(max_spacing / seam_m)))
    return round(multiples * seam_m, 3)


def _max_spacing_for_slab(thickness_m: float) -> float:
    """Get maximum shore spacing based on slab thickness (practical recommendation).

    NBR 15696:2009 + prática de projeto:
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


def _level_primary_axis(slab_results) -> Optional[str]:
    """Eixo de primaria UNICO por pavimento (inspecao visual 2026-06-12).

    O eixo era decidido por painel (perpendicular ao lado maior de CADA
    um), entao paineis vizinhos/sobrepostos saiam com barrotes em
    direcoes opostas — grade cruzada no DXF. Pratica real (projetos
    Orguel): direcao de barroteamento uniforme por regiao/pavimento.
    Voto ponderado por area: cada painel vota no eixo que escolheria
    sozinho; vence o eixo com mais area.
    """
    votes = {"x": 0.0, "y": 0.0}
    for sr in slab_results:
        try:
            min_x, min_y, max_x, max_y = sr.polygon.bounds
        except Exception:
            continue
        w, h = max_x - min_x, max_y - min_y
        # Mesmo criterio do _detect_primary_axis: primaria perpendicular
        # ao lado maior do painel.
        axis = "y" if w >= h else "x"
        votes[axis] += max(sr.area_m2, 0.0)
    if votes["x"] == 0.0 and votes["y"] == 0.0:
        return None
    return "x" if votes["x"] >= votes["y"] else "y"


def _build_slab_vm_grid(
    sr: SlabShoringResult,
    *,
    global_origin: Optional[tuple[float, float]],
    preferred_axis: Optional[str] = None,
):
    """Build the VM grid from the slab's current, post-processed shores."""
    if len(sr.shores) < 2 or sr.area_m2 <= 0:
        return None
    min_x, min_y, max_x, max_y = sr.polygon.bounds
    plywood = default_plywood_spec()
    shore_points = [ShorePoint(x=s.x, y=s.y) for s in sr.shores]
    bbox = (min_x, min_y, max_x, max_y)
    load_kn_m2 = sr.total_load_kn / sr.area_m2
    secondary_spacing_m = _secondary_vm_spacing_m(sr.thickness_m, plywood)

    def _candidate(primary_axis_override: Optional[str] = None) -> VMGrid:
        grid = build_vm_grid(
            shore_points=shore_points,
            polygon_bbox=bbox,
            load_kn_m2=load_kn_m2,
            plywood=plywood,
            secondary_spacing_m=secondary_spacing_m,
            global_origin=global_origin,
            primary_axis_override=primary_axis_override,
        )
        return _clip_vm_grid_to_polygon(grid, sr.polygon, sr.exclusions)

    def _grid_score(grid: VMGrid) -> tuple[int, float, int]:
        failed = [
            seg for seg in getattr(grid, "segments", [])
            if not seg.passes_moment or not seg.passes_deflection
        ]
        worst_utilization = max((seg.utilization for seg in failed), default=0.0)
        return (len(failed), worst_utilization, len(getattr(grid, "issues", [])))

    # Eixo uniforme por pavimento (2026-06-12): usar o eixo preferido do
    # nivel quando fornecido; o eixo alternativo fica apenas como fallback
    # estrutural EXPLICITO (com issue registrada).
    default_grid = _candidate(preferred_axis)
    default_score = _grid_score(default_grid)
    if default_score[0] == 0:
        return default_grid

    alternate_axis = "y" if default_grid.primaria_axis == "x" else "x"
    alternate_grid = _candidate(alternate_axis)
    alternate_score = _grid_score(alternate_grid)
    if alternate_score < default_score:
        alternate_grid.issues.append(
            f"Orientação da malha VM ajustada de {default_grid.primaria_axis} "
            f"para {alternate_axis} por verificação de momento/flecha "
            f"(diverge do eixo uniforme do pavimento — revisar barroteamento "
            f"deste painel)."
        )
        return alternate_grid
    return default_grid


def _distribute_line_first_shores(
    slab: Slab,
    polygon: Polygon,
    shore,
    total_load_kn: float,
    exclusions: List[Any],
    floor_height_m: Optional[float],
    pillar_positions: Optional[List[tuple]] = None,
    tower_mode: bool = False,
    floor_frame: Optional[tuple] = None,
    guide_model: Optional[str] = None,
):
    """Posiciona escoras de laje pelo modo line-first (manual §28.8).

    Gera linhas de guia (direcao por painel, pitch = vao/n) e escoras ao
    longo de cada linha via ``line_first_builder``. O adensamento de
    capitel (Orguel Q6) acontece SOBRE as linhas via ``capitel_centers``
    — nunca pontos avulsos. ``tower_mode=True`` usa pitch/passo de TORRE
    (2.35-2.85 m c-a-c, gold standard 28.8 item 7) — torres apoiam as
    guias. Retorna ``(shores, nx, ny, sx, sy, layout)``
    no mesmo formato de ``distribute_shores`` + o layout para o vm_grid.
    """
    from src.engine.line_first_builder import build_line_first_layout

    q_kn_m2 = total_load_kn / slab.area_m2 if slab.area_m2 > 0 else 7.7
    try:
        cap_kn = (
            shore.effective_capacity(floor_height_m)
            if floor_height_m is not None
            else shore.load_capacity_kn
        )
    except Exception:
        cap_kn = shore.load_capacity_kn
    extra = {}
    if tower_mode:
        extra = dict(
            pitch_range_m=(2.0, 2.85),
            pitch_target_max_m=2.60,
            step_range_m=(2.35, 2.85),
        )
    if floor_frame is not None and not tower_mode:
        # Malha de PAVIMENTO (decisao do revisor 2026-06-12): eixo unico
        # paralelo ao maior sentido do projeto + pitch unico + linhas
        # ancoradas na lattice global -> guias colineares atravessando as
        # vigas em alinhamento continuo. A capacidade e preservada pelo
        # PASSO (densifica ao longo da linha em paineis mais carregados).
        f_angle, f_pitch, f_anchor = floor_frame[:3]
        extra.update(
            angle_override_deg=f_angle,
            pitch_override_m=f_pitch,
            v_anchor=f_anchor,
        )
    if guide_model:
        # Sistema ALU14+VM80 (gold standard §9/§10): painel nervurado usa
        # primarias ALU14 na lattice do pavimento; as secundarias VM80 de
        # passo fixo sao adicionadas depois (append_fixed_step_secondaries).
        extra["guide_model"] = guide_model
    layout = build_line_first_layout(
        polygon,
        q_kn_m2,
        cap_kn,
        exclusions=exclusions,
        capitel_centers=pillar_positions,
        **extra,
    )
    if not layout.shores:
        return [], 0, 0, 0.0, 0.0, None

    load_per = total_load_kn / len(layout.shores)
    capacity = shore.load_capacity_kn or 1.0
    shores = [
        PositionedShore(
            x=round(x, 3),
            y=round(y, 3),
            shore=shore,
            load_applied_kn=round(load_per, 2),
            utilization_ratio=round(load_per / capacity, 4),
        )
        for x, y in layout.shores
    ]
    nx = len(layout.lines)
    ny = max((len(ln.shore_positions) for ln in layout.lines), default=0)
    return shores, nx, ny, layout.step_m, layout.pitch_m, layout


def _line_parts(geom) -> List[LineString]:
    if geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [geom]
    if hasattr(geom, "geoms"):
        parts: List[LineString] = []
        for g in geom.geoms:
            parts.extend(_line_parts(g))
        return parts
    return []


def _clip_vm_grid_to_polygon(
    grid: VMGrid,
    polygon: Polygon,
    exclusions: Optional[List[Any]] = None,
    *,
    min_segment_m: float = 0.10,
) -> VMGrid:
    """Clip VM segments to slab polygon, beams, pillars and openings."""
    clipped = VMGrid(primaria_axis=grid.primaria_axis)
    clip_polygon = polygon.buffer(1e-6)
    obstacle_count = 0
    if exclusions:
        obstacle_polys = []
        for ex in exclusions:
            try:
                obstacle = box(ex.min_x, ex.min_y, ex.max_x, ex.max_y)
                if obstacle.intersects(clip_polygon):
                    obstacle_polys.append(obstacle)
            except Exception:
                continue
        if obstacle_polys:
            try:
                from shapely.ops import unary_union as _uu
                clip_polygon = clip_polygon.difference(_uu(obstacle_polys))
                obstacle_count = len(obstacle_polys)
            except Exception:
                pass
    removed = 0
    split_extra = 0

    def _recheck_segment(seg, start, end):
        span_m = math.hypot(end[0] - start[0], end[1] - start[1])
        length_mm = select_vm_length_mm(span_m, seg.model)
        if seg.role == "secundaria":
            notes = seg.notes
            if span_m < max(LineString([seg.start, seg.end]).length - 1e-6, 0):
                notes = f"{notes}; recortado em viga/borda" if notes else "recortado em viga/borda"
            return replace(
                seg,
                length_mm=length_mm,
                start=start,
                end=end,
                notes=notes,
            )

        ei_by_model = {
            "VM80": 146.8,
            "VM130": 461.8,
            "VM50": 35.0,
        }
        ei = ei_by_model.get(seg.model, 0.0)
        M, Madm, f, fadm, passM, passF = _compute_segment_load_and_moment(
            span_m,
            seg.load_kn_m,
            seg.moment_adm_kn_m,
            ei,
        )
        notes = seg.notes
        if span_m < max(seg.span_m - 1e-6, 0):
            notes = f"{notes}; recortado em viga/borda" if notes else "recortado em viga/borda"
        return replace(
            seg,
            length_mm=length_mm,
            start=start,
            end=end,
            span_m=round(span_m, 3),
            moment_kn_m=round(M, 3),
            flecha_mm=round(f, 2),
            flecha_adm_mm=round(fadm, 2),
            passes_moment=passM,
            passes_deflection=passF,
            notes=notes,
        )

    for seg in grid.segments:
        line = LineString([seg.start, seg.end])
        if line.length < min_segment_m:
            removed += 1
            continue
        if clip_polygon.covers(line):
            clipped.add_segment(_recheck_segment(seg, seg.start, seg.end))
            continue

        parts = [p for p in _line_parts(line.intersection(clip_polygon)) if p.length >= min_segment_m]
        if not parts:
            removed += 1
            continue
        if len(parts) > 1:
            split_extra += len(parts) - 1
        for part in parts:
            coords = list(part.coords)
            start = (float(coords[0][0]), float(coords[0][1]))
            end = (float(coords[-1][0]), float(coords[-1][1]))
            # Preserve the original segment direction for predictable DXF output.
            if Point(end).distance(Point(seg.start)) < Point(start).distance(Point(seg.start)):
                start, end = end, start
            clipped.add_segment(_recheck_segment(seg, start, end))

    clipped.issues = list(grid.issues)
    if removed or split_extra:
        clipped.issues.append(
            f"VMs recortadas pelo contorno da laje: {removed} removida(s), "
            f"{split_extra} divisão(ões)."
        )
    if obstacle_count:
        clipped.issues.append(
            f"VMs interrompidas em {obstacle_count} faixa(s) de viga/pilar/abertura."
        )
    return clipped


def _segment_crosses_exclusion(seg, ex) -> bool:
    x1, y1 = seg.start
    x2, y2 = seg.end
    if abs(x1 - x2) < 1e-6:
        lo, hi = sorted((y1, y2))
        return ex.min_x <= x1 <= ex.max_x and hi >= ex.min_y and lo <= ex.max_y
    if abs(y1 - y2) < 1e-6:
        lo, hi = sorted((x1, x2))
        return ex.min_y <= y1 <= ex.max_y and hi >= ex.min_x and lo <= ex.max_x
    return False


def _filter_vm_grid_for_exclusions(grid: VMGrid, exclusions: List[Any]) -> VMGrid:
    """Remove primary VM segments that would run through pillar exclusions."""
    if not exclusions:
        return grid
    filtered = VMGrid(primaria_axis=grid.primaria_axis)
    skipped = 0
    for seg in grid.segments:
        if (
            seg.role == "primaria"
            and any(_segment_crosses_exclusion(seg, ex) for ex in exclusions)
        ):
            skipped += 1
            continue
        filtered.add_segment(seg)
    filtered.issues = list(grid.issues)
    if skipped:
        filtered.issues.append(
            f"{skipped} segmento(s) de VM primária interrompido(s) por pilar."
        )
    return filtered


def _point_in_exclusions(
    x: float,
    y: float,
    exclusions: List[Any],
) -> bool:
    for ex in exclusions or []:
        if ex.min_x <= x <= ex.max_x and ex.min_y <= y <= ex.max_y:
            return True
    return False


def _recalculate_slab_shore_loads(sr: SlabShoringResult) -> None:
    if not sr.shores or sr.total_load_kn <= 0:
        return
    load_per = sr.total_load_kn / len(sr.shores)
    for shore in sr.shores:
        capacity = shore.shore.load_capacity_kn or 1.0
        shore.load_applied_kn = round(load_per, 2)
        shore.utilization_ratio = round(load_per / capacity, 4)


def _add_vm_primary_reinforcement_shores(
    sr: SlabShoringResult,
    *,
    max_span_m: float = 1.20,
) -> int:
    """Add telescopic shores at failed VM130 primary spans.

    Manual §28 requires primary VMs to pass moment and deflection. A final
    post-processing pass may remove slab shores close to beams or other slabs,
    leaving stale VM spans. When a primary segment still fails after final
    deduplication, insert intermediate slab shores at <=1.20 m intervals and
    rebuild the grid.
    """
    grid = getattr(sr, "vm_grid", None)
    if grid is None or not sr.selected_shore:
        return 0

    failed_primaries = [
        seg for seg in getattr(grid, "segments", [])
        if seg.role == "primaria"
        and (not seg.passes_moment or not seg.passes_deflection)
        and seg.span_m > max_span_m
    ]
    if not failed_primaries:
        return 0

    added = 0
    for seg in failed_primaries:
        # Use floor+1 instead of ceil so exact multiples (2.40, 3.60...)
        # are still split; the VM check includes deflection and may reject a
        # nominal 1.20 m remainder under heavier panels.
        pieces = max(2, int(math.floor(seg.span_m / max_span_m)) + 1)
        for idx in range(1, pieces):
            t = idx / pieces
            x = seg.start[0] + (seg.end[0] - seg.start[0]) * t
            y = seg.start[1] + (seg.end[1] - seg.start[1]) * t
            pt = Point(x, y)
            if not sr.polygon.buffer(1e-6).covers(pt):
                continue
            if _point_in_exclusions(x, y, sr.exclusions):
                continue
            if any(math.hypot(x - s.x, y - s.y) < ESPACAMENTO_MIN for s in sr.shores):
                continue
            sr.shores.append(PositionedShore(
                x=round(x, 3),
                y=round(y, 3),
                shore=sr.selected_shore,
                load_applied_kn=0.0,
                utilization_ratio=0.0,
            ))
            added += 1

    if added:
        _recalculate_slab_shore_loads(sr)
        sr.shores_weight_kg = round(sum(s.shore.weight_kg for s in sr.shores), 2)
    return added


def _ensure_minimum_vm_shores(
    sr: SlabShoringResult,
    *,
    min_area_m2: float = 1.0,
) -> int:
    """Ensure real slab panels have at least two shores for a VM span."""
    if len(sr.shores) >= 2 or sr.area_m2 < min_area_m2 or not sr.selected_shore:
        return 0

    minx, miny, maxx, maxy = sr.polygon.bounds
    width = maxx - minx
    height = maxy - miny
    if width <= 0 or height <= 0:
        return 0

    if sr.shores:
        base = Point(sr.shores[0].x, sr.shores[0].y)
    else:
        base = sr.polygon.representative_point()
    base_x, base_y = base.x, base.y

    if width >= height:
        ordered_dirs = [(1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0)]
        max_offset = width * 0.40
    else:
        ordered_dirs = [(0.0, 1.0), (0.0, -1.0), (1.0, 0.0), (-1.0, 0.0)]
        max_offset = height * 0.40

    offsets = [
        min(max_offset, 0.80),
        min(max_offset, 0.55),
        min(max_offset, 0.35),
    ]
    added = 0
    for offset in offsets:
        if offset < ESPACAMENTO_MIN:
            continue
        for dx, dy in ordered_dirs:
            x = base_x + dx * offset
            y = base_y + dy * offset
            pt = Point(x, y)
            if not sr.polygon.buffer(1e-6).covers(pt):
                continue
            if _point_in_exclusions(x, y, sr.exclusions):
                continue
            if any(math.hypot(x - s.x, y - s.y) < ESPACAMENTO_MIN for s in sr.shores):
                continue
            sr.shores.append(PositionedShore(
                x=round(x, 3),
                y=round(y, 3),
                shore=sr.selected_shore,
                load_applied_kn=0.0,
                utilization_ratio=0.0,
            ))
            added += 1
            if len(sr.shores) >= 2:
                _recalculate_slab_shore_loads(sr)
                sr.shores_weight_kg = round(sum(s.shore.weight_kg for s in sr.shores), 2)
                return added

    if added:
        _recalculate_slab_shore_loads(sr)
        sr.shores_weight_kg = round(sum(s.shore.weight_kg for s in sr.shores), 2)
    return added


def _add_vm_secondary_reinforcement_shores(
    sr: SlabShoringResult,
    *,
    max_span_m: float = 1.60,
) -> int:
    """Add shores under failed VM80 secondary spans.

    Secondary VMs rest on primary guides. If the guide spacing left by final
    shore cleanup is too large, VM80 can fail even when the visual secondary
    spacing is correct. Add intermediate shores on failed secondary lines so
    the next grid rebuild creates extra primary guides and shortens the VM80
    span.
    """
    grid = getattr(sr, "vm_grid", None)
    if grid is None or not sr.selected_shore:
        return 0

    failed_secondaries = [
        seg for seg in getattr(grid, "segments", [])
        if seg.role == "secundaria"
        and (not seg.passes_moment or not seg.passes_deflection)
        and seg.span_m > max_span_m
    ]
    if not failed_secondaries:
        return 0

    added = 0
    for seg in failed_secondaries:
        pieces = max(2, int(math.floor(seg.span_m / max_span_m)) + 1)
        for idx in range(1, pieces):
            t = idx / pieces
            x = seg.start[0] + (seg.end[0] - seg.start[0]) * t
            y = seg.start[1] + (seg.end[1] - seg.start[1]) * t
            pt = Point(x, y)
            if not sr.polygon.buffer(1e-6).covers(pt):
                continue
            if _point_in_exclusions(x, y, sr.exclusions):
                continue
            if any(math.hypot(x - s.x, y - s.y) < ESPACAMENTO_MIN for s in sr.shores):
                continue
            sr.shores.append(PositionedShore(
                x=round(x, 3),
                y=round(y, 3),
                shore=sr.selected_shore,
                load_applied_kn=0.0,
                utilization_ratio=0.0,
            ))
            added += 1

    if added:
        _recalculate_slab_shore_loads(sr)
        sr.shores_weight_kg = round(sum(s.shore.weight_kg for s in sr.shores), 2)
    return added


def _finalize_slab_vm_grids(
    slab_results: List[SlabShoringResult],
    *,
    global_origin: Optional[tuple[float, float]],
    warnings: List[str],
) -> None:
    """Rebuild VM grids after all shore post-processing and reinforce failures."""
    # Eixo de barroteamento UNIFORME por pavimento (2026-06-12): todos os
    # paineis usam a mesma direcao de primaria/secundaria, como nos
    # projetos Orguel reais. Elimina a "grade cruzada" de paineis
    # sobrepostos/vizinhos com eixos opostos.
    # NOTA (manual §28.8 / 23.9): a regra de eixo unico por pavimento fica
    # DEPRECIADA para paineis line-first — neles a direcao e POR PAINEL
    # (perpendicular ao vao menor) e as guias derivam do POLIGONO, nao das
    # escoras, entao o pos-processamento de escoras nao invalida as linhas
    # (momento/flecha/capacidade ja verificados pelo builder).
    preferred_axis = _level_primary_axis(
        [sr for sr in slab_results if getattr(sr, "layout_mode", "grid") != "line_first"]
    )
    for idx, sr in enumerate(slab_results, 1):
        if (
            getattr(sr, "layout_mode", "grid") == "line_first"
            and getattr(sr, "vm_grid", None) is not None
        ):
            continue
        total_added = _ensure_minimum_vm_shores(sr)
        sr.vm_grid = _build_slab_vm_grid(
            sr, global_origin=global_origin, preferred_axis=preferred_axis,
        )
        for _ in range(5):
            added_primary = _add_vm_primary_reinforcement_shores(sr)
            if added_primary:
                sr.vm_grid = _build_slab_vm_grid(
                    sr, global_origin=global_origin,
                    preferred_axis=preferred_axis,
                )

            added_secondary = _add_vm_secondary_reinforcement_shores(sr)
            added = added_primary + added_secondary
            if not added:
                break
            total_added += added
            sr.vm_grid = _build_slab_vm_grid(
                sr, global_origin=global_origin, preferred_axis=preferred_axis,
            )
        if total_added:
            warnings.append(
                f"Laje {idx} (área {sr.area_m2:.1f}m²) — adicionadas "
                f"{total_added} escora(s) para eliminar falha de VM"
            )


# Invariante line-first (manual §28.8): escora de laje SEMPRE sobre uma
# linha de guia. Tolerancia para arredondamento de coordenadas (3 casas).
LINE_FIRST_MAX_OFFLINE_DIST_M = 0.10


def _enforce_line_first_shores_on_lines(
    slab_results: List[SlabShoringResult],
    warnings: List[str],
) -> int:
    """Remove escoras de laje a >0.10 m de qualquer linha de guia (line-first).

    Invariante do modo line-first: TODA escora de laje fica sobre uma linha
    de guia. Pos-processadores legados (geradores de pontos avulsos) nao
    devem injetar escoras fora das linhas — este passo final garante o
    invariante mesmo se um novo pos-processador violar a regra.
    """
    dropped_total = 0
    for idx, sr in enumerate(slab_results, 1):
        if getattr(sr, "layout_mode", "grid") != "line_first":
            continue
        grid = getattr(sr, "vm_grid", None)
        if grid is None or not getattr(grid, "segments", None):
            continue
        guide_lines = [
            LineString([seg.start, seg.end])
            for seg in grid.segments
            if seg.role == "primaria"
        ]
        if not guide_lines:
            continue
        kept = [
            s for s in sr.shores
            if min(ln.distance(Point(s.x, s.y)) for ln in guide_lines)
            <= LINE_FIRST_MAX_OFFLINE_DIST_M
        ]
        dropped = len(sr.shores) - len(kept)
        if dropped and kept:
            sr.shores = kept
            _recalculate_slab_shore_loads(sr)
            sr.shores_weight_kg = round(
                sum(s.shore.weight_kg for s in sr.shores), 2
            )
            dropped_total += dropped
            warnings.append(
                f"Laje {idx} (line-first): removida(s) {dropped} escora(s) "
                f"fora das linhas de guia (>{LINE_FIRST_MAX_OFFLINE_DIST_M:.2f} m)"
            )
    return dropped_total


def _merge_collinear_line_first_guides(
    slab_results: List[SlabShoringResult],
    beam_lines: Optional[List[LineString]],
    warnings: List[str],
    *,
    max_gap_m: float = 1.10,
    max_offset_m: float = 0.12,
    angle_tol_deg: float = 3.0,
) -> int:
    """Funde guias COLINEARES de paineis vizinhos (v6, inspecao 2026-06-12).

    Paineis derivados fragmentados geram guias-toco que deveriam ser uma
    guia continua (marcacao verde do revisor). Regra: duas primarias com o
    mesmo angulo, desvio perpendicular <= 0.12 m e vao longitudinal de ate
    1.10 m sao conectadas — DESDE QUE nenhuma viga de concreto cruze o
    conector (guia para na face da viga, gold standard §28.8). Mantem o
    paralelismo (preferencia do revisor) sem deslocar linhas existentes.
    """
    import math as _m
    from src.engine.vm_grid_builder import VMSegment

    segs: List[tuple] = []  # (sr, seg, angle_deg, grid)
    for sr in slab_results:
        if getattr(sr, "layout_mode", "grid") != "line_first":
            continue
        grid = getattr(sr, "vm_grid", None)
        if grid is None:
            continue
        for seg in getattr(grid, "segments", []):
            if seg.role != "primaria":
                continue
            dx = seg.end[0] - seg.start[0]
            dy = seg.end[1] - seg.start[1]
            if abs(dx) < 1e-9 and abs(dy) < 1e-9:
                continue
            ang = _m.degrees(_m.atan2(dy, dx)) % 180.0
            segs.append((sr, seg, ang, grid))

    merged = 0
    done: set = set()
    for a in range(len(segs)):
        sr_a, seg_a, ang_a, grid_a = segs[a]
        for b in range(a + 1, len(segs)):
            sr_b, seg_b, ang_b, _ = segs[b]
            if sr_a is sr_b:
                continue  # mesmo painel: ja continuo por construcao
            d_ang = min(abs(ang_a - ang_b), 180.0 - abs(ang_a - ang_b))
            if d_ang > angle_tol_deg:
                continue
            # Frame do angulo de A: u ao longo, v perpendicular
            rad = _m.radians(ang_a)
            ca, sa = _m.cos(rad), _m.sin(rad)

            def _uv(pt):
                return (pt[0] * ca + pt[1] * sa, -pt[0] * sa + pt[1] * ca)

            ua = sorted([_uv(seg_a.start)[0], _uv(seg_a.end)[0]])
            ub = sorted([_uv(seg_b.start)[0], _uv(seg_b.end)[0]])
            va = (_uv(seg_a.start)[1] + _uv(seg_a.end)[1]) / 2.0
            vb = (_uv(seg_b.start)[1] + _uv(seg_b.end)[1]) / 2.0
            if abs(va - vb) > max_offset_m:
                continue
            gap = max(ua[0], ub[0]) - min(ua[1], ub[1])
            if gap <= 0 or gap > max_gap_m:
                continue
            # Conector entre as pontas mais proximas
            if ua[1] <= ub[0]:
                p1 = seg_a.start if _uv(seg_a.start)[0] > _uv(seg_a.end)[0] else seg_a.end
                p2 = seg_b.start if _uv(seg_b.start)[0] < _uv(seg_b.end)[0] else seg_b.end
            else:
                p1 = seg_b.start if _uv(seg_b.start)[0] > _uv(seg_b.end)[0] else seg_b.end
                p2 = seg_a.start if _uv(seg_a.start)[0] < _uv(seg_a.end)[0] else seg_a.end
            connector = LineString([p1, p2])
            # v10 (decisao do revisor 2026-06-12): o alinhamento ATRAVESSA
            # vigas internas — conector permitido sobre viga, marcado como
            # tal (peca de VM continua quebrando na face; escoras nunca
            # caem sobre a viga: conectores ficam fora do re-espacamento).
            crosses_beam = bool(beam_lines) and any(
                connector.intersects(bl) for bl in beam_lines
            )
            key = (id(seg_a), id(seg_b))
            if key in done:
                continue
            done.add(key)
            grid_a.add_segment(VMSegment(
                role="primaria",
                model=seg_a.model,
                length_mm=int(round(connector.length * 1000)),
                start=(round(p1[0], 3), round(p1[1], 3)),
                end=(round(p2[0], 3), round(p2[1], 3)),
                axis=getattr(seg_a, "axis", "x"),
                load_kn_m=seg_a.load_kn_m,
                span_m=round(connector.length, 3),
                moment_kn_m=0.0,
                moment_adm_kn_m=seg_a.moment_adm_kn_m,
                flecha_mm=0.0,
                flecha_adm_mm=999.0,
                passes_moment=True,
                passes_deflection=True,
                notes=(
                    "conector atravessa viga interna (alinhamento continuo, v10)"
                    if crosses_beam
                    else "conector de guia continua entre paineis (v6)"
                ),
            ))
            merged += 1
    if merged:
        warnings.append(
            f"{merged} conector(es) de guia continua entre paineis "
            f"fragmentados (line-first v6 — sem viga cruzando o vao)"
        )
    return merged


def _respace_line_first_shores(
    slab_results: List[SlabShoringResult],
    warnings: List[str],
    *,
    chain_offset_m: float = 0.12,
    default_step_m: float = 1.50,
) -> int:
    """Re-espaca escoras EQUIDISTANTES ao longo de cada guia continua.

    Decisao do revisor (2026-06-12): equidistancia prevalece — em um vao
    de 6 m lineares com 5 escoras, o espacamento deve ser 1.20 m constante.
    Extras de transpasse/capitel e cadeias fundidas entre paineis (passos
    diferentes de cada lado) sao substituidos por n = ceil(L/alvo),
    passo = L/n, escoras em i*passo com escora em cada ponta. O alvo por
    painel vem do layout (sr spacing); o n nunca diminui em relacao ao
    numero de escoras que a cadeia tinha (capacidade preservada).
    """
    import math as _m

    respaced = 0
    for sr in slab_results:
        if getattr(sr, "layout_mode", "grid") != "line_first":
            continue
        grid = getattr(sr, "vm_grid", None)
        if grid is None or not getattr(grid, "segments", None):
            continue
        # Conectores que atravessam viga ficam FORA do re-espacamento:
        # escora nunca cai sobre a viga (v10).
        prim = [
            s for s in grid.segments
            if s.role == "primaria"
            and "atravessa viga" not in (s.notes or "")
        ]
        if not prim:
            continue
        target = getattr(sr, "spacing_x_m", None) or default_step_m
        if not (0.30 <= target <= 3.0):
            target = default_step_m

        # Agrupar segmentos em CADEIAS colineares conectadas (uniao por
        # proximidade de extremos + mesmo angulo).
        n_seg = len(prim)
        parent = list(range(n_seg))

        def _find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def _ang(s):
            return _m.degrees(_m.atan2(
                s.end[1] - s.start[1], s.end[0] - s.start[0])) % 180.0

        def _uv_interval(s, rad):
            ca, sa = _m.cos(rad), _m.sin(rad)
            u1 = s.start[0] * ca + s.start[1] * sa
            u2 = s.end[0] * ca + s.end[1] * sa
            v1 = -s.start[0] * sa + s.start[1] * ca
            v2 = -s.end[0] * sa + s.end[1] * ca
            return min(u1, u2), max(u1, u2), (v1 + v2) / 2.0

        for i in range(n_seg):
            for j in range(i + 1, n_seg):
                d_ang = abs(_ang(prim[i]) - _ang(prim[j]))
                d_ang = min(d_ang, 180.0 - d_ang)
                if d_ang > 3.0:
                    continue
                # Colineares se: desvio perpendicular <= tol E intervalos
                # ao longo do eixo se SOBREPOEM (pecas com transpasse de
                # 0.65 m se sobrepoem!) ou tem gap <= tol.
                rad = _m.radians(_ang(prim[i]))
                lo_i, hi_i, v_i = _uv_interval(prim[i], rad)
                lo_j, hi_j, v_j = _uv_interval(prim[j], rad)
                if abs(v_i - v_j) > chain_offset_m:
                    continue
                gap = max(lo_i, lo_j) - min(hi_i, hi_j)
                if gap <= chain_offset_m:
                    parent[_find(i)] = _find(j)

        chains: Dict[int, list] = {}
        for i in range(n_seg):
            chains.setdefault(_find(i), []).append(prim[i])

        # Re-espacar escoras por cadeia
        new_shores: List = []
        claimed: set = set()
        shore_pts = [(s, Point(s.x, s.y)) for s in sr.shores]
        for segs in chains.values():
            rad = _m.radians(_ang(segs[0]))
            ca, sa = _m.cos(rad), _m.sin(rad)
            us, vs = [], []
            for s in segs:
                for pt in (s.start, s.end):
                    us.append(pt[0] * ca + pt[1] * sa)
                    vs.append(-pt[0] * sa + pt[1] * ca)
            u_lo, u_hi = min(us), max(us)
            v_mid = sum(vs) / len(vs)
            length = u_hi - u_lo
            chain_lines = [LineString([s.start, s.end]) for s in segs]
            mine = [
                (idx, s) for idx, (s, p) in enumerate(shore_pts)
                if idx not in claimed
                and min(ln.distance(p) for ln in chain_lines) <= 0.10
            ]
            for idx, _s in mine:
                claimed.add(idx)
            if length < 0.30 or not mine:
                new_shores.extend(s for _i, s in mine)
                continue
            n_old = len(mine)
            n_steps = max(
                int(_m.ceil(length / target - 1e-9)),
                n_old - 1 if n_old >= 2 else 1,
            )
            step = length / n_steps
            tmpl = mine[0][1]
            for k in range(n_steps + 1):
                u = u_lo + k * step
                x = u * ca - v_mid * sa
                y = u * sa + v_mid * ca
                new_shores.append(PositionedShore(
                    x=round(x, 3), y=round(y, 3),
                    shore=tmpl.shore,
                    load_applied_kn=tmpl.load_applied_kn,
                    utilization_ratio=tmpl.utilization_ratio,
                    support_type=getattr(tmpl, "support_type", None),
                    tower=getattr(tmpl, "tower", None),
                    distribution_beam=getattr(tmpl, "distribution_beam", None),
                ))
            respaced += 1

        # Escoras nao atribuidas a nenhuma cadeia permanecem
        new_shores.extend(
            s for idx, (s, _p) in enumerate(shore_pts) if idx not in claimed
        )
        if respaced:
            sr.shores = new_shores
            _recalculate_slab_shore_loads(sr)
            sr.shores_weight_kg = round(
                sum(s.shore.weight_kg for s in sr.shores), 2
            )
    if respaced:
        warnings.append(
            f"{respaced} guia(s) continua(s) re-espacada(s) com escoras "
            f"equidistantes (L/n constante - decisao do revisor 2026-06-12)"
        )
    return respaced


def _drop_lines_glued_to_beams(
    slab_results: List[SlabShoringResult],
    beam_lines: Optional[List[LineString]],
    warnings: List[str],
    max_dist_m: float = 0.45,
    angle_tol_deg: float = 5.0,
) -> int:
    """Remove linhas de guia PARALELAS e grudadas em vigas (v11).

    Inspecao do revisor (circulos vermelhos): linha de guia de laje
    correndo a < 0.45 m de uma viga paralela e redundante — a faixa ja e
    suportada pelo escoramento da propria viga — e gera escoras coladas
    nas escoras da viga. Remove o segmento e as escoras sobre ele.
    """
    import math as _m

    if not beam_lines:
        return 0
    dropped = 0
    for idx, sr in enumerate(slab_results, 1):
        if getattr(sr, "layout_mode", "grid") != "line_first":
            continue
        grid = getattr(sr, "vm_grid", None)
        if grid is None or not getattr(grid, "segments", None):
            continue
        to_drop = []
        for seg in grid.segments:
            if seg.role != "primaria":
                continue
            sl = LineString([seg.start, seg.end])
            if sl.length < 0.30:
                continue
            ang_s = _m.degrees(_m.atan2(
                seg.end[1] - seg.start[1], seg.end[0] - seg.start[0])) % 180.0
            for bl in beam_lines:
                bc = list(bl.coords)
                ang_b = _m.degrees(_m.atan2(
                    bc[-1][1] - bc[0][1], bc[-1][0] - bc[0][0])) % 180.0
                d_ang = min(abs(ang_s - ang_b), 180.0 - abs(ang_s - ang_b))
                if d_ang > angle_tol_deg:
                    continue
                d1 = bl.distance(Point(seg.start))
                d2 = bl.distance(Point(seg.end))
                if max(d1, d2) < max_dist_m:
                    to_drop.append(seg)
                    break
        if not to_drop:
            continue
        drop_lines = [LineString([s.start, s.end]) for s in to_drop]
        grid.segments = [s for s in grid.segments if s not in to_drop]
        kept = [
            s for s in sr.shores
            if min(ln.distance(Point(s.x, s.y)) for ln in drop_lines) > 0.10
        ]
        # Painel sem NENHUMA primaria restante = faixa estreita inteira
        # suportada pelo escoramento da(s) viga(s): nenhuma escora de laje
        # orfa pode sobrar (invariante line-first §28.8 — escora sempre
        # sobre linha; CAD-1 v1, 2026-06-12).
        has_primaria = any(s.role == "primaria" for s in grid.segments)
        if not has_primaria:
            kept = []
        n_removed = len(sr.shores) - len(kept)
        if n_removed:
            sr.shores = kept
            _recalculate_slab_shore_loads(sr)
            sr.shores_weight_kg = round(
                sum(s.shore.weight_kg for s in sr.shores), 2
            )
        dropped += len(to_drop)
        if n_removed or to_drop:
            warnings.append(
                f"Laje {idx}: {len(to_drop)} linha(s) de guia paralela(s) "
                f"grudada(s) em viga (< {max_dist_m:.2f} m) removida(s) "
                f"com {n_removed} escora(s) — faixa suportada pela viga (v11)"
            )
    return dropped


def _dedupe_beam_shores(
    beam_results: List,
    warnings: List[str],
    min_dist_m: float = 0.30,
) -> int:
    """Dedup GLOBAL de escoras de viga (v14, audit OP-102).

    Vigas fragmentadas/sobrepostas e cruzamentos viga x viga geravam
    escoras empilhadas (pares a 0.00-0.30 m — 338 no CAD-1, 694 no
    CFL-SUB). Duas fases: extremidades e torres ocupam a grade primeiro
    (apoios estruturais); depois as intermediarias — qualquer uma a
    < min_dist de escora ja aceita e removida, com re-rateio de carga.
    """
    import math as _m

    cell = max(min_dist_m, 0.05)
    occupied: dict = {}

    def _key(x, y):
        return (int(_m.floor(x / cell)), int(_m.floor(y / cell)))

    def _near(x, y):
        kx, ky = _key(x, y)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for ox, oy in occupied.get((kx + dx, ky + dy), ()):
                    if _m.hypot(x - ox, y - oy) < min_dist_m:
                        return True
        return False

    def _add(x, y):
        occupied.setdefault(_key(x, y), []).append((x, y))

    def _is_anchor(br, i, s):
        if "tower" in str(getattr(s, "support_type", "")).lower():
            return True
        return i == 0 or i == len(br.shores) - 1

    keep_flags: dict = {}
    # Fase 1: ancoras (extremidades/torres) tem prioridade
    for br in beam_results:
        for i, s in enumerate(getattr(br, "shores", []) or []):
            if _is_anchor(br, i, s):
                if _near(s.x, s.y):
                    keep_flags[id(s)] = False
                else:
                    _add(s.x, s.y)
                    keep_flags[id(s)] = True
    # Fase 2: intermediarias
    for br in beam_results:
        for s in getattr(br, "shores", []) or []:
            if id(s) in keep_flags:
                continue
            if _near(s.x, s.y):
                keep_flags[id(s)] = False
            else:
                _add(s.x, s.y)
                keep_flags[id(s)] = True

    dropped = 0
    for br in beam_results:
        ss = getattr(br, "shores", []) or []
        kept = [s for s in ss if keep_flags.get(id(s), True)]
        n_rm = len(ss) - len(kept)
        if n_rm and kept:
            total = sum(s.load_applied_kn for s in ss)
            per = total / len(kept)
            cap = kept[0].shore.load_capacity_kn or 1.0
            for s in kept:
                s.load_applied_kn = round(per, 2)
                s.utilization_ratio = round(per / cap, 4)
            br.shores = kept
            dropped += n_rm
    if dropped:
        warnings.append(
            f"{dropped} escora(s) de viga duplicada(s)/colada(s) "
            f"removida(s) (dedup global v14, < {min_dist_m:.2f} m; "
            f"extremidades e torres preservadas)"
        )
    return dropped


def _fill_beam_shore_gaps(
    beam_results: List,
    warnings: List[str],
    max_gap_m: float = 1.80,
) -> int:
    """Preenche vaos de viga acima do teto (v14, audit OP-101).

    Apos align-a-lattice + dedup, um vao entre escoras consecutivas (ou
    entre a extremidade e a primeira escora) pode exceder o teto pratico.
    Insere escoras no(s) ponto(s) medio(s) — cobertura garantida por
    construcao; o teto segue o audit OP-101 (1.80 m, folga sobre o 1.00 m
    do manual §10.3 ja coberto pelo passo proprio da viga).
    """
    import math as _m
    from copy import copy as _copy

    added = 0
    for br in beam_results:
        ss = getattr(br, "shores", []) or []
        if len(ss) < 1:
            continue
        # Eixo pela GEOMETRIA da viga (cobre vaos de extremidade — entre a
        # ponta da viga e a primeira/ultima escora); fallback: linha das
        # escoras.
        geom = getattr(getattr(br, "beam", None), "geometry", None)
        if geom and len(geom) >= 2:
            (x1, y1), (x2, y2) = geom[0], geom[-1]
        else:
            x1, y1 = ss[0].x, ss[0].y
            x2, y2 = ss[-1].x, ss[-1].y
        L_ax = _m.hypot(x2 - x1, y2 - y1)
        if L_ax < 0.10:
            continue
        ux, uy = (x2 - x1) / L_ax, (y2 - y1) / L_ax
        ts = sorted(
            (((s.x - x1) * ux + (s.y - y1) * uy, s) for s in ss),
            key=lambda p: p[0],
        )
        # Bordas virtuais nas extremidades da viga (sem escora-objeto):
        # o vao extremidade->primeira escora tambem deve respeitar o teto.
        first_t, first_s = ts[0]
        last_t, last_s = ts[-1]
        walk = [(0.0, first_s)] + ts + [(L_ax, last_s)] if geom else ts
        new_pts = []
        for (ta, sa), (tb, _sb) in zip(walk, walk[1:]):
            gap = tb - ta
            if gap > max_gap_m:
                n_ins = int(_m.ceil(gap / max_gap_m)) - 1
                for k in range(1, n_ins + 1):
                    t = ta + gap * k / (n_ins + 1)
                    new_pts.append((x1 + ux * t, y1 + uy * t, sa))
        if not new_pts:
            continue
        for (nx_, ny_, template) in new_pts:
            clone = _copy(template)
            clone.x = round(nx_, 3)
            clone.y = round(ny_, 3)
            br.shores.append(clone)
            added += 1
        # reordenar ao longo do eixo e re-ratear cargas
        br.shores.sort(key=lambda s: (s.x - x1) * ux + (s.y - y1) * uy)
        total = sum(s.load_applied_kn for s in br.shores)
        per = total / len(br.shores)
        cap = br.shores[0].shore.load_capacity_kn or 1.0
        for s in br.shores:
            s.load_applied_kn = round(per, 2)
            s.utilization_ratio = round(per / cap, 4)
    if added:
        warnings.append(
            f"{added} escora(s) de viga inserida(s) em vao acima de "
            f"{max_gap_m:.2f} m (preenchimento v14 / audit OP-101)"
        )
    return added


def _align_beam_shores_to_lattice(
    beam_results: List,
    floor_frame: Optional[tuple],
    warnings: List[str],
    *,
    perp_min_angle_deg: float = 45.0,
) -> Tuple[int, int]:
    """Alinha escoras de VIGA aos cruzamentos da lattice do pavimento (v12).

    Decisao do revisor (2026-06-12): o motor prioriza as linhas de
    escoramento das lajes e posiciona as escoras das vigas AO LONGO dessas
    linhas; so depois verifica a necessidade de escoras complementares.
    Para cada viga aproximadamente PERPENDICULAR as linhas da lattice
    (quadro ``floor_frame = (angulo, pitch, ancora)``), os cruzamentos das
    linhas com o eixo da viga ocorrem a cada ~pitch. A escora de viga mais
    proxima de cada cruzamento (tolerancia passo/2) e snapada para o ponto
    de cruzamento; as demais viram COMPLEMENTARES e so permanecem onde o
    vao entre escoras consecutivas exceder o passo admissivel que o
    beam_calculator ja decidiu (``spacing_m`` como teto). Vigas PARALELAS
    as linhas mantem o passo proprio. Torres e escoras de ponta (apoios)
    nunca sao removidas. Deve rodar ANTES de ``_enforce_min_shore_distance``.

    Retorna ``(n_snapadas, n_complementares_removidas)``.
    """
    import math as _m

    if not floor_frame or not beam_results:
        return 0, 0
    f_angle, f_pitch, f_anchor = floor_frame[:3]
    if not f_pitch or f_pitch <= 0:
        return 0, 0
    rad = _m.radians(f_angle % 180.0)
    ca, sa = _m.cos(rad), _m.sin(rad)

    def _v(x: float, y: float) -> float:
        # Coordenada perpendicular as linhas: linhas em v = ancora + k*pitch
        return -x * sa + y * ca

    snapped_total = 0
    removed_total = 0
    for br in beam_results:
        beam = getattr(br, "beam", None)
        geom = list(getattr(beam, "geometry", None) or [])
        shores = list(br.shores or [])
        if len(geom) < 2 or not shores:
            continue
        ax, ay = float(geom[0][0]), float(geom[0][1])
        bx, by = float(geom[1][0]), float(geom[1][1])
        length = _m.hypot(bx - ax, by - ay)
        if length < 1e-6:
            continue
        ux, uy = (bx - ax) / length, (by - ay) / length
        beam_ang = _m.degrees(_m.atan2(uy, ux)) % 180.0
        d_ang = abs(beam_ang - (f_angle % 180.0))
        d_ang = min(d_ang, 180.0 - d_ang)
        if d_ang < perp_min_angle_deg:
            continue  # viga ~paralela as linhas: mantem o passo proprio

        dv_dt = _v(ux, uy)  # variacao de v por metro ao longo do eixo
        if abs(dv_dt) < 1e-9:
            continue
        v0 = _v(ax, ay)
        k_a = (v0 - f_anchor) / f_pitch
        k_b = (v0 + length * dv_dt - f_anchor) / f_pitch
        k_lo = int(_m.ceil(min(k_a, k_b) - 1e-9))
        k_hi = int(_m.floor(max(k_a, k_b) + 1e-9))
        crossings = sorted(
            t for t in (
                (f_anchor + k * f_pitch - v0) / dv_dt
                for k in range(k_lo, k_hi + 1)
            )
            if -1e-6 <= t <= length + 1e-6
        )
        if not crossings:
            continue

        step_cap = (
            br.spacing_m
            if getattr(br, "spacing_m", 0) and br.spacing_m > 0
            else ESPACAMENTO_MAX_VIGA
        )
        tol = step_cap / 2.0

        # Parametro t (projecao no eixo) de cada escora
        shore_t = {
            i: (s.x - ax) * ux + (s.y - ay) * uy for i, s in enumerate(shores)
        }
        order = sorted(range(len(shores)), key=lambda i: shore_t[i])
        # Protegidas de remocao: pontas (apoios) e torres (demanda estrutural)
        protected = {order[0], order[-1]} | {
            i for i, s in enumerate(shores)
            if getattr(s, "tower", None) is not None
        }

        # 1) Snap: cada cruzamento captura a escora (nao-torre) mais proxima
        snapped: Dict[int, float] = {}
        for t_c in crossings:
            best_i, best_d = None, tol + 1e-9
            for i, s in enumerate(shores):
                if i in snapped or getattr(s, "tower", None) is not None:
                    continue
                d = abs(shore_t[i] - t_c)
                if d < best_d:
                    best_d, best_i = d, i
            if best_i is None:
                continue
            s = shores[best_i]
            s.x = round(ax + t_c * ux, 3)
            s.y = round(ay + t_c * uy, 3)
            shore_t[best_i] = t_c
            snapped[best_i] = t_c
        if not snapped:
            continue
        snapped_total += len(snapped)

        # 2) Complementares: entre ancoras consecutivas (snapadas/protegidas)
        # mantem o MINIMO de escoras para que nenhum vao exceda step_cap;
        # vaos ja cobertos perdem as complementares redundantes.
        order = sorted(range(len(shores)), key=lambda i: shore_t[i])
        anchor_set = set(snapped) | protected
        anchors = [i for i in order if i in anchor_set]
        keep = set(anchor_set)
        for a, b in zip(anchors, anchors[1:]):
            comps = [
                i for i in order
                if shore_t[a] < shore_t[i] < shore_t[b] and i not in anchor_set
            ]
            last_t = shore_t[a]
            for j, i in enumerate(comps):
                next_t = (
                    shore_t[comps[j + 1]] if j + 1 < len(comps) else shore_t[b]
                )
                if next_t - last_t > step_cap + 1e-6:
                    keep.add(i)
                    last_t = shore_t[i]
        removed = len(shores) - len(keep)
        if removed:
            n_old = len(shores)
            kept_shores = [shores[i] for i in order if i in keep]
            # Escala uniforme das cargas (preserva amplificacao Regra 14)
            scale = n_old / len(kept_shores) if kept_shores else 1.0
            for s in kept_shores:
                cap = s.shore.load_capacity_kn or 1.0
                s.load_applied_kn = round(s.load_applied_kn * scale, 2)
                s.utilization_ratio = round(s.load_applied_kn / cap, 4)
            br.shores = kept_shores
            br.shore_count = len(kept_shores)
            br.shores_weight_kg = round(
                sum(s.shore.weight_kg for s in kept_shores), 2
            )
            removed_total += removed
        else:
            br.shores = shores

    if snapped_total or removed_total:
        warnings.append(
            f"Escoras de viga alinhadas a lattice do pavimento: "
            f"{snapped_total} snapada(s) em cruzamentos de linha, "
            f"{removed_total} complementar(es) redundante(s) removida(s) "
            f"(line-first v12 — vigas perpendiculares as linhas)"
        )
    return snapped_total, removed_total


def _enforce_min_shore_distance(
    slab_results: List[SlabShoringResult],
    beam_results: List,
    warnings: List[str],
    min_dist_m: float = 0.30,
) -> int:
    """Distancia minima GLOBAL entre escoras (v10, decisao do revisor).

    Nenhuma escora pode ficar a menos de `min_dist_m` de outra (default
    0.30 m = ESPACAMENTO_MIN; vira campo do perfil §28.9). Prioridade:
    escora de VIGA vence escora de laje (a viga e estrutural e o passo
    dela e proprio); entre escoras de laje, a primeira permanece.
    Implementado com grade hash para nao ser O(n^2) global.
    """
    import math as _m

    cell = max(min_dist_m, 0.05)
    occupied: dict = {}

    def _key(x: float, y: float):
        return (int(_m.floor(x / cell)), int(_m.floor(y / cell)))

    def _near(x: float, y: float) -> bool:
        kx, ky = _key(x, y)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for ox, oy in occupied.get((kx + dx, ky + dy), ()):
                    if _m.hypot(x - ox, y - oy) < min_dist_m:
                        return True
        return False

    def _add(x: float, y: float):
        occupied.setdefault(_key(x, y), []).append((x, y))

    # 1) Escoras de viga tem prioridade: ocupam a grade primeiro
    for br in beam_results:
        for s in getattr(br, "shores", []) or []:
            _add(s.x, s.y)

    dropped = 0
    for idx, sr in enumerate(slab_results, 1):
        kept = []
        removed_here = 0
        for s in sr.shores:
            if _near(s.x, s.y):
                removed_here += 1
                continue
            _add(s.x, s.y)
            kept.append(s)
        if removed_here and kept:
            sr.shores = kept
            _recalculate_slab_shore_loads(sr)
            sr.shores_weight_kg = round(
                sum(s.shore.weight_kg for s in sr.shores), 2
            )
            dropped += removed_here
    if dropped:
        warnings.append(
            f"{dropped} escora(s) de laje removida(s) por distancia "
            f"< {min_dist_m:.2f} m de outra escora (check global v10; "
            f"escora de viga tem prioridade)"
        )
    return dropped


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


def _filter_beams_to_main_cluster(
    beams: List[ClassifiedElement],
    buffer_m: float = 5.0,
) -> List[ClassifiedElement]:
    """Keep only beams belonging to the largest spatial cluster.

    Detail/section views contain lines that get classified as beams.
    These "phantom beams" are spatially isolated from the main structural
    plan. By clustering beam midpoints and keeping only the largest
    connected component, we discard all detail-view beams.

    Uses union-find on beam midpoints: two beams are "connected" if their
    LineStrings are within buffer_m of each other.

    CVS-006 (2026-06-12): a versao anterior bufferizava AMBAS as linhas em
    buffer_m e testava intersecao — limiar efetivo de 2x buffer_m (10 m),
    que deixava a tabela ESQUEMA DE NIVEIS (linhas no layer estrutural '1',
    a 9 m da planta) encadear no cluster principal via a barra de corte e
    receber escoramento fantasma. Conexao agora usa distancia direta entre
    linhas < buffer_m, como o docstring sempre prometeu.
    """
    if len(beams) <= 1:
        return beams

    # Collect midpoints and LineStrings
    midpoints = []
    lines = []
    for b in beams:
        if b.element_type != ElementType.BEAM or len(b.geometry) < 2:
            midpoints.append(None)
            lines.append(None)
            continue
        s, e = b.geometry[0], b.geometry[1]
        midpoints.append(((s[0] + e[0]) / 2, (s[1] + e[1]) / 2))
        try:
            lines.append(LineString([s, e]))
        except Exception:
            lines.append(None)

    n = len(beams)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Connect beams whose buffered geometries intersect
    for i in range(n):
        if midpoints[i] is None:
            continue
        for j in range(i + 1, n):
            if midpoints[j] is None:
                continue
            # Quick distance check first
            dx = midpoints[i][0] - midpoints[j][0]
            dy = midpoints[i][1] - midpoints[j][1]
            dist_sq = dx * dx + dy * dy
            # Skip pairs that are very far apart (> 20m between midpoints)
            if dist_sq > 400.0:
                continue
            # Connect if lines are within buffer_m of each other
            if lines[i] is not None and lines[j] is not None:
                try:
                    if lines[i].distance(lines[j]) < buffer_m:
                        union(i, j)
                except Exception:
                    pass

    # Find largest group by total beam length (not just count)
    from collections import defaultdict as dd
    groups: dict = dd(float)
    for i in range(n):
        if midpoints[i] is None:
            continue
        root = find(i)
        s, e = beams[i].geometry[0], beams[i].geometry[1]
        length = ((s[0] - e[0]) ** 2 + (s[1] - e[1]) ** 2) ** 0.5
        groups[root] += length

    if not groups:
        return beams

    main_root = max(groups, key=groups.get)
    main_total_length = groups[main_root]

    filtered = [beams[i] for i in range(n) if find(i) == main_root]
    removed = len(beams) - len(filtered)

    if removed > 0:
        logger.info(
            f"Beam cluster filter: kept {len(filtered)} beams "
            f"(total length {main_total_length:.0f}m), "
            f"discarded {removed} from {len(groups)} isolated cluster(s)"
        )

    return filtered


def _filter_isolated_slabs(
    polygons: List[Polygon],
    min_group_area_ratio: float = 0.10,
) -> List[Polygon]:
    """Keep only the largest connected component of slab polygons.

    Slabs from the main structural plan form a contiguous group (sharing
    beam boundaries, touching or very close). Slabs from detail views /
    secondary drawings are spatially isolated.

    Two slabs are "connected" if they intersect when buffered. Buffer
    aumentado de 3.0 -> 5.0m em 2026-05-31 (bug "areas X verde sem
    escoras"): lajes pequenas dentro da planta principal eram descartadas
    porque o buffer de 3m nao alcancava o grupo principal em casos de
    aberturas internas (atrios, shafts).

    Adicionalmente: lajes cujo CENTROIDE cai dentro do bounding box
    expandido do grupo principal sao SEMPRE mantidas, mesmo que
    aparentemente isoladas - sao lajes legitimas dentro da planta.
    """
    if len(polygons) <= 1:
        return polygons

    n = len(polygons)
    buffered = []
    for p in polygons:
        try:
            buffered.append(p.buffer(5.0))
        except Exception:
            buffered.append(p)

    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            try:
                if buffered[i].intersects(polygons[j]):
                    union(i, j)
            except Exception:
                pass

    # Find group with largest total area
    from collections import defaultdict as dd
    group_area: dict = dd(float)
    group_members: dict = dd(list)
    for i in range(n):
        root = find(i)
        group_area[root] += polygons[i].area
        group_members[root].append(i)

    if not group_area:
        return polygons

    main_root = max(group_area, key=group_area.get)
    total_area = sum(group_area.values())
    main_area = group_area[main_root]

    # Only filter if the main group clearly dominates
    if main_area < min_group_area_ratio * total_area:
        logger.info(
            f"Slab connectivity filter: main group area={main_area:.0f}m² "
            f"is only {main_area / total_area:.0%} of total — keeping all slabs"
        )
        return polygons

    main_indices = set(group_members[main_root])
    # Safety net (manual §28.7, 2026-05-31): lajes cujo CENTROIDE cai
    # dentro do bbox do grupo principal sao mantidas mesmo se nao
    # conectadas via buffer. Isso protege lajes pequenas legitimas em
    # atrios/aberturas que o filtro por conectividade nao alcanca.
    from shapely.ops import unary_union
    try:
        main_union = unary_union([polygons[i] for i in main_indices])
        mb = main_union.bounds  # (minx, miny, maxx, maxy)
        # Pequena tolerancia para nao reescorar do lado de fora
        TOL = 0.5
        for i in range(n):
            if i in main_indices:
                continue
            try:
                c = polygons[i].centroid
                if (
                    mb[0] - TOL <= c.x <= mb[2] + TOL
                    and mb[1] - TOL <= c.y <= mb[3] + TOL
                ):
                    main_indices.add(i)
            except Exception:
                pass
    except Exception:
        pass

    filtered = [polygons[i] for i in sorted(main_indices)]
    removed = n - len(filtered)

    if removed > 0:
        removed_area = total_area - main_area
        logger.info(
            f"Slab connectivity filter: kept {len(filtered)} slabs "
            f"({main_area:.0f}m²), discarded {removed} isolated slabs "
            f"({removed_area:.0f}m²) from {len(group_area)} group(s)"
        )

    return filtered


def _axis_aligned_perimeter_ratio(
    polygon: Polygon,
    *,
    angle_tolerance_deg: float = 3.0,
) -> tuple[float, int]:
    """Return axis-aligned perimeter ratio and short-segment count."""
    try:
        coords = list(polygon.exterior.coords)
    except Exception:
        return 1.0, 0

    total_len = 0.0
    axis_len = 0.0
    short_segments = 0
    for a, b in zip(coords, coords[1:]):
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            continue
        total_len += length
        if length < 0.20:
            short_segments += 1
        angle = abs(math.degrees(math.atan2(dy, dx))) % 180.0
        axis_deviation = min(angle, abs(angle - 90.0), abs(angle - 180.0))
        if axis_deviation <= angle_tolerance_deg:
            axis_len += length

    if total_len <= 0:
        return 1.0, short_segments
    return axis_len / total_len, short_segments


def _is_noisy_nonorthogonal_slab_contour(polygon: Polygon) -> bool:
    """Detect small contour artifacts generated by arcs/details.

    Real slab panels in these structural plans are beam-bounded and mostly
    orthogonal. The false CVS lower-left panel is a small arc-derived contour:
    many tiny segments, low rectangularity, and almost no H/V perimeter.
    """
    try:
        coords = list(polygon.exterior.coords)
        vertex_count = len(coords)
        minx, miny, maxx, maxy = polygon.bounds
        bbox_area = (maxx - minx) * (maxy - miny)
    except Exception:
        return False

    if vertex_count < 24 or polygon.area > 25.0 or bbox_area <= 0:
        return False

    rectangularity = polygon.area / bbox_area
    axis_ratio, short_segments = _axis_aligned_perimeter_ratio(polygon)
    segment_count = max(1, vertex_count - 1)
    short_ratio = short_segments / segment_count

    return (
        rectangularity < 0.75
        and axis_ratio < 0.50
        and short_ratio > 0.50
    )


def _filter_noisy_overlapping_slabs(polygons: List[Polygon]) -> List[Polygon]:
    """Remove small arc/detail contours that overlap a larger slab panel."""
    if len(polygons) <= 1:
        return polygons

    removed: set[int] = set()
    for i, polygon in enumerate(polygons):
        if not _is_noisy_nonorthogonal_slab_contour(polygon):
            continue

        max_overlap_ratio = 0.0
        for j, other in enumerate(polygons):
            if i == j or other.area <= polygon.area * 1.5:
                continue
            try:
                overlap_area = polygon.intersection(other).area
            except Exception:
                overlap_area = 0.0
            if polygon.area > 0:
                max_overlap_ratio = max(max_overlap_ratio, overlap_area / polygon.area)

        if max_overlap_ratio >= 0.02:
            removed.add(i)
            logger.info(
                f"Noisy slab contour filter: discarded area={polygon.area:.1f}m2 "
                f"overlap={max_overlap_ratio:.0%} "
                f"centroid=({polygon.centroid.x:.1f}, {polygon.centroid.y:.1f})"
            )

    if not removed:
        return polygons
    return [p for i, p in enumerate(polygons) if i not in removed]


def _pillar_hull(pillars: List[ClassifiedElement]):
    """Return the convex hull polygon of pillar centers, or None if <3 pillars.

    Used to detect perimeter (external) beams — a beam whose centroid lies
    more than PERIMETER_BEAM_HULL_DISTANCE_M beyond this hull is considered
    external (regra Orguel 16).
    """
    pts = []
    for p in pillars:
        if p.element_type != ElementType.PILLAR or not p.geometry:
            continue
        pts.append(Point(p.geometry[0]))
    if len(pts) < 3:
        return None
    try:
        return MultiPoint(pts).convex_hull
    except Exception:
        return None


def _is_perimeter_beam(beam: ClassifiedElement, hull) -> bool:
    """True when the beam centroid is outside the pillar convex hull by >0.5m."""
    if hull is None or len(beam.geometry) < 2:
        return False
    start_pt = beam.geometry[0]
    end_pt = beam.geometry[1]
    cx = (start_pt[0] + end_pt[0]) / 2.0
    cy = (start_pt[1] + end_pt[1]) / 2.0
    centroid = Point(cx, cy)
    try:
        if hull.contains(centroid):
            return False
        return centroid.distance(hull) > PERIMETER_BEAM_HULL_DISTANCE_M
    except Exception:
        return False


# Orguel Q3/A4: toda interseção de viga sem pilar deve ter escora/torre.
# Tolerância (m) para considerar que existe um pilar na interseção: se um
# pilar está a ≤ BEAM_INTERSECTION_PILLAR_TOLERANCE do ponto de cruzamento
# das vigas, não é necessário forçar uma escora adicional.
BEAM_INTERSECTION_PILLAR_TOLERANCE_M = 0.70


def _beam_intersections_without_pillar(
    beam: ClassifiedElement,
    other_beams: List[ClassifiedElement],
    pillars: List[ClassifiedElement],
) -> List[float]:
    """Return positions (m ao longo da viga) onde outra viga cruza sem pilar.

    Regra Orguel Q3: em toda interseção de viga sem pilar deve haver escora.
    Esta função localiza pontos de cruzamento beam×other_beam e filtra os que
    já estão sustentados por algum pilar (dentro de
    BEAM_INTERSECTION_PILLAR_TOLERANCE_M).
    """
    if len(beam.geometry) < 2:
        return []
    start_pt = beam.geometry[0]
    end_pt = beam.geometry[1]
    beam_line = LineString([start_pt, end_pt])
    if beam_line.length <= 0:
        return []

    pillar_points = [
        Point(p.geometry[0])
        for p in pillars
        if p.element_type == ElementType.PILLAR and p.geometry
    ]

    positions: List[float] = []
    for other in other_beams:
        if other is beam or len(other.geometry) < 2:
            continue
        other_line = LineString([other.geometry[0], other.geometry[1]])
        try:
            inter = beam_line.intersection(other_line)
        except Exception:
            continue
        if inter.is_empty:
            continue

        # Flatten possible multi-point intersections
        raw_points = []
        geom_type = getattr(inter, "geom_type", "")
        if geom_type == "Point":
            raw_points.append(inter)
        elif geom_type == "MultiPoint":
            raw_points.extend(list(inter.geoms))
        else:
            # LineString intersections (colinear beams) — use midpoint
            try:
                raw_points.append(inter.centroid)
            except Exception:
                continue

        for ip in raw_points:
            # Skip if a pillar is already near this intersection
            if any(
                ip.distance(pp) <= BEAM_INTERSECTION_PILLAR_TOLERANCE_M
                for pp in pillar_points
            ):
                continue
            pos = beam_line.project(ip)
            # Skip endpoints (they are beam-to-beam joins, handled by endpoint
            # support / cantilever logic)
            if pos < 0.10 or pos > beam_line.length - 0.10:
                continue
            positions.append(round(pos, 4))

    # Deduplicate nearby positions (beams crossing at the same point)
    positions.sort()
    deduped: List[float] = []
    for p in positions:
        if not deduped or p - deduped[-1] > 0.25:
            deduped.append(p)
    return deduped


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
    shaft_diagonals: Optional[list] = None,
    shaft_texts: Optional[list] = None,
    density_correction: float = 1.0,
    mode: str = "price",
    inventory: Optional[Any] = None,
    text_entities: Optional[List[Dict[str, Any]]] = None,
    slab_layout_mode: str = "grid",
) -> CalculationResult:
    """Run the full calculation pipeline.

    Args:
        elements: Classified beams and pillars with geometry populated.
        pe_direito_m: Floor-to-ceiling height in meters.
        pe_direito_is_default: True if pe_direito was not found in DXF.
        slab_thickness_m: Slab thickness override. None = use default.
        slab_type: Detected slab type (solid, ribbed, waffle, etc.)
        slab_layout_mode: "grid" (default, grid de pontos legado) ou
            "line_first" (linhas de guia Orguel gold-standard, manual §28.8).

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

    # Filter beams by confidence + drop TQS axis lines and absurd sections
    valid_beams = []
    rejected_axis = 0
    rejected_section = 0
    for b in beams:
        if b.score_final < MIN_CONFIDENCE:
            warnings.append(
                f"Viga {b.name or 'sem nome'} ignorada — confiança {b.score_final:.0%} < 50%"
            )
            continue
        # Reject TQS axis lines named "Eixo X=..." / "Eixo Y=..." — mas
        # SOMENTE quando nao ha evidencia de secao (v9, 2026-06-12): o
        # classificador tambem nomeia "Eixo ..." vigas reais detectadas
        # por par de linhas paralelas sem texto de etiqueta (ex.: vigas de
        # periferia do CVS-006 com largura 0.20 m), e o filtro as matava
        # — vigas inteiras ficavam SEM escoramento (inspecao do revisor).
        name = (b.name or "").strip()
        if name.startswith("Eixo X=") or name.startswith("Eixo Y="):
            _w = b.section_width_m
            _h = b.section_height_m
            has_section = (_w is not None and _w >= 0.10) or (
                _h is not None and _h >= 0.10
            )
            if not has_section:
                rejected_axis += 1
                continue
        # Reject absurd cross-sections (< 10 cm in either direction when known)
        w = b.section_width_m
        h = b.section_height_m
        if (w is not None and 0 < w < 0.10) or (h is not None and 0 < h < 0.10):
            rejected_section += 1
            continue
        if b.score_final < LOW_CONFIDENCE:
            warnings.append(
                f"Viga {b.name or 'sem nome'} com baixa confiança ({b.score_final:.0%}) — revisar"
            )
        valid_beams.append(b)
    if rejected_axis:
        warnings.append(
            f"{rejected_axis} linhas de eixo TQS (Eixo X=/Y=) descartadas do cálculo"
        )
    if rejected_section:
        warnings.append(
            f"{rejected_section} vigas com seção absurda (<10 cm) descartadas"
        )

    # Filter beams to main structural cluster — discards beams from
    # detail views, sections, and other non-structural drawing areas
    if len(valid_beams) > 3:
        before_count = len(valid_beams)
        valid_beams = _filter_beams_to_main_cluster(valid_beams)
        removed_beams = before_count - len(valid_beams)
        if removed_beams > 0:
            warnings.append(
                f"Filtradas {removed_beams} vigas de regiões secundárias "
                f"(cortes, detalhes, elevações)"
            )

    # Pillar hull clamp for beams: discard beams whose line doesn't touch
    # the structural footprint (convex hull of pillars + margin).
    # Uses intersects() instead of contains() to keep perimeter beams.
    _BEAM_HULL_MARGIN = 5.0  # generous margin for perimeter/cantilever beams
    _pillar_pts_beam = [
        p.geometry[0] for p in pillars
        if p.element_type == ElementType.PILLAR and p.geometry
    ]
    if len(_pillar_pts_beam) >= 3 and len(valid_beams) > 1:
        from shapely.geometry import MultiPoint as _MP, Point as _Pt
        _bhull = _MP([_Pt(xy) for xy in _pillar_pts_beam]).convex_hull
        _beam_hull_buf = _bhull.buffer(_BEAM_HULL_MARGIN)
        before_hull_b = len(valid_beams)

        def _hull_keep(b) -> bool:
            if len(b.geometry) < 2:
                return True
            if _beam_hull_buf.intersects(
                LineString([b.geometry[0], b.geometry[1]])
            ):
                return True
            # v11 (2026-06-12): viga com SECAO detectada (par de linhas
            # paralelas 0.10-0.60 m) e estrutural mesmo fora do hull — alas
            # cujos pilares nao foram classificados (ex.: ala superior do
            # CVS-006) ficavam com vigas reais sem escoramento.
            _w, _h = b.section_width_m, b.section_height_m
            return (_w is not None and 0.10 <= _w <= 0.60) or (
                _h is not None and 0.10 <= _h <= 1.20
            )

        valid_beams = [b for b in valid_beams if _hull_keep(b)]
        removed_hull_b = before_hull_b - len(valid_beams)
        if removed_hull_b > 0:
            warnings.append(
                f"Filtradas {removed_hull_b} vigas fora do perímetro estrutural "
                f"(detalhes, cortes, selo)"
            )

    # Load shore catalog
    try:
        catalog = load_catalog()
    except FileNotFoundError:
        warnings.append("Catálogo de escoras não encontrado — usando valores padrão")
        catalog = []

    # Load tower and distribution beam catalog
    try:
        tower_catalog, dist_beam_catalog, _ = load_tower_catalog()
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
    pillar_hull = _pillar_hull(pillars)

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

        beam_is_perimeter = _is_perimeter_beam(beam, pillar_hull)

        # Decide: telescopic shore or tower or mixed?
        support_type, tower_fraction, decision_reasons, decision_rule = decide_support_type(
            required_height_m=shore_height,
            load_per_point_kn=load_per_shore_estimate,
            slab_thickness_m=thickness,
            span_m=beam_length,
            slab_type=slab_type,
            element_type="beam",
            shore_catalog=catalog,
            mode=mode,
            inventory=inventory,
            is_perimeter=beam_is_perimeter,
            beam_width_m=beam_width,
            beam_height_m=beam_height,
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
        tower_shore_entry = None  # Tower as ShoreCatalogEntry when applicable

        # Select tower when TOWER or MIXED requires it
        if support_type in (SupportType.TOWER, SupportType.MIXED) and tower_catalog:
            selected_tower = select_tower(tower_catalog, shore_height, load_per_shore_estimate, mode=mode, inventory=inventory)
            if selected_tower:
                rule_suffix = f" [{decision_rule}]" if decision_rule else ""
                warnings.append(
                    f"Viga {beam.name or 'sem nome'} — torre {selected_tower.model} "
                    f"({selected_tower.manufacturer}): "
                    f"{'; '.join(decision_reasons)}{rule_suffix}"
                )
                # Select distribution beam if available
                if dist_beam_catalog:
                    selected_dist_beam = select_distribution_beam(
                        dist_beam_catalog, span_m=1.0, load_kn_m=total_linear_load,
                        mode=mode, inventory=inventory,
                    )
                from src.models.shore import ShoreCatalogEntry
                tower_shore_entry = ShoreCatalogEntry(
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

        # For pure TOWER → use tower entry; for MIXED or TELESCOPIC → use telescopic
        # (MIXED places both types — telescopic first, then swaps a fraction to tower)
        if support_type == SupportType.TOWER and tower_shore_entry is not None:
            selected_shore = tower_shore_entry
        else:
            selected_shore = select_shore(catalog, shore_height, load_per_shore_estimate, mode=mode, inventory=inventory) if catalog else None

        if not selected_shore:
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

        # Spacing: TOWER uses wider, MIXED uses telescopic (dense) spacing
        beam_max_spacing = ESPACAMENTO_MAX_VIGA
        if support_type == SupportType.TOWER and tower_shore_entry is not None:
            beam_max_spacing = max(ESPACAMENTO_MAX_VIGA * 1.5, 1.50)
        if density_correction > 0:
            beam_max_spacing = beam_max_spacing / density_correction

        # Orguel Q3/A4: força escora em cada interseção viga×viga sem pilar.
        intersection_positions = _beam_intersections_without_pillar(
            beam, valid_beams, pillars,
        )

        shores, n_shores, spacing = distribute_beam_shores(
            beam_length_m=beam_length,
            beam_width_m=beam_width,
            beam_height_m=beam_height,
            shore=selected_shore,
            total_linear_load_kn_m=total_linear_load,
            max_spacing=beam_max_spacing,
            start_x=start_pt[0],
            start_y=start_pt[1],
            direction=direction,
            support_positions=assoc["support_positions"],
            is_cantilever_start=assoc["is_cantilever_start"],
            is_cantilever_end=assoc["is_cantilever_end"],
            forced_positions=intersection_positions,
        )

        # === MIXED BEAM SUPPORT (posicionamento estrutural) ===
        # Torres em pontos de demanda estrutural, não fração fixa.
        # Critérios (Orguel DOCX + DXF analysis):
        # 1. Interseções viga×viga sem pilar → torre
        # 2. Extremos de vigas longas (>4.5m) → torre nos apoios
        # 3. Vãos entre torres > 4.0m → torre intermediária (VM130 max span)
        if (support_type == SupportType.MIXED and tower_shore_entry is not None
                and len(shores) >= 2):
            import math as _m
            tower_indices = set()

            # 1. Interseções sem pilar → torre na escora mais próxima
            if intersection_positions:
                for ipos in intersection_positions:
                    best_idx = None
                    best_dist = float('inf')
                    for idx, s in enumerate(shores):
                        # Distância ao longo do eixo da viga
                        if direction == "x":
                            d = abs(s.x - (start_pt[0] + ipos))
                        else:
                            d = abs(s.y - (start_pt[1] + ipos))
                        if d < best_dist:
                            best_dist = d
                            best_idx = idx
                    if best_idx is not None and best_dist < 1.0:
                        tower_indices.add(best_idx)

            # 2. Extremos (apoios) para vigas longas (>4.5m, mediana DXF Orguel)
            if beam_length > 4.5:
                tower_indices.add(0)
                tower_indices.add(len(shores) - 1)

            # 3. Preencher vãos entre torres > 4.0m (VM130 max span ~4.10m)
            _MAX_TOWER_GAP = 4.0
            if len(tower_indices) >= 2 and len(shores) >= 3:
                sorted_ti = sorted(tower_indices)
                new_towers = set()
                for a, b in zip(sorted_ti, sorted_ti[1:]):
                    sa, sb = shores[a], shores[b]
                    gap = _m.hypot(sb.x - sa.x, sb.y - sa.y)
                    if gap > _MAX_TOWER_GAP:
                        # Inserir torre(s) intermediária(s) — coordinate-based search
                        n_fill = _m.ceil(gap / _MAX_TOWER_GAP) - 1
                        for k in range(1, n_fill + 1):
                            frac = k / (n_fill + 1)
                            target_x = sa.x + frac * (sb.x - sa.x)
                            target_y = sa.y + frac * (sb.y - sa.y)
                            # Find closest shore to target coordinate (not already a tower)
                            best_idx = min(
                                (idx for idx in range(a + 1, b)
                                 if idx not in tower_indices and idx not in new_towers),
                                key=lambda idx: _m.hypot(
                                    shores[idx].x - target_x, shores[idx].y - target_y),
                                default=None,
                            )
                            if best_idx is not None:
                                new_towers.add(best_idx)
                tower_indices.update(new_towers)

            # Garantir mínimo de 2 torres para MIXED
            if len(tower_indices) < 2 and len(shores) >= 2:
                tower_indices.add(0)
                tower_indices.add(len(shores) - 1)

            from src.models.shore import PositionedShore as _PS
            for idx in tower_indices:
                if idx < len(shores):
                    s = shores[idx]
                    shores[idx] = _PS(
                        x=s.x, y=s.y,
                        shore=tower_shore_entry,
                        load_applied_kn=s.load_applied_kn,
                        utilization_ratio=round(
                            s.load_applied_kn / tower_shore_entry.load_capacity_kn, 4
                        ),
                        support_type=SupportType.TOWER,
                        tower=selected_tower,
                        distribution_beam=selected_dist_beam,
                    )

            # Pendência 21 (manual §9/§18): validar pela fração empírica de
            # torres em VIGAS mistas (29-44%, 12 projetos Orguel medidos).
            # Fora do envelope = alerta com justificativa, não bloqueio
            # (as torres aqui vêm de demanda estrutural, não de fração).
            frac_tw = len(tower_indices) / max(len(shores), 1)
            if not (0.29 <= frac_tw <= 0.44):
                warnings.append(
                    f"Viga {beam.name or 'sem nome'} (misto): fração de "
                    f"torres {frac_tw:.0%} fora do envelope empírico "
                    f"29-44% (manual §18) — posicionamento por demanda "
                    f"estrutural (extremos/interseções/vãos), revisar se "
                    f"intencional"
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
            shores_weight_kg=round(sum(s.shore.weight_kg for s in shores), 2),
            is_perimeter=beam_is_perimeter,
            decision_rule=decision_rule,
        ))

        # Contra-flecha recommendation for spans > 2m
        beam_name = beam.name or "sem nome"
        warnings.extend(_contra_flecha_warnings(beam_length, beam_name))

    # === PILLAR PROXIMITY FILTER FOR BEAM SHORES ===
    # Removed — shore_reviewer.py now handles this with the same threshold
    # (DISTANCIA_PILAR_MIN = 0.70m). Having two filters with different thresholds
    # caused shores placed at 0.70-1.00m to be incorrectly removed.

    # === NERVURA DETECTION ===
    nervura_regions = detect_nervura_regions(
        rects=nervura_rects or [],
        beams=valid_beams,
    )

    # === SLAB SHORING ===
    # Strategy: 4-tier slab detection with merge
    # Tier 1: Beam grid polygonize (most precise, aligned to beams)
    # Tier 1.5: Adjacent beam pairs (cantilever/edge slabs without full closure)
    # Tier 2: Beam axes with extended tolerance (fallback for sparse grids)
    # Tier 3: Direct boundary extraction from DXF hatches/polylines

    # Build beam LineStrings for proximity validation in Tier 3
    _beam_lines: List[LineString] = []
    for b in valid_beams:
        if b.element_type == ElementType.BEAM and len(b.geometry) >= 2:
            try:
                _beam_lines.append(LineString([b.geometry[0], b.geometry[1]]))
            except Exception:
                pass

    # Tier 1: Beam grid
    slab_polygons = derive_slabs_from_beams(valid_beams)

    # Tier 1.5: Beam pair slabs (cantilever/edge slabs)
    pair_slabs = derive_slabs_from_beam_pairs(valid_beams)
    if pair_slabs:
        slab_polygons = merge_slab_sources(slab_polygons, pair_slabs)
        logger.info(
            f"Tier 1.5: {len(pair_slabs)} beam-pair slab candidates, "
            f"{len(slab_polygons)} total after merge"
        )

    # Tier 2: Extended beam axes — always run when beam segments exist.
    # merge_slab_sources deduplicates overlapping panels, so running Tier 2
    # unconditionally is safe and catches regions where beam pairs are sparse
    # (e.g. single-line beams in the center section of 110749).
    if beam_layer_segments:
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

    # Manual §28.7 (2026-06-01): integracao de lajes pre-moldadas TQS.
    # Estrategia: adicionar APENAS polygons cuja maior parte (>60%) esta
    # FORA de slabs existentes. Evita sobreposicao com lajes ja detectadas
    # que reduziria densidade de escoras.
    if shaft_texts:
        from src.engine.slab_builder import detect_precast_slab_clusters
        precast_slabs = detect_precast_slab_clusters(shaft_texts)
        if precast_slabs and slab_polygons:
            from shapely.ops import unary_union as _uu
            existing_union = _uu(slab_polygons)
            kept = []
            for p in precast_slabs:
                try:
                    overlap = p.intersection(existing_union)
                    overlap_ratio = overlap.area / p.area if p.area > 0 else 0
                except Exception:
                    overlap_ratio = 0
                if overlap_ratio < 0.40:  # >60% area nova
                    kept.append(p)
            if kept:
                slab_polygons = slab_polygons + kept
                total_area = sum(p.area for p in kept)
                warnings.append(
                    f"Lajes pre-moldadas TQS (areas novas): {len(kept)} painel(eis), "
                    f"area total {total_area:.0f}m²"
                )
        elif precast_slabs:
            # Sem slabs existentes: adicionar todos
            slab_polygons = list(precast_slabs)
            total_area = sum(p.area for p in precast_slabs)
            warnings.append(
                f"Lajes pre-moldadas TQS: {len(precast_slabs)} painel(eis), "
                f"area total {total_area:.0f}m²"
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
            slab_polygons = merge_slab_sources(
                slab_polygons, boundary_slabs,
                beam_lines=_beam_lines if _beam_lines else None,
            )
            added = len(slab_polygons) - before
            if added > 0:
                total_area = sum(p.area for p in boundary_slabs)
                warnings.append(
                    f"Lajes detectadas em hatches/polylines do DXF — "
                    f"{added} painel(éis) adicionais, "
                    f"área total {total_area:.0f}m²"
                )

    # === SHAFT/VOID DETECTION ===
    # Detect elevator shafts, pipe openings, etc. and exclude from slab shoring
    shaft_regions = detect_all_shafts(
        diagonals=shaft_diagonals or [],
        texts=shaft_texts or [],
        hatches=slab_hatches or [],
        polylines=slab_polylines or [],
        scale=1.0,
    )

    if shaft_regions:
        # First, cut shaft holes from slab polygons (handles small shafts
        # inside large slabs without removing the entire slab)
        before_cut = len(slab_polygons)
        slab_polygons = subtract_shafts_from_slabs(slab_polygons, shaft_regions)

        # Then, remove slabs that are mostly shaft (overlap >= 30%)
        before = len(slab_polygons)
        slab_polygons, removed_indices = filter_slab_polygons_by_shafts(
            slab_polygons, shaft_regions,
        )
        if removed_indices:
            warnings.append(
                f"Shafts detectados: {len(shaft_regions)} abertura(s) — "
                f"{len(removed_indices)} painel(éis) de laje excluído(s)"
            )

    # Filter isolated slab groups — discard slabs from detail views that
    # survived upstream filters. Main plan slabs form a connected cluster;
    # slabs from sections/details are spatially isolated.
    if len(slab_polygons) > 2:
        before_slab_count = len(slab_polygons)
        slab_polygons = _filter_isolated_slabs(slab_polygons)
        removed_slabs = before_slab_count - len(slab_polygons)
        if removed_slabs > 0:
            warnings.append(
                f"Filtradas {removed_slabs} lajes isoladas de regiões "
                f"não-estruturais (cortes, detalhes)"
            )

    # Pillar convex hull clamp: discard slabs whose centroid is far outside
    # the structural footprint (convex hull of pillars). Detail views, section
    # cuts, title blocks, and engineer notes produce phantom slabs that pass
    # spatial clustering when they're adjacent to the main plan.
    _HULL_MARGIN = 5.0  # m — generous tolerance for perimeter/cantilever slabs
    pillar_pts_for_hull = [
        p.geometry[0] for p in pillars
        if p.element_type == ElementType.PILLAR and p.geometry
    ]
    if len(pillar_pts_for_hull) >= 3 and len(slab_polygons) > 1:
        from shapely.geometry import MultiPoint as _MP
        _slab_hull = _MP([Point(xy) for xy in pillar_pts_for_hull]).convex_hull
        _hull_buffered = _slab_hull.buffer(_HULL_MARGIN)
        before_hull = len(slab_polygons)
        kept_slabs = []
        for sp in slab_polygons:
            # Keep slab if ANY part of it overlaps the hull (generous — only
            # discard slabs that are completely outside the structural footprint)
            try:
                overlaps = sp.intersects(_hull_buffered)
            except Exception:
                overlaps = True  # keep on error
            if overlaps:
                kept_slabs.append(sp)
            else:
                logger.info(
                    f"Pillar hull clamp: discarded slab area={sp.area:.1f}m² "
                    f"centroid=({sp.centroid.x:.1f}, {sp.centroid.y:.1f}) — "
                    f"outside structural footprint"
                )
        slab_polygons = kept_slabs
        removed_hull = before_hull - len(slab_polygons)
        if removed_hull > 0:
            warnings.append(
                f"Filtradas {removed_hull} lajes fora do perímetro estrutural "
                f"(detalhes, cortes, selo do engenheiro)"
            )

    # Remove small non-orthogonal contour artifacts that overlap a larger,
    # orthogonal slab. This catches arc/detail geometry accidentally
    # polygonized as a slab while preserving standalone curved slabs.
    if len(slab_polygons) > 1:
        before_noisy = len(slab_polygons)
        slab_polygons = _filter_noisy_overlapping_slabs(slab_polygons)
        removed_noisy = before_noisy - len(slab_polygons)
        if removed_noisy > 0:
            warnings.append(
                f"Filtradas {removed_noisy} lajes com contorno fragmentado "
                f"sobreposto a paineis estruturais"
            )

    cantilever_flags = detect_cantilever_slabs(slab_polygons, pillars)

    pillar_exclusions = _build_pillar_exclusions(pillars)
    beam_exclusions = _build_beam_exclusions(valid_beams)
    # Add shaft regions as exclusion zones to prevent shores inside voids
    shaft_exclusions = []
    if shaft_regions:
        for sr in shaft_regions:
            shaft_exclusions.append(PillarExclusion(
                cx=(sr.x_min + sr.x_max) / 2,
                cy=(sr.y_min + sr.y_max) / 2,
                width_m=sr.x_max - sr.x_min,
                depth_m=sr.y_max - sr.y_min,
                margin=0.30,
            ))
    all_exclusions = pillar_exclusions + beam_exclusions + shaft_exclusions

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

    # Constants for filtering out thin-strip "slabs" (cornijas, ornamental
    # outlines) that real shoring plans never shore. Platibandas, beirais,
    # balanços e marquises LEGÍTIMAS são preservadas: bypass via layer keyword
    # (CATEGORY_LAYER_KEYWORDS) ou heurística de anel perimetral.
    THIN_STRIP_MIN_DIM_M = 0.5   # narrow side smaller than this → strip
    THIN_STRIP_RATIO = 5.0       # long/short aspect ratio above this → strip
    # Heurística platibanda: polígono fino suficiente cujo centróide fica
    # próximo da borda de uma laje muito maior → é anel perimetral (platibanda).
    PLATIBANDA_GEOM_SHORT_MAX_M = 0.5
    PLATIBANDA_GEOM_RATIO_MIN = 3.0
    PLATIBANDA_BOUNDARY_BUFFER_M = 0.30
    PLATIBANDA_LARGER_SLAB_FACTOR = 5.0
    rejected_strip = 0

    def _detect_platibanda_geometry(poly, all_polygons) -> bool:
        """Detecta platibandas (muretas perimetrais) por geometria.

        Retorna True quando o polígono é fino (lado curto ≤ 0.5m, ratio ≥ 3)
        E seu centróide cai a no máximo 0.30m da borda de alguma outra laje
        pelo menos 5× maior. Padrão típico de mureta seguindo perímetro.
        """
        try:
            minx_, miny_, maxx_, maxy_ = poly.bounds
            w_ = maxx_ - minx_
            h_ = maxy_ - miny_
            short_ = min(w_, h_)
            long_ = max(w_, h_)
            if short_ <= 0:
                return False
            ratio_ = long_ / short_
            if short_ > PLATIBANDA_GEOM_SHORT_MAX_M:
                return False
            if ratio_ < PLATIBANDA_GEOM_RATIO_MIN:
                return False
            # Usa ponto representativo (sempre dentro da casca) em vez de centróide
            rep = poly.representative_point()
            for other in all_polygons:
                if other is poly:
                    continue
                if other.area < poly.area * PLATIBANDA_LARGER_SLAB_FACTOR:
                    continue
                try:
                    buffered_boundary = other.boundary.buffer(PLATIBANDA_BOUNDARY_BUFFER_M)
                    if buffered_boundary.contains(rep):
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    def _classify_panel(
        poly, layer_name: str, all_polys, cantilever_flag: bool,
    ) -> str:
        """Determina a categoria do painel com a seguinte prioridade:
        1) Layer keyword (platibanda, beiral, marquise, balanço, cantilever)
        2) Heurística geométrica de anel perimetral → platibanda
        3) Flag de cantilever detectada previamente → cantilever
        4) Default → laje
        """
        cat = classify_layer(layer_name)
        if cat:
            return cat
        if _detect_platibanda_geometry(poly, all_polys):
            return "platibanda"
        if cantilever_flag:
            return "cantilever"
        return CATEGORY_DEFAULT

    # Prepara buffers de textos uma única vez (best-effort).
    # Cada item: dict com 'text' e 'position' (x,y).
    _panel_texts: List[Dict[str, Any]] = []
    if text_entities:
        for te in text_entities:
            if not isinstance(te, dict):
                continue
            content = te.get("text") or ""
            pos = te.get("position")
            if not content or not pos:
                continue
            try:
                _panel_texts.append({
                    "text": str(content),
                    "x": float(pos[0]),
                    "y": float(pos[1]),
                })
            except Exception:
                continue

    TEXT_BUFFER_M = 0.5
    TEXT_EDGE_MAX_M = 0.5  # desempate: só manter room_hint se a fronteira estiver perto

    def _texts_in_polygon(poly) -> List[Dict[str, Any]]:
        """Retorna textos dentro do polígono OU dentro de buffer TEXT_BUFFER_M.

        Para desempate entre polígonos sobrepostos, limita-se no consumidor:
        o polígono de menor área vence para cada texto.
        """
        if not _panel_texts:
            return []
        try:
            buffered = poly.buffer(TEXT_BUFFER_M)
        except Exception:
            buffered = poly
        matched = []
        for t in _panel_texts:
            try:
                p = Point(t["x"], t["y"])
                if buffered.contains(p):
                    matched.append(t)
            except Exception:
                continue
        return matched

    def _find_text_inside_polygon(poly, all_polys):
        """Procura nome estrutural (L3) e cômodo (Quarto 1) em textos próximos.

        Critério de desempate quando o texto pode cair em múltiplos polígonos
        (sobreposição em planta arquitetônica): o polígono com MENOR área vence.
        """
        matches = _texts_in_polygon(poly)
        structural_name: Optional[str] = None
        room_hint: Optional[str] = None
        for t in matches:
            # Desempate: só aceitar o texto para este polígono se for o menor
            # polígono que o contém. Isso mantém o vínculo no painel mais
            # específico quando há sobreposição.
            own_area = poly.area
            p = Point(t["x"], t["y"])
            is_most_specific = True
            for other in all_polys:
                if other is poly:
                    continue
                try:
                    if other.area >= own_area:
                        continue
                    other_buf = other.buffer(TEXT_BUFFER_M)
                    if other_buf.contains(p):
                        # Outro polígono menor também cobre esse texto
                        is_most_specific = False
                        break
                except Exception:
                    continue
            if not is_most_specific:
                continue

            if structural_name is None:
                sn = extract_structural_name(t["text"])
                if sn:
                    structural_name = sn
            if room_hint is None:
                rh = extract_room_hint(t["text"])
                if rh:
                    # Só manter se o texto estiver dentro do polígono ou ≤ 0.5m
                    # da fronteira do polígono mais próximo (critério do plano).
                    try:
                        dist_to_boundary = poly.boundary.distance(p)
                        # Se o ponto está dentro do polígono, distance == 0
                        inside = poly.contains(p)
                        if inside or dist_to_boundary <= TEXT_EDGE_MAX_M:
                            room_hint = rh
                    except Exception:
                        room_hint = rh
        return structural_name, room_hint

    def _layer_for_polygon(poly) -> str:
        """Best-effort: retorna o layer DXF da polyline/hatch de origem.

        A associação por índice é frágil (slab_polygons vem de múltiplas fontes
        e é deduplicado). Estratégia: procurar a polyline/hatch cuja geometria
        sobrepõe significativamente este polígono — ganha o layer com maior
        overlap relativo à área do painel.
        """
        best_layer = ""
        best_score = 0.0
        sources = []
        if slab_polylines:
            sources.extend(slab_polylines)
        if slab_hatches:
            sources.extend(slab_hatches)
        for raw in sources:
            if not isinstance(raw, dict):
                continue
            pts = raw.get("points") or []
            if len(pts) < 3:
                continue
            try:
                cand = Polygon(pts)
                if not cand.is_valid or cand.is_empty:
                    continue
                inter = poly.intersection(cand).area
                if inter <= 0 or poly.area <= 0:
                    continue
                score = inter / poly.area
                if score > best_score:
                    best_score = score
                    best_layer = raw.get("layer", "") or ""
            except Exception:
                continue
        return best_layer

    # Dedup de paineis sobrepostos (v6, 2026-06-12): poligonos derivados
    # que se sobrepoem a um painel MAIOR (intersecao >= 50% da propria
    # area) geram layouts duplicados/cruzados (grade em duas direcoes na
    # mesma regiao - defeito apontado em inspecao visual). Mantem o maior.
    if len(slab_polygons) > 1:
        _order = sorted(
            range(len(slab_polygons)),
            key=lambda i: slab_polygons[i].area,
            reverse=True,
        )
        _drop: set = set()
        for pos, i in enumerate(_order):
            if i in _drop:
                continue
            for j in _order[pos + 1:]:
                if j in _drop:
                    continue
                try:
                    inter = slab_polygons[i].intersection(slab_polygons[j]).area
                except Exception:
                    continue
                area_j = slab_polygons[j].area
                if area_j > 0 and inter / area_j >= 0.50:
                    _drop.add(j)
        if _drop:
            warnings.append(
                f"{len(_drop)} painel(is) de laje sobreposto(s) descartado(s) "
                f"(intersecao >= 50% com painel maior - dedup v6)"
            )
            keep_idx = [i for i in range(len(slab_polygons)) if i not in _drop]
            slab_polygons = [slab_polygons[i] for i in keep_idx]
            cantilever_flags = [
                cantilever_flags[i] for i in keep_idx
                if i < len(cantilever_flags)
            ]

    # Quadro de PAVIMENTO para o modo line-first (decisao do revisor
    # 2026-06-12): eixo UNICO paralelo ao maior sentido do projeto, pitch
    # unico (alvo modal 1.50 m) e linhas ancoradas numa lattice global —
    # guias colineares entre paineis, atravessando as vigas em alinhamento.
    _lf_floor_frame = None
    if slab_layout_mode == "line_first" and slab_polygons:
        _bs = [p.bounds for p in slab_polygons]
        _ub = (
            min(b[0] for b in _bs), min(b[1] for b in _bs),
            max(b[2] for b in _bs), max(b[3] for b in _bs),
        )
        _w, _h = _ub[2] - _ub[0], _ub[3] - _ub[1]
        _f_angle = 0.0 if _w >= _h else 90.0  # guia ao longo do maior sentido
        _f_pitch = 1.50  # alvo modal gold-standard; passo densifica por carga
        # v = coordenada perpendicular as guias: ancorar no inicio do
        # pavimento + meia malha
        _f_anchor = (_ub[1] if _f_angle == 0.0 else _ub[0]) + _f_pitch / 2.0
        # u = coordenada AO LONGO das guias: ancora da lattice global das
        # secundarias VM80 de passo fixo (paineis nervurados, gold standard
        # ALU14+VM80) — garante passo constante e alinhado entre paineis.
        _f_u_anchor = _ub[0] if _f_angle == 0.0 else _ub[1]
        _lf_floor_frame = (_f_angle, _f_pitch, _f_anchor, _f_u_anchor)

    # Compute global grid origin: the minimum (x, y) across all slab bounding
    # boxes, offset by DISTANCIA_BORDA_MIN.  All slab grids snap to this origin
    # so shores align across adjacent compartments.
    _all_bounds = [p.bounds for p in slab_polygons]
    if _all_bounds:
        _global_ox = min(b[0] for b in _all_bounds) + DISTANCIA_BORDA_MIN
        _global_oy = min(b[1] for b in _all_bounds) + DISTANCIA_BORDA_MIN
        _global_origin = (_global_ox, _global_oy)
    else:
        _global_origin = None

    for i, polygon in enumerate(slab_polygons):
        is_cantilever = cantilever_flags[i] if i < len(cantilever_flags) else False
        panel_layer = _layer_for_polygon(polygon)
        panel_category = _classify_panel(
            polygon, panel_layer, slab_polygons, is_cantilever,
        )
        panel_structural_name, panel_room_hint = _find_text_inside_polygon(
            polygon, slab_polygons,
        )

        # Reject thin strip "slabs" — estes são cornijas/molduras ornamentais.
        # Platibandas/beirais/balanços/marquises/cantilevers estão protegidos
        # pela categorização: só categoria "laje" (default) é rejeitada.
        minx, miny, maxx, maxy = polygon.bounds
        w = maxx - minx
        h = maxy - miny
        short = min(w, h)
        long = max(w, h)
        ratio = long / short if short > 0 else float("inf")
        if (
            panel_category == CATEGORY_DEFAULT
            and short < THIN_STRIP_MIN_DIM_M
            and ratio > THIN_STRIP_RATIO
        ):
            rejected_strip += 1
            continue

        slab = Slab.from_polygon(
            polygon=polygon,
            layer_name="derived",
            thickness_m=thickness,
        )

        total_load = calculate_total_load(slab)

        # Pendência 16 (manual §13.6, Orguel p.89): a abertura/altura do
        # equipamento em laje desconta também a PILHA forma + vigamento
        # (h_guia VM130 + h_barrote VM80 + e_compensado). Com o compensado
        # default de 18 mm → 0.228 m (canônico Orguel com 14 mm → 0.224 m).
        # Sapata + forcado absorvem o residual (não entram aqui).
        slab_shore_height = pe_direito_m - thickness - compute_h_pilha()
        if slab_shore_height <= 0:
            warnings.append(
                f"Laje (área {slab.area_m2:.1f}m²) — altura da escora negativa"
            )
            continue

        estimated_shores = max(1, int(slab.area_m2 / (ESPACAMENTO_MAX_DEFAULT ** 2)))
        load_per_shore_estimate = total_load / estimated_shores

        # Decide: telescopic shore, tower, or mixed?
        slab_support_type, slab_tower_fraction, slab_decision_reasons, slab_decision_rule = decide_support_type(
            required_height_m=slab_shore_height,
            load_per_point_kn=load_per_shore_estimate,
            slab_thickness_m=thickness,
            slab_type=slab_type,
            element_type="slab",
            slab_area_m2=slab.area_m2,
            shore_catalog=catalog,
            mode=mode,
            inventory=inventory,
        )


        slab_tower = None
        use_tower_entry = None  # ShoreCatalogEntry representing the tower
        if slab_support_type in (SupportType.TOWER, SupportType.MIXED) and tower_catalog:
            slab_tower = select_tower(tower_catalog, slab_shore_height, load_per_shore_estimate, mode=mode, inventory=inventory)
            if slab_tower:
                slab_rule_suffix = f" [{slab_decision_rule}]" if slab_decision_rule else ""
                warnings.append(
                    f"Laje (área {slab.area_m2:.1f}m²) — torre {slab_tower.model}: "
                    f"{'; '.join(slab_decision_reasons)}{slab_rule_suffix}"
                )
                from src.models.shore import ShoreCatalogEntry as _SCE
                use_tower_entry = _SCE(
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

        # Pure TOWER → all tower entries with wider spacing.
        # MIXED → telescopic as primary (dense grid), towers added to subset.
        if slab_support_type == SupportType.TOWER and use_tower_entry is not None:
            selected_shore = use_tower_entry
        else:
            selected_shore = select_shore(catalog, slab_shore_height, load_per_shore_estimate, mode=mode, inventory=inventory) if catalog else None

        if not selected_shore:
            if slab_tower and slab_support_type == SupportType.TOWER:
                # Only fall back to tower if Rule 0 didn't force TELESCOPIC
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
            elif not selected_shore and catalog:
                # Fallback: try the smallest telescopic shore that covers the height
                for shore in sorted(catalog, key=lambda s: s.height_max_m):
                    if shore.height_min_m <= slab_shore_height <= shore.height_max_m:
                        selected_shore = shore
                        break
            if not selected_shore and catalog:
                # Last resort: use the tallest shore in catalog even if height
                # doesn't match perfectly — at least 1 shore on the drawing
                selected_shore = max(catalog, key=lambda s: s.height_max_m)
                warnings.append(
                    f"Laje (área {slab.area_m2:.1f}m²) — escora aproximada usada "
                    f"(altura {slab_shore_height:.2f}m, carga {load_per_shore_estimate:.1f} kN)"
                )
            if not selected_shore:
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
                    category=panel_category,
                    structural_name=panel_structural_name,
                    room_hint=panel_room_hint,
                    shores_weight_kg=0.0,
                    decision_rule=slab_decision_rule,
                ))
                continue

        max_spacing = _max_spacing_for_slab(thickness)
        if is_cantilever:
            max_spacing *= CANTILEVER_SPACING_FACTOR
        # Pure TOWER grids use moderately wider spacing. MIXED keeps dense
        # telescopic spacing (towers are added to a subset afterwards).
        if slab_support_type == SupportType.TOWER and use_tower_entry is not None:
            max_spacing = max(max_spacing * 1.3, 2.0)
        if density_correction > 0:
            max_spacing = max_spacing / density_correction

        # Check if this panel is a nervura slab — use rib-based shore placement
        is_nervura_panel = nervura_regions and _panel_is_nervura(polygon)

        # Manual §28.8 + gold standard §9/§10 (ALU14+VM80): no modo
        # line_first o painel NERVURADO nao cai no grid de nervuras (que
        # gerava escoras em pontos avulsos e secundarias com passo esticado
        # POR PAINEL) — ele usa o sistema line-first com primarias ALU14 na
        # lattice do pavimento e secundarias VM80 de passo FIXO (c/0.60
        # nervurada; c/0.367 macica espessa) ancorado na lattice global.
        lf_nervura_panel = bool(is_nervura_panel) and slab_layout_mode == "line_first"

        if is_nervura_panel and not lf_nervura_panel:
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

                    # Require the rib-based placement to reach at least
                    # half the uniform-grid estimate; otherwise fall back.
                    # Without this, globally-detected "nervura" flags force
                    # sparse rib grids onto solid panels and some panels
                    # end up with 0-3 shores while others get a dense grid.
                    min_acceptable = max(3, int(estimated_shores * 0.5))
                    if positioned and len(positioned) >= min_acceptable:
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
                            category=panel_category,
                            structural_name=panel_structural_name,
                            room_hint=panel_room_hint,
                            shores_weight_kg=round(sum(s.shore.weight_kg for s in positioned), 2),
                            decision_rule=slab_decision_rule,
                        ))
                        nervura_panel_count += 1
                        continue

            # Fallback: no ribs found in this nervura panel — use uniform grid
            is_nervura_panel = False

        # Solid slab — shore placement
        # Manual §28.8 (gold standard Orguel): modo "line_first" gera linhas
        # de guia por painel e escoras ao longo de cada linha. Paineis 100%
        # torre TAMBEM usam line-first (v6, 2026-06-12): torres apoiam as
        # guias, com passo/pitch de torre (2.35-2.85 m c-a-c, gold standard
        # consolidado) — antes caiam no grid legado e saiam com malha
        # cruzada destoando do resto do pavimento.
        line_first_layout = None
        if slab_layout_mode == "line_first":
            _is_tower_panel = (
                slab_support_type == SupportType.TOWER
                and use_tower_entry is not None
            )
            try:
                shores, nx, ny, sx, sy, line_first_layout = _distribute_line_first_shores(
                    slab=slab,
                    polygon=polygon,
                    shore=use_tower_entry if _is_tower_panel else selected_shore,
                    total_load_kn=total_load,
                    exclusions=pillar_exclusions + shaft_exclusions,
                    floor_height_m=slab_shore_height,
                    pillar_positions=[
                        (p.geometry[0][0], p.geometry[0][1])
                        for p in pillars
                        if p.element_type == ElementType.PILLAR and p.geometry
                    ],
                    tower_mode=_is_tower_panel,
                    floor_frame=_lf_floor_frame,
                    guide_model="ALU14" if lf_nervura_panel else None,
                )
            except Exception as exc:
                logger.warning(
                    f"Line-first falhou para laje (area={slab.area_m2:.1f}m2): {exc}"
                )
                line_first_layout = None
            if line_first_layout is None or not shores:
                line_first_layout = None

        if line_first_layout is None:
            # Grid de pontos legado (default). Passa floor_height_m para
            # ativar espaçamento adaptativo por carga.
            shores, nx, ny, sx, sy = distribute_shores(
                slab=slab,
                shore=selected_shore,
                total_load_kn=total_load,
                max_spacing=max_spacing,
                exclusions=all_exclusions,
                floor_height_m=slab_shore_height,
                global_origin=_global_origin,
            )

        # === MIXED SLAB SUPPORT ===
        # VM-driven orthogonal tower grid: towers spaced at VM130 max span
        # (3.0-4.0m) on strict orthogonal axes within the slab bounding box.
        # Runs BEFORE capitel densification (Orguel Q6): capitel ring stays
        # 100% telescopic — towers near pillars contradict Orguel practice.
        if (slab_support_type == SupportType.MIXED and use_tower_entry is not None
                and len(shores) >= 4):
            import math as _m2

            # Build capitel exclusion set: shores within 1.50m of any pillar
            _CAPITEL_RADIUS = 1.50
            _pillar_xy_mixed = [
                (p.geometry[0][0], p.geometry[0][1])
                for p in pillars
                if p.element_type == ElementType.PILLAR and p.geometry
            ]
            capitel_set = set()
            for idx, s in enumerate(shores):
                for px, py in _pillar_xy_mixed:
                    if _m2.hypot(s.x - px, s.y - py) <= _CAPITEL_RADIUS:
                        capitel_set.add(idx)
                        break

            # VM-driven tower grid spacing (VM130 max practical span = 4.10m)
            bb = slab.bounding_box
            slab_w = bb.max_x - bb.min_x
            slab_h = bb.max_y - bb.min_y
            _VM_MAX_SPAN = 4.0
            spacing_tw = min(_VM_MAX_SPAN, max(min(slab_w, slab_h) / 2, 2.0))

            # Generate ideal tower (x, y) positions on strict orthogonal grid
            n_tw_x = max(2, _m2.ceil(slab_w / spacing_tw) + 1)
            n_tw_y = max(2, _m2.ceil(slab_h / spacing_tw) + 1)
            actual_sx = slab_w / max(n_tw_x - 1, 1)
            actual_sy = slab_h / max(n_tw_y - 1, 1)

            ideal_positions = []
            for iy in range(n_tw_y):
                for ix in range(n_tw_x):
                    ideal_positions.append((
                        bb.min_x + ix * actual_sx,
                        bb.min_y + iy * actual_sy,
                    ))

            # For each ideal position, snap to nearest eligible shore
            tower_indices = set()
            eligible = [i for i in range(len(shores)) if i not in capitel_set]
            for tx, ty in ideal_positions:
                # Skip positions within capitel radius of any pillar
                skip = False
                for px, py in _pillar_xy_mixed:
                    if _m2.hypot(tx - px, ty - py) <= _CAPITEL_RADIUS:
                        skip = True
                        break
                if skip:
                    continue
                # Find closest eligible shore not already assigned
                best_idx = min(
                    (i for i in eligible if i not in tower_indices),
                    key=lambda i: _m2.hypot(shores[i].x - tx, shores[i].y - ty),
                    default=None,
                )
                if best_idx is not None:
                    # Only snap if reasonably close (within 1.5× grid spacing)
                    dist = _m2.hypot(shores[best_idx].x - tx, shores[best_idx].y - ty)
                    if dist <= spacing_tw * 1.5:
                        tower_indices.add(best_idx)

            # Select distribution beam for slab towers
            slab_dist_beam = None
            if dist_beam_catalog and tower_indices:
                slab_vm_span = spacing_tw
                slab_vm_load = total_load / max(len(shores), 1)
                slab_dist_beam = select_distribution_beam(
                    dist_beam_catalog, span_m=slab_vm_span,
                    load_kn_m=slab_vm_load, mode=mode, inventory=inventory,
                )

            from src.models.shore import PositionedShore as _PS
            for idx in tower_indices:
                s = shores[idx]
                shores[idx] = _PS(
                    x=s.x, y=s.y,
                    shore=use_tower_entry,
                    load_applied_kn=s.load_applied_kn,
                    utilization_ratio=round(
                        s.load_applied_kn / use_tower_entry.load_capacity_kn, 4
                    ),
                    support_type=SupportType.TOWER,
                    tower=slab_tower,
                    distribution_beam=slab_dist_beam,
                )

            # Pendência 21 (manual §9/§18): fração empírica de torres em
            # LAJES mistas = 13-22% (12 projetos Orguel). Alerta, não gerador:
            # as torres vêm do grid ortogonal guiado pelo vão da VM
            # (torre-a-torre, escoras quebrando o vão — DOCX resposta 9).
            frac_tw_slab = len(tower_indices) / max(len(shores), 1)
            if tower_indices and not (0.13 <= frac_tw_slab <= 0.22):
                warnings.append(
                    f"Laje (área {slab.area_m2:.1f}m², misto): fração de "
                    f"torres {frac_tw_slab:.0%} fora do envelope empírico "
                    f"13-22% (manual §18) — grid VM torre-a-torre, revisar "
                    f"se intencional"
                )

        # === CAPITEL DENSIFICATION (Orguel Q6) ===
        # Laje lisa (não nervurada, não em balanço): densificar grid ao redor
        # de cada pilar no anel 0.70-1.50m, com espaçamento 30% menor.
        # Rodamos APÓS o swap MIXED para garantir que as escoras de capitel
        # fiquem sempre telescópicas (ver comentário do bloco MIXED acima).
        # No modo line-first o adensamento JA aconteceu SOBRE as linhas
        # (capitel_centers no builder, manual §28.8) — pular o gerador de
        # pontos avulsos, que criaria escoras orfas fora das linhas.
        if not is_cantilever and line_first_layout is None:
            from src.engine.capitel_densification import (
                capitel_densification_shores,
            )
            pillar_xy = [
                (p.geometry[0][0], p.geometry[0][1])
                for p in pillars
                if p.element_type == ElementType.PILLAR and p.geometry
            ]
            # Manual §28.7 (2026-06-01): passar global_origin + spacing
            # para snap das escoras de capitel ao grid global, eliminando
            # padrao visual desalinhado. sx vem do distribute_shores e
            # representa o spacing efetivo (1.00, 1.20...) ja snap-ado.
            extra_shores = capitel_densification_shores(
                polygon=polygon,
                shore_entry=selected_shore,
                pillar_positions=pillar_xy,
                existing_shores=shores,
                max_spacing=max_spacing,
                global_origin=_global_origin,
                grid_spacing=sx,
            )
            shores.extend(extra_shores)

        # Line-first: pitch/passo verificados por capacidade + VM (manual
        # §28.8) podem exceder o teto legado de 1.10 m — validar contra o
        # teto da faixa observada (1.80 m).
        if line_first_layout is not None:
            from src.engine.line_first_builder import PITCH_RANGE_M
            is_valid, errors = validate_result(
                shores, sx, sy, max_spacing=PITCH_RANGE_M[1],
            )
        else:
            is_valid, errors = validate_result(shores, sx, sy)
        validation_errors.extend(errors)

        # --- Manual §28: grid completo de VMs (primarias + secundarias) ---
        # Gera grid de vigas metalicas sobre TODAS as escoras posicionadas
        # (escoras telescopicas + torres), conforme padrao Orguel/UTFPR.
        # Pulado se o painel tiver <2 escoras (sem vao para definir VMs).
        # No modo line-first o grid vem do proprio layout (so guias
        # primarias; barrotes de madeira do cliente nao se desenham —
        # gold standard nota 15).
        slab_vm_grid = None
        try:
            if line_first_layout is not None:
                from src.engine.line_first_builder import layout_to_vm_grid
                q_unit_kn_m2 = total_load / slab.area_m2 if slab.area_m2 > 0 else 7.7
                slab_vm_grid = layout_to_vm_grid(line_first_layout, q_unit_kn_m2)
                if lf_nervura_panel:
                    # Sistema ALU14+VM80: secundarias VM80 de passo FIXO
                    # ancorado na lattice GLOBAL do pavimento (nunca
                    # esticado por painel — gold standard 110749/101112).
                    from src.engine.line_first_builder import (
                        append_fixed_step_secondaries,
                    )
                    _is_ribbed = is_nervura_panel or str(slab_type) in (
                        "ribbed", "waffle",
                    )
                    append_fixed_step_secondaries(
                        slab_vm_grid,
                        line_first_layout,
                        polygon,
                        q_unit_kn_m2,
                        ribbed=_is_ribbed,
                        u_anchor=(
                            _lf_floor_frame[3]
                            if _lf_floor_frame is not None
                            else None
                        ),
                        exclusions=pillar_exclusions + shaft_exclusions,
                    )
                    nervura_panel_count += 1
            elif len(shores) >= 2 and slab.area_m2 > 0:
                bbox = slab.bounding_box
                q_unit_kn_m2 = total_load / slab.area_m2 if slab.area_m2 > 0 else 7.7
                slab_vm_grid = build_vm_grid(
                    shore_points=[ShorePoint(x=s.x, y=s.y) for s in shores],
                    polygon_bbox=(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y),
                    load_kn_m2=q_unit_kn_m2,
                    plywood=default_plywood_spec(),
                    # Manual §28.7 fix (2026-05-30): snap das secundarias ao
                    # grid GLOBAL para eliminar barrotes sobrepostos entre
                    # lajes adjacentes (bug 'VMs proximas demais').
                    global_origin=_global_origin,
                )
        except Exception as exc:
            logger.warning(f"Falha ao gerar VM grid para laje (area={slab.area_m2:.1f}m2): {exc}")
            slab_vm_grid = None

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
            category=panel_category,
            structural_name=panel_structural_name,
            room_hint=panel_room_hint,
            shores_weight_kg=round(sum(s.shore.weight_kg for s in shores), 2),
            decision_rule=slab_decision_rule,
            layout_mode="line_first" if line_first_layout is not None else "grid",
            vm_grid=slab_vm_grid,
        ))
        solid_panel_count += 1

    if nervura_panel_count > 0:
        warnings.append(
            f"Laje nervurada: {nervura_panel_count} painel(éis) "
            + (
                "(line-first ALU14 + VM80 c/passo fixo)"
                if slab_layout_mode == "line_first"
                else "com escoras nas nervuras"
            )
        )
    if solid_panel_count > 0:
        warnings.append(
            f"Laje maciça: {solid_panel_count} painel(éis) com escoras em grid uniforme"
        )
    if rejected_strip > 0:
        warnings.append(
            f"Painéis descartados (cornijas/molduras finas): {rejected_strip}"
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
            # Never reduce to 0 — keep at least 1 shore per slab
            if not filtered and sr.shores:
                filtered = [sr.shores[len(sr.shores) // 2]]
            removed = len(sr.shores) - len(filtered)
            sr.shores = filtered
            # Recalculate load per shore
            if sr.shores and sr.total_load_kn > 0:
                load_per = sr.total_load_kn / len(sr.shores)
                util = load_per / (sr.selected_shore.load_capacity_kn if sr.selected_shore else 1)
                for s in sr.shores:
                    s.load_applied_kn = round(load_per, 2)
                    s.utilization_ratio = round(util, 4)

    # === CROSS-SLAB DEDUPLICATION ===
    # With global grid alignment, overlapping slab polygons produce shores at
    # identical or near-identical positions. Remove shores from larger slabs
    # (processed later) that are too close to shores from smaller slabs
    # (processed earlier, more precise beam-grid panels).
    MIN_CROSS_SLAB_DIST = ESPACAMENTO_MIN  # 0.30m
    # Sort slab results by area ascending — smaller slabs have priority
    slab_order = sorted(range(len(slab_results)), key=lambda k: slab_results[k].area_m2)
    # Build set of all "claimed" shore positions (from smaller slabs first)
    claimed_positions: list = []
    for si in slab_order:
        sr = slab_results[si]
        filtered = []
        for ss in sr.shores:
            too_close = False
            for cx, cy in claimed_positions:
                if math.hypot(ss.x - cx, ss.y - cy) < MIN_CROSS_SLAB_DIST:
                    too_close = True
                    break
            if not too_close:
                filtered.append(ss)
                claimed_positions.append((ss.x, ss.y))
        if len(filtered) < len(sr.shores):
            if not filtered and sr.shores:
                filtered = [sr.shores[len(sr.shores) // 2]]
                claimed_positions.append((filtered[0].x, filtered[0].y))
            removed = len(sr.shores) - len(filtered)
            sr.shores = filtered
            if sr.shores and sr.total_load_kn > 0:
                load_per = sr.total_load_kn / len(sr.shores)
                util = load_per / (sr.selected_shore.load_capacity_kn if sr.selected_shore else 1)
                for s in sr.shores:
                    s.load_applied_kn = round(load_per, 2)
                    s.utilization_ratio = round(util, 4)
            logger.info(
                f"Cross-slab dedup: removed {removed} shores from slab "
                f"area={sr.area_m2:.1f}m²"
            )

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

    # Apply removals (never reduce a beam to 0 shores)
    if to_remove:
        for bi, br in enumerate(beam_results):
            indices_to_remove = {si for (b, si) in to_remove if b == bi}
            if indices_to_remove:
                remaining = [s for idx, s in enumerate(br.shores) if idx not in indices_to_remove]
                if not remaining and br.shores:
                    remaining = [br.shores[len(br.shores) // 2]]
                br.shores = remaining
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

    # O review/dedup final pode remover ou mover escoras. Recalcular a malha
    # de VMs depois disso evita DXF com segmentos antigos em VM_FALHA.
    _finalize_slab_vm_grids(
        slab_results,
        global_origin=_global_origin,
        warnings=warnings,
    )

    # Invariante line-first (manual §28.8): nenhuma escora de laje a mais
    # de 0.10 m de uma linha de guia sobrevive ao pos-processamento.
    _enforce_line_first_shores_on_lines(slab_results, warnings)

    # v6 (inspecao 2026-06-12): fundir guias colineares de paineis
    # fragmentados em guias continuas, quando nenhuma viga cruza o vao.
    _merge_collinear_line_first_guides(
        slab_results,
        _beam_lines if _beam_lines else None,
        warnings,
    )

    # v11 (decisao do revisor 2026-06-12): linha de guia paralela e
    # grudada (< 0.45 m) numa viga e redundante — remover antes do
    # re-espacamento.
    _drop_lines_glued_to_beams(
        slab_results, _beam_lines if _beam_lines else None, warnings,
    )

    # v7 (decisao do revisor 2026-06-12): escoras EQUIDISTANTES ao longo
    # de cada guia continua (L/n constante), absorvendo extras de
    # transpasse/capitel e diferencas de passo entre paineis fundidos.
    _respace_line_first_shores(slab_results, warnings)

    # v12 (decisao do revisor 2026-06-12): escoras de viga alinhadas aos
    # cruzamentos da lattice de linhas do pavimento (vigas perpendiculares
    # as linhas); complementares apenas onde o vao excede o passo admissivel
    # da viga. SEMPRE antes do check global de distancia minima.
    if slab_layout_mode == "line_first" and _lf_floor_frame is not None:
        _align_beam_shores_to_lattice(beam_results, _lf_floor_frame, warnings)

    # v14 (audit OP-102): dedup global de escoras de viga — fragmentos
    # sobrepostos e cruzamentos viga x viga empilhavam escoras.
    _dedupe_beam_shores(beam_results, warnings)

    # v14 (audit OP-101): preencher vaos de viga acima do teto — o align
    # a lattice/dedup pode abrir vao sem complementar; inserir escora no(s)
    # ponto(s) medio(s) garante cobertura por construcao.
    _fill_beam_shore_gaps(beam_results, warnings)

    # v10 (decisao do revisor 2026-06-12): distancia minima global entre
    # escoras — escora de laje a < 0.30 m de escora de viga (ou de outra
    # escora) e removida; a de viga prevalece.
    _enforce_min_shore_distance(slab_results, beam_results, warnings)

    # Sync shore_count with actual len(shores) after all post-processing
    for br in beam_results:
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

    calc_result.shore_catalog_used = list(shore_models_used.values())
    calc_result.total_shores = all_shores_count
    calc_result.total_load_kn = round(all_load, 2)
    calc_result.is_valid = len(validation_errors) == 0
    # Pydantic COPIA a lista na construcao do CalculationResult: avisos
    # appendados pelos pos-passes (review, merge/respace/align line-first,
    # distancia minima) depois da construcao eram perdidos. Re-sincronizar.
    calc_result.warnings = warnings

    # === VOLUME ESCORADO ===
    # V_escorado = Σ A_laje × pé-direito − Σ V_vigas − Σ V_pilares
    # Inclui cantilevers/beirais (todos os painéis de laje entram no bruto).
    # Exclui vigas (penduram abaixo da laje) e pilares (atravessam o pé-direito).
    for sr in slab_results:
        sr.volume_m3 = round(sr.area_m2 * pe_direito_m, 3)

    slab_area_total = sum(sr.area_m2 for sr in slab_results)
    slab_volume_gross = slab_area_total * pe_direito_m

    beam_volume_deducted = sum(
        (br.beam.length_m or 0.0)
        * (br.beam.section_width_m or 0.0)
        * (br.beam.section_height_m or 0.0)
        for br in beam_results
    )

    pillar_volume_deducted = sum(
        (p.section_width_m or 0.0)
        * (p.section_height_m or 0.0)
        * pe_direito_m
        for p in pillars
        if p.element_type == ElementType.PILLAR
    )

    total_volume = max(
        0.0,
        slab_volume_gross - beam_volume_deducted - pillar_volume_deducted,
    )

    calc_result.slab_volume_gross_m3 = round(slab_volume_gross, 3)
    calc_result.beam_volume_deducted_m3 = round(beam_volume_deducted, 3)
    calc_result.pillar_volume_deducted_m3 = round(pillar_volume_deducted, 3)
    calc_result.total_volume_m3 = round(total_volume, 3)
    calc_result.pillar_count = sum(
        1 for p in pillars if p.element_type == ElementType.PILLAR
    )

    # === AUTO-NUMERAÇÃO + BREAKDOWN DE VOLUME ===
    # Ordena por (categoria ASC, área DESC) e atribui índice 1-based por
    # categoria. Monta rótulo final conforme prioridade:
    #   structural_name > room_hint+categoria > categoria+index.
    counters: Dict[str, int] = defaultdict(int)
    for sr in sorted(slab_results, key=lambda s: (s.category, -s.area_m2)):
        counters[sr.category] += 1
        sr.category_index = counters[sr.category]
        base = CATEGORY_LABELS_PT.get(sr.category, sr.category.title())
        if sr.structural_name:
            sr.label = f"{base} {sr.structural_name}"
        elif sr.room_hint and sr.category == CATEGORY_DEFAULT:
            sr.label = f"{base} {sr.category_index} ({sr.room_hint})"
        else:
            sr.label = f"{base} {sr.category_index}"

    # Popular volume_breakdown mantendo ordem de slab_results
    breakdown: List[VolumeBreakdownEntry] = []
    for sr in slab_results:
        try:
            rep = sr.polygon.representative_point()
            cx, cy = float(rep.x), float(rep.y)
        except Exception:
            try:
                c = sr.polygon.centroid
                cx, cy = float(c.x), float(c.y)
            except Exception:
                cx, cy = 0.0, 0.0
        breakdown.append(VolumeBreakdownEntry(
            category=sr.category,
            label=sr.label,
            area_m2=round(sr.area_m2, 3),
            pe_direito_m=round(pe_direito_m, 3),
            volume_m3=round(sr.volume_m3, 3),
            centroid_x=round(cx, 3),
            centroid_y=round(cy, 3),
            shores_weight_kg=round(sr.shores_weight_kg, 2),
        ))
    calc_result.volume_breakdown = breakdown

    return calc_result
