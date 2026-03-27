"""Derive slab panels from beam grid via Shapely polygonize.

Algorithm:
1. Convert each beam to a Shapely LineString along its axis
2. Snap beam endpoints to nearby perpendicular beams (bridge pillar gaps)
3. Union all beam lines into a geometry network
4. Use shapely.ops.polygonize() to extract closed regions
5. Each polygon = one slab panel
"""

from typing import List, Tuple
from shapely.geometry import LineString, Point, MultiPoint
from shapely.ops import polygonize, unary_union, snap
from shapely.geometry.polygon import Polygon
from src.models.pipeline_models import ClassifiedElement, ElementType

MIN_SLAB_AREA = 0.5  # m2 -- anything smaller is noise

# Max gap to bridge between beam endpoints and perpendicular beams (pillar width)
SNAP_TOLERANCE = 0.60  # m — typical pillar is 0.20-0.50m wide


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


def derive_slabs_from_beams(beams: List[ClassifiedElement]) -> List[Polygon]:
    """Extract closed slab panels from the beam grid."""
    lines = _extend_beams_to_grid(beams)

    if not lines:
        return []

    merged = unary_union(lines)
    polygons = list(polygonize(merged))
    return [p for p in polygons if p.area >= MIN_SLAB_AREA]


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
