"""Post-processing review of shore placement quality.

Catches errors that slip through individual placement logic:
1. Shores too close to each other (overlapping)
2. Shores on top of pillars
3. Shores outside slab polygon boundaries
4. Slab shores on top of beam axes

Applies corrections automatically and logs what was fixed.
"""

import math
import logging
from typing import List, Tuple, Set

from src.models.calculation_models import BeamShoringResult, SlabShoringResult, CalculationResult
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.shore import PositionedShore

logger = logging.getLogger(__name__)

# Minimum distance between any two shores in the entire project (m)
# Ensures shores don't visually overlap in DXF output (marker radius ~0.20m)
# and don't physically conflict on site
MIN_GLOBAL_SHORE_DIST = 0.50

# Minimum distance from shore center to pillar face (m)
# Must match the placement threshold used in beam_calculator.py (DIST_MIN_APOIO)
# and constants.py (DISTANCIA_PILAR_MIN = 0.70m).
# Previously 1.00m — caused shores placed at 0.70-1.00m to be removed here,
# creating gaps near beam-pillar junctions.
from src.utils.constants import DISTANCIA_PILAR_MIN
MIN_PILLAR_FACE_DIST = DISTANCIA_PILAR_MIN

# Minimum distance from slab shore to beam axis (m)
# Beam already has its own shores — slab shore on beam is redundant
MIN_BEAM_AXIS_DIST = 0.30


def review_and_fix(
    calc: CalculationResult,
    pillars: List[ClassifiedElement],
    beams: List[ClassifiedElement],
) -> List[str]:
    """Review all shore positions and fix placement errors.

    Modifies calc in-place (removes invalid shores, recalculates loads).
    Returns list of correction descriptions for warnings.
    """
    corrections: List[str] = []

    # === PASS 1: Remove shores on pillar positions ===
    pillar_info = _extract_pillar_zones(pillars)
    corrections.extend(_fix_pillar_overlaps(calc.beam_results, pillar_info, "viga"))
    corrections.extend(_fix_pillar_overlaps_slab(calc.slab_results, pillar_info))

    # === PASS 2: Remove slab shores too close to beam axes ===
    beam_axes = _extract_beam_axes(beams)
    corrections.extend(_fix_beam_axis_overlaps(calc.slab_results, beam_axes))

    # === PASS 3: Global deduplication — remove overlapping shores ===
    corrections.extend(_fix_global_overlaps(calc.beam_results, calc.slab_results))

    # === PASS 4: Remove slab shores outside polygon ===
    corrections.extend(_fix_outside_polygon(calc.slab_results))

    # Update totals
    calc.total_shores = (
        sum(r.shore_count for r in calc.beam_results)
        + sum(len(r.shores) for r in calc.slab_results)
    )

    if corrections:
        logger.info(f"Shore review: {len(corrections)} corrections applied")

    return corrections


def _extract_pillar_zones(
    pillars: List[ClassifiedElement],
) -> List[Tuple[float, float, float, float]]:
    """Extract pillar zones as (cx, cy, half_w, half_d) tuples."""
    zones = []
    for p in pillars:
        if p.element_type != ElementType.PILLAR or not p.geometry:
            continue
        cx, cy = p.geometry[0]
        hw = (p.section_width_m or 0.20) / 2
        hd = (p.section_height_m or 0.20) / 2
        zones.append((cx, cy, hw, hd))
    return zones


def _dist_to_pillar_face(
    sx: float, sy: float,
    pcx: float, pcy: float, phw: float, phd: float,
) -> float:
    """Distance from shore to nearest pillar face (not center)."""
    dx = max(0.0, abs(sx - pcx) - phw)
    dy = max(0.0, abs(sy - pcy) - phd)
    return math.hypot(dx, dy)


def _fix_pillar_overlaps(
    beam_results: List[BeamShoringResult],
    pillar_zones: List[Tuple[float, float, float, float]],
    element_type: str,
) -> List[str]:
    """Remove beam shores that fall on or too close to pillars."""
    corrections = []
    for br in beam_results:
        before = len(br.shores)
        filtered = []
        for s in br.shores:
            on_pillar = False
            for pcx, pcy, phw, phd in pillar_zones:
                if _dist_to_pillar_face(s.x, s.y, pcx, pcy, phw, phd) < MIN_PILLAR_FACE_DIST:
                    on_pillar = True
                    break
            if not on_pillar:
                filtered.append(s)
        if len(filtered) < before:
            removed = before - len(filtered)
            br.shores = filtered
            br.shore_count = len(filtered)
            _recalc_beam_loads(br)
            name = br.beam.name or "sem nome"
            corrections.append(
                f"Revisão: removidas {removed} escora(s) da viga {name} "
                f"sobrepostas a pilares"
            )
    return corrections


