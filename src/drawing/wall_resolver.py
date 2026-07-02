"""Wall intersection resolver — merges overlapping wall polygons at junctions.

Solves the visual quality problem where walls drawn as independent rectangles
overlap at corners. Produces clean L-junctions, T-junctions, and X-crossings
by computing the union of all wall polygons using Shapely.

Also handles wall segments with openings by subtracting opening voids from
wall geometry before drawing.

Usage:
    from src.drawing.wall_resolver import resolve_walls, draw_resolved_walls

    resolved = resolve_walls(model.walls_on_floor(0))
    draw_resolved_walls(sheet, resolved)
"""

import math
import logging
from dataclasses import dataclass
from typing import List, Tuple

from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

from .nbr import HatchMaterial, LineType

logger = logging.getLogger(__name__)

Point2D = Tuple[float, float]


@dataclass
class ResolvedWall:
    """A wall polygon after intersection resolution."""
    polygon: List[Point2D]       # Outer boundary (clean corners)
    holes: List[List[Point2D]]   # Opening voids
    is_structural: bool = True
    hatch: HatchMaterial = HatchMaterial.BRICK
    thickness_m: float = 0.15


def _wall_polygon(p1: Point2D, p2: Point2D, thickness: float) -> Polygon:
    """Create a Shapely polygon for a wall segment."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = math.sqrt(dx**2 + dy**2)
    if length < 1e-6:
        return Polygon()

    # Normal direction
    t = thickness / 2
    nx = -dy / length * t
    ny = dx / length * t

    coords = [
        (p1[0] + nx, p1[1] + ny),
        (p2[0] + nx, p2[1] + ny),
        (p2[0] - nx, p2[1] - ny),
        (p1[0] - nx, p1[1] - ny),
    ]
    return Polygon(coords)


def _opening_polygon(
    wall_p1: Point2D,
    wall_p2: Point2D,
    wall_thickness: float,
    position_m: float,
    width: float,
) -> Polygon:
    """Create a Shapely polygon for an opening void in plan view."""
    dx = wall_p2[0] - wall_p1[0]
    dy = wall_p2[1] - wall_p1[1]
    length = math.sqrt(dx**2 + dy**2)
    if length < 1e-6:
        return Polygon()

    ux, uy = dx / length, dy / length
    nx, ny = -uy * wall_thickness / 2, ux * wall_thickness / 2

    # Opening start and end along wall
    sx = wall_p1[0] + ux * position_m
    sy = wall_p1[1] + uy * position_m
    ex = sx + ux * width
    ey = sy + uy * width

    # Extend slightly beyond wall thickness to ensure clean cut
    ext = wall_thickness * 0.1
    coords = [
        (sx + nx * (1 + ext), sy + ny * (1 + ext)),
        (ex + nx * (1 + ext), ey + ny * (1 + ext)),
        (ex - nx * (1 + ext), ey - ny * (1 + ext)),
        (sx - nx * (1 + ext), sy - ny * (1 + ext)),
    ]
    return Polygon(coords)


def resolve_walls(walls) -> List[ResolvedWall]:
    """Resolve wall intersections by merging overlapping polygons.

    Groups walls by structural/non-structural, computes union within
    each group, then subtracts opening voids.

    Args:
        walls: List of WallSegment from BuildingModel

    Returns:
        List of ResolvedWall with clean corner geometry
    """
    # Group by structural type
    structural_polys = []
    non_structural_polys = []
    opening_polys = []

    structural_hatch = HatchMaterial.BRICK
    non_structural_hatch = HatchMaterial.GENERIC

    for wall in walls:
        poly = _wall_polygon(wall.p1, wall.p2, wall.thickness_m)
        if poly.is_empty:
            continue

        if wall.is_structural:
            structural_polys.append(poly)
            structural_hatch = wall.hatch
        else:
            non_structural_polys.append(poly)
            non_structural_hatch = wall.hatch

        # Collect opening voids
        for opening in wall.openings:
            op = _opening_polygon(
                wall.p1, wall.p2, wall.thickness_m,
                opening.position_m, opening.width,
            )
            if not op.is_empty:
                opening_polys.append(op)

    results = []

    # Merge structural walls
    if structural_polys:
        merged = unary_union(structural_polys)
        # Subtract openings
        if opening_polys:
            opening_union = unary_union(opening_polys)
            merged = merged.difference(opening_union)

        for geom in _to_polygons(merged):
            ext = list(geom.exterior.coords)
            holes = [list(h.coords) for h in geom.interiors]
            results.append(ResolvedWall(
                polygon=ext,
                holes=holes,
                is_structural=True,
                hatch=structural_hatch,
                thickness_m=walls[0].thickness_m if walls else 0.15,
            ))

    # Merge non-structural walls
    if non_structural_polys:
        merged = unary_union(non_structural_polys)
        if opening_polys:
            opening_union = unary_union(opening_polys)
            merged = merged.difference(opening_union)

        for geom in _to_polygons(merged):
            ext = list(geom.exterior.coords)
            holes = [list(h.coords) for h in geom.interiors]
            results.append(ResolvedWall(
                polygon=ext,
                holes=holes,
                is_structural=False,
                hatch=non_structural_hatch,
            ))

    logger.info(
        f"Wall resolver: {len(walls)} segments → {len(results)} resolved polygons "
        f"({len(opening_polys)} openings subtracted)"
    )

    return results


def _to_polygons(geom) -> List[Polygon]:
    """Convert a Shapely geometry to a list of Polygons."""
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    # GeometryCollection or other
    result = []
    for g in geom.geoms:
        if isinstance(g, Polygon):
            result.append(g)
    return result


def draw_resolved_walls(sheet, resolved: List[ResolvedWall]) -> None:
    """Draw resolved wall polygons on a TechnicalSheet.

    Uses polyline for outline and hatch for fill, with clean
    corners at wall junctions.
    """
    for rw in resolved:
        layer = "PAR-ESTRU" if rw.is_structural else "PAR-VEDA"
        lt = LineType.A if rw.is_structural else LineType.B

        # Draw outer boundary
        sheet.draw_polyline(
            rw.polygon, layer=layer, closed=True, line_type=lt,
        )

        # Draw holes (opening voids)
        for hole in rw.holes:
            sheet.draw_polyline(
                hole, layer=layer, closed=True, line_type=lt,
            )

        # Hatch fill
        if rw.is_structural:
            hatch = sheet.msp.add_hatch(
                color=8,
                dxfattribs={"layer": layer},
            )
            hatch.set_solid_fill()
            hatch.paths.add_polyline_path(
                [(p[0], p[1]) for p in rw.polygon],
                is_closed=True,
            )
            # Subtract holes from hatch
            for hole in rw.holes:
                hatch.paths.add_polyline_path(
                    [(p[0], p[1]) for p in hole],
                    is_closed=True,
                )
