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
from typing import List, Optional, Set, Tuple

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

# Load-aware thinning: if two shores within the same element are closer than
# this distance, try to remove one. The removal is only applied when the
# remaining shores can still carry the element's load with the NBR 15696
# safety factor against the derated capacity at the actual shore height.
REDUNDANCY_DIST_M = 0.80
from src.engine.tower_selector import SHORE_SAFETY_FACTOR


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

    # === PASS 3b: Load-aware thinning of redundant close shores ===
    corrections.extend(_thin_redundant_shores(calc.beam_results, calc.slab_results))

    # === PASS 4: Remove slab shores outside polygon ===
    corrections.extend(_fix_outside_polygon(calc.slab_results))

    # === FINAL SAFETY NET: never output 0 shores for any element ===
    corrections.extend(_ensure_minimum_shores(calc.beam_results, calc.slab_results))

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
        # Never reduce to 0 — a beam always needs at least 1 shore
        if not filtered and br.shores:
            filtered = [br.shores[len(br.shores) // 2]]
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
        # Never reduce to 0 — a slab always needs at least 1 shore
        if not filtered and sr.shores:
            filtered = [sr.shores[len(sr.shores) // 2]]
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
        # Never reduce to 0 — a slab always needs at least 1 shore
        if not filtered and sr.shores:
            filtered = [sr.shores[len(sr.shores) // 2]]
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

    # Apply removals to beam results (never reduce to 0)
    beam_removals = 0
    for bi, br in enumerate(beam_results):
        indices = {s for (t, r, s) in to_remove if t == "beam" and r == bi}
        if indices:
            remaining = [s for idx, s in enumerate(br.shores) if idx not in indices]
            if not remaining and br.shores:
                remaining = [br.shores[len(br.shores) // 2]]
            beam_removals += len(br.shores) - len(remaining)
            br.shores = remaining
            br.shore_count = len(br.shores)
            _recalc_beam_loads(br)

    # Apply removals to slab results (never reduce below minimum)
    slab_removals = 0
    for si_r, sr in enumerate(slab_results):
        indices = {s for (t, r, s) in to_remove if t == "slab" and r == si_r}
        if indices:
            remaining = [s for idx, s in enumerate(sr.shores) if idx not in indices]
            # Minimum 1 shore per 20m² (at least 1 always)
            min_shores = max(1, math.ceil(sr.area_m2 / 20.0))
            if len(remaining) < min_shores and sr.shores:
                # Keep the min_shores with highest load
                sorted_shores = sorted(sr.shores, key=lambda s: s.load_applied_kn, reverse=True)
                remaining = sorted_shores[:min_shores]
            slab_removals += len(sr.shores) - len(remaining)
            sr.shores = remaining
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


def _thin_redundant_shores(
    beam_results: List[BeamShoringResult],
    slab_results: List[SlabShoringResult],
) -> List[str]:
    """Remove shores that are too close to a neighbor when physics allows it.

    For each element (beam or slab), finds pairs of shores closer than
    REDUNDANCY_DIST_M. For each such pair, tentatively removes the one whose
    removal leaves the biggest safety margin (i.e. the one closest to its
    sibling on both sides, or the one with lower contribution). The removal
    is only kept if the remaining shores can still carry the element's total
    load with the derated capacity × SAFETY_FACTOR.

    Iterates until no more removals are possible.
    """
    corrections: List[str] = []

    # --- Beams ---
    for br in beam_results:
        if len(br.shores) < 2 or br.selected_shore is None:
            continue
        beam_length = br.beam.length_m or 1.0
        total_load = br.total_linear_load_kn_m * beam_length
        eff_cap = br.selected_shore.effective_capacity(br.shore_height_m)
        if eff_cap <= 0:
            continue

        removed = 0
        while True:
            if len(br.shores) <= 1:
                break
            # Minimum shores needed physically (never 0)
            required_n = max(1, math.ceil(total_load * SHORE_SAFETY_FACTOR / eff_cap))
            if len(br.shores) <= required_n:
                break
            # Find the tightest pair
            idx_to_remove = _find_closest_redundant(
                [(s.x, s.y) for s in br.shores], REDUNDANCY_DIST_M
            )
            if idx_to_remove is None:
                break
            # Verify that after removal we still satisfy capacity
            if len(br.shores) - 1 < required_n:
                break
            br.shores.pop(idx_to_remove)
            removed += 1
        if removed > 0:
            br.shore_count = len(br.shores)
            _recalc_beam_loads(br)
            name = br.beam.name or "sem nome"
            corrections.append(
                f"Revisão: removidas {removed} escora(s) redundantes da viga "
                f"{name} (carga recalculada cabe nas escoras restantes)"
            )

    # --- Slabs ---
    for i, sr in enumerate(slab_results):
        if len(sr.shores) < 2 or sr.selected_shore is None:
            continue
        # Slab shores sit at (pe_direito - thickness); the PositionedShore
        # records load but not height, so use the selected shore model's
        # static height bracket via height_max as a conservative upper bound.
        # If the shore has a curve, this gives the most-derated capacity.
        shore_height = sr.selected_shore.height_max_m
        eff_cap = sr.selected_shore.effective_capacity(shore_height)
        if eff_cap <= 0:
            continue
        total_load = sr.total_load_kn

        # Minimum 1 shore per 20m² (at least 1 shore always)
        min_shores = max(1, math.ceil(sr.area_m2 / 20.0))

        removed = 0
        while True:
            if len(sr.shores) <= min_shores:
                break
            required_n = math.ceil(total_load * SHORE_SAFETY_FACTOR / eff_cap)
            required_n = max(required_n, min_shores)
            if len(sr.shores) <= required_n:
                break
            idx_to_remove = _find_closest_redundant(
                [(s.x, s.y) for s in sr.shores], REDUNDANCY_DIST_M
            )
            if idx_to_remove is None:
                break
            if len(sr.shores) - 1 < required_n:
                break
            sr.shores.pop(idx_to_remove)
            removed += 1
        if removed > 0:
            _recalc_slab_loads(sr)
            corrections.append(
                f"Revisão: removidas {removed} escora(s) redundantes da laje "
                f"{i+1} (área {sr.area_m2:.1f}m², carga cabe nas restantes)"
            )

    return corrections


def _find_closest_redundant(
    points: List[Tuple[float, float]],
    min_dist_m: float,
) -> Optional[int]:
    """Return the index of a shore that has a neighbor closer than min_dist_m.

    Prefers the shore whose nearest neighbor is the closest overall (i.e. the
    densest spot). Returns None if no pair qualifies.
    """
    best_idx: Optional[int] = None
    best_dist = min_dist_m
    n = len(points)
    for i in range(n):
        xi, yi = points[i]
        for j in range(n):
            if i == j:
                continue
            xj, yj = points[j]
            d = math.hypot(xi - xj, yi - yj)
            if d < best_dist:
                best_dist = d
                best_idx = i
    return best_idx


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
        # Never reduce to 0 — if all are outside, keep centroid shore
        if not filtered and sr.shores:
            centroid = sr.polygon.centroid
            from src.models.shore import PositionedShore as _PS
            # Place a fallback shore at polygon centroid
            best = sr.shores[0]
            filtered = [_PS(
                x=round(centroid.x, 4), y=round(centroid.y, 4),
                shore=best.shore,
                load_applied_kn=best.load_applied_kn,
                utilization_ratio=best.utilization_ratio,
            )]
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


def _ensure_minimum_shores(
    beam_results: List[BeamShoringResult],
    slab_results: List[SlabShoringResult],
) -> List[str]:
    """Final safety net: any element with 0 shores gets a fallback at its centroid."""
    corrections = []

    for br in beam_results:
        if br.shores or br.selected_shore is None:
            continue
        # Place a fallback shore at beam midpoint
        geom = br.beam.geometry
        if geom and len(geom) >= 2:
            mx = (geom[0][0] + geom[-1][0]) / 2
            my = (geom[0][1] + geom[-1][1]) / 2
        else:
            continue
        beam_length = br.beam.length_m or 1.0
        total_load = br.total_linear_load_kn_m * beam_length
        cap = br.selected_shore.load_capacity_kn
        util = min(total_load / cap, 1.0) if cap > 0 else 1.0
        br.shores = [PositionedShore(
            x=round(mx, 4), y=round(my, 4),
            shore=br.selected_shore,
            load_applied_kn=round(total_load, 2),
            utilization_ratio=round(util, 4),
        )]
        br.shore_count = 1
        name = br.beam.name or "sem nome"
        corrections.append(
            f"Revisão: viga {name} ficou com 0 escoras — colocada 1 escora "
            f"de segurança no ponto médio"
        )

    for i, sr in enumerate(slab_results):
        if sr.shores or sr.selected_shore is None:
            continue
        # Place a fallback shore at polygon centroid
        if hasattr(sr, 'polygon') and sr.polygon is not None:
            centroid = sr.polygon.centroid
            cx, cy = centroid.x, centroid.y
        else:
            continue
        total_load = sr.total_load_kn
        cap = sr.selected_shore.load_capacity_kn
        util = min(total_load / cap, 1.0) if cap > 0 else 1.0
        sr.shores = [PositionedShore(
            x=round(cx, 4), y=round(cy, 4),
            shore=sr.selected_shore,
            load_applied_kn=round(total_load, 2),
            utilization_ratio=round(util, 4),
        )]
        corrections.append(
            f"Revisão: laje {i+1} (área {sr.area_m2:.1f}m²) ficou com 0 escoras "
            f"— colocada 1 escora de segurança no centroide"
        )

    return corrections