def _fix_pillar_overlaps_slab(
    slab_results: List[SlabShoringResult],
    pillar_zones: List[Tuple[float, float, float, float]],
) -> List[str]:
    """Remove slab shores that fall on or too close to pillars."""
    corrections = []
    for i, sr in enumerate(slab_results):
        before = len(sr.shores)
        filtered = []
        for s in sr.shores:
            on_pillar = False
            for pcx, pcy, phw, phd in pillar_zones:
                if _dist_to_pillar_face(s.x, s.y, pcx, pcy, phw, phd) < MIN_PILLAR_FACE_DIST:
                    on_pillar = True
                    break
            if not on_pillar:
                filtered.append(s)
        if len(filtered) < before:
            removed = before - len(filtered)
            sr.shores = filtered
            _recalc_slab_loads(sr)
            corrections.append(
                f"Revisão: removidas {removed} escora(s) da laje {i+1} "
                f"(área {sr.area_m2:.1f}m²) sobrepostas a pilares"
            )
    return corrections


def _extract_beam_axes(
    beams: List[ClassifiedElement],
) -> List[Tuple[Tuple[float, float], Tuple[float, float], float]]:
    """Extract beam axis lines as ((x1,y1), (x2,y2), width) tuples."""
    axes = []
    for b in beams:
        if b.element_type != ElementType.BEAM or len(b.geometry) < 2:
            continue
        axes.append((b.geometry[0], b.geometry[1], b.section_width_m or 0.14))
    return axes


def _dist_point_to_segment(
    px: float, py: float,
    ax: float, ay: float, bx: float, by: float,
) -> float:
    """Distance from point (px,py) to line segment (ax,ay)-(bx,by)."""
    dx = bx - ax
    dy = by - ay
    len_sq = dx * dx + dy * dy
    if len_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len_sq))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _fix_beam_axis_overlaps(
    slab_results: List[SlabShoringResult],
    beam_axes: List[Tuple[Tuple[float, float], Tuple[float, float], float]],
) -> List[str]:
    """Remove slab shores that sit on top of beam axes."""
    corrections = []
    for i, sr in enumerate(slab_results):
        before = len(sr.shores)
        filtered = []
        for s in sr.shores:
            on_beam = False
            for (ax, ay), (bx, by), bw in beam_axes:
                dist = _dist_point_to_segment(s.x, s.y, ax, ay, bx, by)
                # Shore is on beam if closer than beam half-width + margin
                if dist < (bw / 2) + MIN_BEAM_AXIS_DIST:
                    on_beam = True
                    break
            if not on_beam:
                filtered.append(s)
        if len(filtered) < before:
            removed = before - len(filtered)
            sr.shores = filtered
            _recalc_slab_loads(sr)
            corrections.append(
                f"Revisão: removidas {removed} escora(s) da laje {i+1} "
                f"sobrepostas a eixos de vigas"
            )
    return corrections


