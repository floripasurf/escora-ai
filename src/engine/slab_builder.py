"""Derive slab panels from beam grid via Shapely polygonize.

Algorithm:
1. Convert each beam to a Shapely LineString along its axis
2. Snap beam endpoints to nearby perpendicular beams (bridge pillar gaps)
3. Union all beam lines into a geometry network
4. Use shapely.ops.polygonize() to extract closed regions
5. Each polygon = one slab panel

Also supports direct slab extraction from:
- DXF HATCH entities (boundary polygons)
- Closed LWPOLYLINE/POLYLINE entities
"""

import logging
from typing import List, Tuple, Dict, Any
from shapely.geometry import LineString, Point, MultiPoint
from shapely.ops import polygonize, unary_union, snap
from shapely.geometry.polygon import Polygon
from shapely.validation import make_valid
from src.models.pipeline_models import ClassifiedElement, ElementType

logger = logging.getLogger(__name__)

MIN_SLAB_AREA = 0.5  # m2 -- anything smaller is noise

# Max gap to bridge between beam endpoints and perpendicular beams (pillar width)
# Increased from 0.60m: real pillars are 0.20-1.0m wide, and beams stop at
# pillar faces, leaving gaps of pillar_width + beam_offset ≈ 0.5-1.5m
SNAP_TOLERANCE = 1.20  # m

# Extended tolerance for beam axes — bridges larger gaps across pillars
# Real pillar widths range from 0.20m to 1.0m+, and beams stop at pillar faces
# leaving gaps of pillar_width + 2 * beam_offset ≈ 0.5-2.0m
SNAP_TOLERANCE_AXES = 2.00  # m


def _classify_beam_direction(start: Tuple, end: Tuple) -> str:
    """Return 'H' or 'V' based on major axis."""
    dx = abs(end[0] - start[0])
    dy = abs(end[1] - start[1])
    return "H" if dx >= dy else "V"


def _extend_beams_to_grid(beams: List[ClassifiedElement]) -> List[LineString]:
    """Extend beam endpoints to snap onto perpendicular beams.

    In real DXF files, beams don't touch at intersections — there's a gap
    where the pillar sits. This extends each beam endpoint toward the nearest
    perpendicular beam axis so they form a connected grid for polygonize.
    """
    # Separate into H and V beams with their axis info
    h_beams = []  # (y_axis, x_start, x_end, beam)
    v_beams = []  # (x_axis, y_start, y_end, beam)

    for beam in beams:
        if beam.element_type != ElementType.BEAM or len(beam.geometry) < 2:
            continue
        start, end = beam.geometry[0], beam.geometry[1]
        direction = _classify_beam_direction(start, end)
        if direction == "H":
            y = (start[1] + end[1]) / 2
            x_min = min(start[0], end[0])
            x_max = max(start[0], end[0])
            h_beams.append((y, x_min, x_max, beam))
        else:
            x = (start[0] + end[0]) / 2
            y_min = min(start[1], end[1])
            y_max = max(start[1], end[1])
            v_beams.append((x, y_min, y_max, beam))

    lines = []

    # For each H beam, try to extend start/end to nearest V beam axis
    for y, x_min, x_max, beam in h_beams:
        new_x_min = x_min
        new_x_max = x_max

        # Find closest V beam to the left of x_min
        best_left = None
        for vx, vy_min, vy_max, _ in v_beams:
            if vx >= x_min:
                continue  # not to the left
            if vx < x_min - SNAP_TOLERANCE:
                continue  # too far
            # Check Y overlap: the V beam must span this H beam's Y
            if vy_min <= y + SNAP_TOLERANCE and vy_max >= y - SNAP_TOLERANCE:
                if best_left is None or vx > best_left:
                    best_left = vx
        if best_left is not None:
            new_x_min = best_left

        # Find closest V beam to the right of x_max
        best_right = None
        for vx, vy_min, vy_max, _ in v_beams:
            if vx <= x_max:
                continue
            if vx > x_max + SNAP_TOLERANCE:
                continue
            if vy_min <= y + SNAP_TOLERANCE and vy_max >= y - SNAP_TOLERANCE:
                if best_right is None or vx < best_right:
                    best_right = vx
        if best_right is not None:
            new_x_max = best_right

        lines.append(LineString([(new_x_min, y), (new_x_max, y)]))

    # For each V beam, try to extend start/end to nearest H beam axis
    for x, y_min, y_max, beam in v_beams:
        new_y_min = y_min
        new_y_max = y_max

        # Find closest H beam below y_min
        best_below = None
        for hy, hx_min, hx_max, _ in h_beams:
            if hy >= y_min:
                continue
            if hy < y_min - SNAP_TOLERANCE:
                continue
            if hx_min <= x + SNAP_TOLERANCE and hx_max >= x - SNAP_TOLERANCE:
                if best_below is None or hy > best_below:
                    best_below = hy
        if best_below is not None:
            new_y_min = best_below

        # Find closest H beam above y_max
        best_above = None
        for hy, hx_min, hx_max, _ in h_beams:
            if hy <= y_max:
                continue
            if hy > y_max + SNAP_TOLERANCE:
                continue
            if hx_min <= x + SNAP_TOLERANCE and hx_max >= x - SNAP_TOLERANCE:
                if best_above is None or hy < best_above:
                    best_above = hy
        if best_above is not None:
            new_y_max = best_above

        lines.append(LineString([(x, new_y_min), (x, new_y_max)]))

    return lines


