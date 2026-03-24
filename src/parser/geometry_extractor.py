"""Extração de geometrias de entidades DXF para polígonos Shapely."""

from shapely.geometry import Polygon
from ezdxf.entities import LWPolyline, Polyline, DXFEntity
from typing import List, Optional


def lwpolyline_to_polygon(entity: LWPolyline) -> Optional[Polygon]:
    """Converte uma LWPOLYLINE fechada em polígono Shapely."""
    if not entity.closed:
        return None

    points = [(p[0], p[1]) for p in entity.get_points(format="xy")]
    if len(points) < 3:
        return None

    polygon = Polygon(points)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return polygon


def polyline_to_polygon(entity: Polyline) -> Optional[Polygon]:
    """Converte uma POLYLINE fechada em polígono Shapely."""
    if not entity.is_closed:
        return None

    points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
    if len(points) < 3:
        return None

    polygon = Polygon(points)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return polygon


def entity_to_polygon(entity: DXFEntity) -> Optional[Polygon]:
    """Converte qualquer entidade DXF suportada em polígono Shapely."""
    if entity.dxftype() == "LWPOLYLINE":
        return lwpolyline_to_polygon(entity)
    elif entity.dxftype() == "POLYLINE":
        return polyline_to_polygon(entity)
    return None


def extract_polygons(entities: List[DXFEntity]) -> List[Polygon]:
    """Extrai polígonos de uma lista de entidades DXF."""
    polygons = []
    for entity in entities:
        polygon = entity_to_polygon(entity)
        if polygon is not None:
            polygons.append(polygon)
    return polygons