def _fix_global_overlaps(
    beam_results: List[BeamShoringResult],
    slab_results: List[SlabShoringResult],
) -> List[str]:
    """Remove shores that are too close to each other globally.

    Builds a spatial index of ALL shores, then for each close pair,
    removes the one with lower structural importance (slab < beam,
    lower load < higher load).
    """
    corrections = []

    # Collect all shore positions with metadata
    # (x, y, source_type, source_idx, shore_idx, load)
    all_shores: List[Tuple[float, float, str, int, int, float]] = []
    for bi, br in enumerate(beam_results):
        for si, s in enumerate(br.shores):
            all_shores.append((s.x, s.y, "beam", bi, si, s.load_applied_kn))
    for si_r, sr in enumerate(slab_results):
        for si, s in enumerate(sr.shores):
            all_shores.append((s.x, s.y, "slab", si_r, si, s.load_applied_kn))

    # Find pairs that are too close
    to_remove: Set[Tuple[str, int, int]] = set()
    for i in range(len(all_shores)):
        x1, y1, t1, r1, s1, l1 = all_shores[i]
        key1 = (t1, r1, s1)
        if key1 in to_remove:
            continue
        for j in range(i + 1, len(all_shores)):
            x2, y2, t2, r2, s2, l2 = all_shores[j]
            key2 = (t2, r2, s2)
            if key2 in to_remove:
                continue
            # Same slab's shores are already handled by grid spacing
            if t1 == "slab" and t2 == "slab" and r1 == r2:
                continue

            dist = math.hypot(x2 - x1, y2 - y1)
            if dist < MIN_GLOBAL_SHORE_DIST:
                # Decide which to remove: prefer removing slab over beam,
                # and lower load over higher load
                if t1 == "beam" and t2 == "slab":
                    to_remove.add(key2)
                elif t1 == "slab" and t2 == "beam":
                    to_remove.add(key1)
                elif l1 >= l2:
                    to_remove.add(key2)
                else:
                    to_remove.add(key1)

    if not to_remove:
        return corrections

    # Apply removals to beam results
    beam_removals = 0
    for bi, br in enumerate(beam_results):
        indices = {s for (t, r, s) in to_remove if t == "beam" and r == bi}
        if indices:
            beam_removals += len(indices)
            br.shores = [s for idx, s in enumerate(br.shores) if idx not in indices]
            br.shore_count = len(br.shores)
            _recalc_beam_loads(br)

    # Apply removals to slab results
    slab_removals = 0
    for si_r, sr in enumerate(slab_results):
        indices = {s for (t, r, s) in to_remove if t == "slab" and r == si_r}
        if indices:
            slab_removals += len(indices)
            sr.shores = [s for idx, s in enumerate(sr.shores) if idx not in indices]
            _recalc_slab_loads(sr)

    if beam_removals > 0:
        corrections.append(
            f"Revisão: removidas {beam_removals} escora(s) de vigas "
            f"sobrepostas a outras escoras (dist < {MIN_GLOBAL_SHORE_DIST}m)"
        )
    if slab_removals > 0:
        corrections.append(
            f"Revisão: removidas {slab_removals} escora(s) de lajes "
            f"sobrepostas a outras escoras (dist < {MIN_GLOBAL_SHORE_DIST}m)"
        )

    return corrections


def _fix_outside_polygon(
    slab_results: List[SlabShoringResult],
) -> List[str]:
    """Remove slab shores that ended up outside their polygon."""
    from shapely.geometry import Point

    corrections = []
    for i, sr in enumerate(slab_results):
        if not hasattr(sr, 'polygon') or sr.polygon is None:
            continue
        before = len(sr.shores)
        filtered = []
        for s in sr.shores:
            if sr.polygon.contains(Point(s.x, s.y)):
                filtered.append(s)
        if len(filtered) < before:
            removed = before - len(filtered)
            sr.shores = filtered
            _recalc_slab_loads(sr)
            corrections.append(
                f"Revisão: removidas {removed} escora(s) da laje {i+1} "
                f"fora do perímetro do painel"
            )
    return corrections


def _recalc_beam_loads(br: BeamShoringResult) -> None:
    """Recalculate load per shore after removing shores from a beam."""
    if not br.shores:
        return
    beam_length = br.beam.length_m or 1.0
    total_load = br.total_linear_load_kn_m * beam_length
    load_per = total_load / len(br.shores)
    cap = br.selected_shore.load_capacity_kn if br.selected_shore else 1.0
    util = load_per / cap
    for s in br.shores:
        s.load_applied_kn = round(load_per, 2)
        s.utilization_ratio = round(min(util, 1.0), 4)


def _recalc_slab_loads(sr: SlabShoringResult) -> None:
    """Recalculate load per shore after removing shores from a slab."""
    if not sr.shores:
        return
    load_per = sr.total_load_kn / len(sr.shores)
    cap = sr.selected_shore.load_capacity_kn if sr.selected_shore else 1.0
    util = load_per / cap
    for s in sr.shores:
        s.load_applied_kn = round(load_per, 2)
        s.utilization_ratio = round(min(util, 1.0), 4)