def _extend_axes_to_grid(
    h_axes: List[Tuple[float, float, float]],
    v_axes: List[Tuple[float, float, float]],
    tolerance: float = SNAP_TOLERANCE_AXES,
) -> List[LineString]:
    """Extend beam axis lines to snap onto perpendicular axes.

    Similar to _extend_beams_to_grid but operates on raw beam axes
    (midline between parallel pairs) rather than ClassifiedElement objects.
    Uses a larger tolerance to bridge pillar gaps.

    Args:
        h_axes: List of (y, x_start, x_end) for horizontal beam axes.
        v_axes: List of (x, y_start, y_end) for vertical beam axes.
        tolerance: Maximum gap to bridge between endpoints and perpendicular axes.
    """
    lines = []

    for y, x_min, x_max in h_axes:
        new_x_min = x_min
        new_x_max = x_max

        for vx, vy_min, vy_max in v_axes:
            # Extend left
            if vx < x_min and x_min - vx <= tolerance:
                if vy_min <= y + tolerance and vy_max >= y - tolerance:
                    new_x_min = min(new_x_min, vx)
            # Extend right
            if vx > x_max and vx - x_max <= tolerance:
                if vy_min <= y + tolerance and vy_max >= y - tolerance:
                    new_x_max = max(new_x_max, vx)

        lines.append(LineString([(new_x_min, y), (new_x_max, y)]))

    for x, y_min, y_max in v_axes:
        new_y_min = y_min
        new_y_max = y_max

        for hy, hx_min, hx_max in h_axes:
            # Extend down
            if hy < y_min and y_min - hy <= tolerance:
                if hx_min <= x + tolerance and hx_max >= x - tolerance:
                    new_y_min = min(new_y_min, hy)
            # Extend up
            if hy > y_max and hy - y_max <= tolerance:
                if hx_min <= x + tolerance and hx_max >= x - tolerance:
                    new_y_max = max(new_y_max, hy)

        lines.append(LineString([(x, new_y_min), (x, new_y_max)]))

    return lines


