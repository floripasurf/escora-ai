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


def derive_slabs_from_beams(beams: List[ClassifiedElement]) -> List[Polygon]:
    """Extract closed slab panels from the beam grid."""
    lines = _extend_beams_to_grid(beams)

    if not lines:
        return []

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
