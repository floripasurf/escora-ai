"""Derive slab panels from beam grid via Shapely polygonize.

Algorithm:
1. Convert each beam to a Shapely LineString along its axis
2. Union all beam lines into a geometry network
3. Use shapely.ops.polygonize() to extract closed regions
4. Each polygon = one slab panel
"""

from typing import List
from shapely.geometry import LineString, Point, MultiPoint
from shapely.ops import polygonize, unary_union
from shapely.geometry.polygon import Polygon
from src.models.pipeline_models import ClassifiedElement, ElementType

MIN_SLAB_AREA = 0.5  # m2 -- anything smaller is noise


def derive_slabs_from_beams(beams: List[ClassifiedElement]) -> List[Polygon]:
    """Extract closed slab panels from the beam grid."""
    lines = []
    for beam in beams:
        if beam.element_type != ElementType.BEAM:
            continue
        if len(beam.geometry) < 2:
            continue
        start = beam.geometry[0]
        end = beam.geometry[1]
        line = LineString([start, end])
        if line.length > 0:
            lines.append(line)

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