def _close_open_beam_cells(
    lines: List[LineString],
    max_gap: float = 10.0,
    min_gap: float = 0.3,
) -> List[LineString]:
    """Add virtual closure lines for cantilever/edge slab detection.

    In cantilever slabs and building edges, beams form 3 sides of a cell
    but the 4th side is open (no beam). This finds pairs of free endpoints
    (degree-1 nodes) at similar X or Y coordinates and connects them,
    closing the cell so polygonize can extract the slab polygon.

    Args:
        lines: Beam axis LineStrings from _extend_beams_to_grid.
        max_gap: Maximum distance between free endpoints to close (m).
        min_gap: Minimum distance to avoid degenerate closures (m).

    Returns:
        Original lines + virtual closure lines.
    """
    from collections import Counter

    def rnd(pt: Tuple[float, float]) -> Tuple[float, float]:
        return (round(pt[0], 2), round(pt[1], 2))

    # Build node degree map
    node_deg: Counter = Counter()
    for line in lines:
        coords = list(line.coords)
        node_deg[rnd(coords[0])] += 1
        node_deg[rnd(coords[-1])] += 1

    # Free endpoints: exactly 1 line meets here
    free = [pt for pt, deg in node_deg.items() if deg == 1]

    if len(free) < 2:
        return lines

    closure: List[LineString] = []
    used: set = set()

    # --- Horizontal closures: pair free endpoints at similar Y ---
    by_y = sorted(free, key=lambda p: (round(p[1], 1), p[0]))
    for i in range(len(by_y)):
        if by_y[i] in used:
            continue
        # Try to pair with the next endpoint at similar Y
        for j in range(i + 1, len(by_y)):
            if by_y[j] in used:
                continue
            p1, p2 = by_y[i], by_y[j]
            dy = abs(p2[1] - p1[1])
            dx = abs(p2[0] - p1[0])
            if dy > 0.2:
                break  # sorted by Y, no more candidates at this Y level
            if min_gap < dx < max_gap:
                closure.append(LineString([p1, p2]))
                used.add(p1)
                used.add(p2)
                break

    # --- Vertical closures: pair free endpoints at similar X ---
    by_x = sorted(free, key=lambda p: (round(p[0], 1), p[1]))
    for i in range(len(by_x)):
        if by_x[i] in used:
            continue
        for j in range(i + 1, len(by_x)):
            if by_x[j] in used:
                continue
            p1, p2 = by_x[i], by_x[j]
            dx = abs(p2[0] - p1[0])
            dy = abs(p2[1] - p1[1])
            if dx > 0.2:
                break
            if min_gap < dy < max_gap:
                closure.append(LineString([p1, p2]))
                used.add(p1)
                used.add(p2)
                break

    if closure:
        logger.info(
            f"Edge closure: {len(closure)} virtual boundaries "
            f"for cantilever/edge slabs"
        )

    return lines + closure


def derive_slabs_from_beam_pairs(
    beams: List[ClassifiedElement],
    max_span: float = 8.0,
    min_overlap: float = 1.5,
    min_slab_area: float = MIN_SLAB_AREA,
) -> List[Polygon]:
    """Derive slab panels from pairs of adjacent parallel beams.

    Unlike polygonize (which requires fully closed regions), this finds
    slabs between pairs of parallel beams even when the grid is open.
    Handles cantilever slabs, edge slabs, and sparse grids.

    Algorithm:
    1. Sort H beams by Y, V beams by X
    2. For each pair of consecutive parallel beams:
       - Compute X/Y overlap span
       - If gap < max_span and overlap > min_overlap, create slab polygon
    3. Filter by area and deduplicate

    Args:
        beams: Classified beam elements.
        max_span: Maximum gap between parallel beams to form a slab (m).
        min_overlap: Minimum overlap span to be a valid slab (m).
        min_slab_area: Minimum slab area threshold (m²).
    """
    h_beams: List[Tuple[float, float, float]] = []  # (y, x_min, x_max)
    v_beams: List[Tuple[float, float, float]] = []  # (x, y_min, y_max)

    for beam in beams:
        if beam.element_type != ElementType.BEAM or len(beam.geometry) < 2:
            continue
        start, end = beam.geometry[0], beam.geometry[1]
        direction = _classify_beam_direction(start, end)
        if direction == "H":
            y = (start[1] + end[1]) / 2
            x_min = min(start[0], end[0])
            x_max = max(start[0], end[0])
            # Skip very short segments (pillar outlines, not real beams)
            if x_max - x_min < 2.5:
                continue
            h_beams.append((y, x_min, x_max))
        else:
            x = (start[0] + end[0]) / 2
            y_min = min(start[1], end[1])
            y_max = max(start[1], end[1])
            if y_max - y_min < 2.5:
                continue
            v_beams.append((x, y_min, y_max))

    candidates: List[Polygon] = []

    def _has_intermediate_h(y1: float, y2: float, x_lo: float, x_hi: float) -> bool:
        """Check if any H beam lies between y1 and y2 overlapping [x_lo, x_hi]."""
        for ym, xm_min, xm_max in h_beams:
            if ym <= y1 + 0.3 or ym >= y2 - 0.3:
                continue
            # Check X overlap with the slab region
            overlap = min(xm_max, x_hi) - max(xm_min, x_lo)
            if overlap >= min_overlap:
                return True
        return False

    def _has_intermediate_v(x1: float, x2: float, y_lo: float, y_hi: float) -> bool:
        """Check if any V beam lies between x1 and x2 overlapping [y_lo, y_hi]."""
        for xm, ym_min, ym_max in v_beams:
            if xm <= x1 + 0.3 or xm >= x2 - 0.3:
                continue
            overlap = min(ym_max, y_hi) - max(ym_min, y_lo)
            if overlap >= min_overlap:
                return True
        return False

    # --- H beam pairs: slab between two horizontal beams ---
    h_beams.sort(key=lambda b: b[0])  # sort by Y
    for i in range(len(h_beams)):
        y1, x1_min, x1_max = h_beams[i]
        for j in range(i + 1, len(h_beams)):
            y2, x2_min, x2_max = h_beams[j]
            gap = y2 - y1
            if gap < 0.5:
                continue  # same Y level, skip
            if gap > max_span:
                break  # sorted, no more candidates for this beam

            # Compute X overlap
            overlap_min = max(x1_min, x2_min)
            overlap_max = min(x1_max, x2_max)
            overlap = overlap_max - overlap_min
            if overlap < min_overlap:
                continue

            # Skip if an intermediate H beam splits this region
            if _has_intermediate_h(y1, y2, overlap_min, overlap_max):
                continue

            poly = Polygon([
                (overlap_min, y1), (overlap_max, y1),
                (overlap_max, y2), (overlap_min, y2),
            ])
            if poly.area >= min_slab_area:
                candidates.append(poly)

    # --- V beam pairs: slab between two vertical beams ---
    v_beams.sort(key=lambda b: b[0])  # sort by X
    for i in range(len(v_beams)):
        x1, y1_min, y1_max = v_beams[i]
        for j in range(i + 1, len(v_beams)):
            x2, y2_min, y2_max = v_beams[j]
            gap = x2 - x1
            if gap < 0.5:
                continue
            if gap > max_span:
                break

            overlap_min = max(y1_min, y2_min)
            overlap_max = min(y1_max, y2_max)
            overlap = overlap_max - overlap_min
            if overlap < min_overlap:
                continue

            # Skip if an intermediate V beam splits this region
            if _has_intermediate_v(x1, x2, overlap_min, overlap_max):
                continue

            poly = Polygon([
                (x1, overlap_min), (x2, overlap_min),
                (x2, overlap_max), (x1, overlap_max),
            ])
            if poly.area >= min_slab_area:
                candidates.append(poly)

    if not candidates:
        return []

    result = _deduplicate_polygons(candidates)
    if result:
        logger.info(
            f"Beam-pair slabs: {len(result)} panels from "
            f"adjacent parallel beams"
        )
    return result


def derive_slabs_from_beams(beams: List[ClassifiedElement]) -> List[Polygon]:
    """Extract closed slab panels from the beam grid.

    After extending beams to bridge pillar gaps, adds virtual closure
    lines at open edges (cantilever/edge slabs) before polygonizing.
    """
    lines = _extend_beams_to_grid(beams)

    if not lines:
        return []

    # Close open cells for cantilever/edge slabs
    lines = _close_open_beam_cells(lines)

    merged = unary_union(lines)
    polygons = list(polygonize(merged))
    return [p for p in polygons if p.area >= MIN_SLAB_AREA]


def derive_slabs_from_axes(
    h_axes: List[Tuple[float, float, float]],
    v_axes: List[Tuple[float, float, float]],
) -> List[Polygon]:
    """Extract closed slab panels from beam axis lines.

    Uses all beam candidates (not just classified beams) with extended
    snapping tolerance to bridge pillar gaps. This produces slab panels
    even when the classified beam set is too sparse for polygonize.

    Args:
        h_axes: List of (y, x_start, x_end) for horizontal beam axes.
        v_axes: List of (x, y_start, y_end) for vertical beam axes.

    Returns:
        List of Shapely Polygon representing slab panels.
    """
    if not h_axes and not v_axes:
        return []

    lines = _extend_axes_to_grid(h_axes, v_axes)

    if not lines:
        return []

    # Close open cells for cantilever/edge slabs
    lines = _close_open_beam_cells(lines)

    merged = unary_union(lines)
    polygons = list(polygonize(merged))
    return [p for p in polygons if p.area >= MIN_SLAB_AREA]


# Layer name patterns that indicate slab boundaries
_SLAB_LAYER_KEYWORDS = {
    "laje", "lajes", "slab", "forma", "piso", "forro",
}

# Maximum realistic slab area (m²) — filter out full-floor hatches
MAX_SLAB_AREA = 500.0

# Minimum overlap to consider two polygons as duplicates
DEDUP_OVERLAP_RATIO = 0.50


def _is_slab_layer(layer_name: str) -> bool:
    """Check if a layer name suggests slab content."""
    lower = layer_name.lower().strip()
    for kw in _SLAB_LAYER_KEYWORDS:
        if kw in lower:
            return True
    return False


def _points_to_polygon(
    points: List[Tuple[float, float]], scale: float = 1.0,
) -> Polygon | None:
    """Convert a list of points to a valid Shapely Polygon.

    Returns None if the polygon is invalid, too small, or degenerate.
    """
    if len(points) < 3:
        return None

    scaled = [(x * scale, y * scale) for x, y in points]

    # Close the ring if not already closed
    if scaled[0] != scaled[-1]:
        scaled.append(scaled[0])

    try:
        poly = Polygon(scaled)
        if not poly.is_valid:
            poly = make_valid(poly)
        if poly.is_empty or poly.area < MIN_SLAB_AREA:
            return None
        if poly.area > MAX_SLAB_AREA:
            return None
        return poly
    except Exception:
        return None


def _deduplicate_polygons(
    polygons: List[Polygon], overlap_ratio: float = DEDUP_OVERLAP_RATIO,
) -> List[Polygon]:
    """Remove duplicate/overlapping polygons, keeping the larger one."""
    if len(polygons) <= 1:
        return polygons

    # Sort by area descending — keep larger polygons first
    sorted_polys = sorted(polygons, key=lambda p: p.area, reverse=True)
    kept = []

    for poly in sorted_polys:
        is_dup = False
        for existing in kept:
            try:
                intersection = poly.intersection(existing)
                overlap = intersection.area / poly.area if poly.area > 0 else 0
                if overlap >= overlap_ratio:
                    is_dup = True
                    break
            except Exception:
                continue
        if not is_dup:
            kept.append(poly)

    return kept


def derive_slabs_from_boundaries(
    hatches: List[Dict[str, Any]],
    polylines: List[Dict[str, Any]],
    scale: float = 1.0,
) -> List[Polygon]:
    """Extract slab panels directly from DXF HATCH and closed POLYLINE entities.

    This is a direct extraction method that doesn't depend on beam grid
    polygonization. Many DXFs have explicit slab boundaries drawn as:
    - HATCH fills (concrete pattern, solid fill) on slab layers
    - Closed LWPOLYLINE/POLYLINE on LAJE/FORMA/SLAB layers

    Args:
        hatches: List of dicts with keys: points, layer, pattern_name, is_solid, area
        polylines: List of dicts with keys: points, layer, is_closed
        scale: Coordinate scale factor (1.0 for real meters)

    Returns:
        List of Shapely Polygon representing slab panels.
    """
    candidates: List[Polygon] = []

    # Extract from hatches
    for h in hatches:
        layer = h.get("layer", "")
        points = h.get("points", [])
        is_solid = h.get("is_solid", False)
        pattern = h.get("pattern_name", "").upper()

        # Accept hatches on slab layers, or solid/concrete fills anywhere
        is_slab_hatch = (
            _is_slab_layer(layer)
            or is_solid
            or pattern in ("CONCRETE", "ANSI31", "ANSI32", "AR-CONC", "SOLID")
        )
        if not is_slab_hatch:
            continue

        poly = _points_to_polygon(points, scale)
        if poly is not None:
            candidates.append(poly)

    # Extract from closed polylines
    for pl in polylines:
        if not pl.get("is_closed", False):
            continue
        layer = pl.get("layer", "")
        if not _is_slab_layer(layer):
            continue

        points = pl.get("points", [])
        poly = _points_to_polygon(points, scale)
        if poly is not None:
            candidates.append(poly)

    if not candidates:
        return []

    # Deduplicate overlapping polygons
    result = _deduplicate_polygons(candidates)

    if result:
        total_area = sum(p.area for p in result)
        logger.info(
            f"Slab boundaries: {len(result)} panels from "
            f"hatches/polylines (total {total_area:.0f}m²)"
        )

    return result


def merge_slab_sources(
    beam_slabs: List[Polygon],
    boundary_slabs: List[Polygon],
) -> List[Polygon]:
    """Merge slab polygons from beam grid and boundary extraction.

    Strategy:
    - Start with beam-grid slabs (more precise, aligned to beams)
    - Add boundary slabs that don't overlap significantly with existing ones
    - This captures slabs that the beam grid misses
    """
    if not boundary_slabs:
        return beam_slabs
    if not beam_slabs:
        return boundary_slabs

    merged = list(beam_slabs)

    for bslab in boundary_slabs:
        is_covered = False
        for existing in merged:
            try:
                intersection = bslab.intersection(existing)
                overlap = intersection.area / bslab.area if bslab.area > 0 else 0
                if overlap >= DEDUP_OVERLAP_RATIO:
                    is_covered = True
                    break
            except Exception:
                continue
        if not is_covered:
            merged.append(bslab)

    return merged


def detect_cantilever_slabs(
    slab_polygons: List[Polygon],
    pillars: List[ClassifiedElement],
) -> List[bool]:
    """Determine which slab panels are cantilevers (outside pillar hull)."""
    if len(pillars) < 3:
        return [True] * len(slab_polygons)

    pillar_points = []
    for p in pillars:
        if p.element_type != ElementType.PILLAR or not p.geometry:
            continue
        pillar_points.append(Point(p.geometry[0]))

    if len(pillar_points) < 3:
        return [True] * len(slab_polygons)

    hull = MultiPoint(pillar_points).convex_hull

    results = []
    for slab in slab_polygons:
        centroid = slab.centroid
        is_cantilever = not hull.contains(centroid)
        results.append(is_cantilever)

    return results
