"""Extração de geometrias de entidades DXF para polígonos Shapely."""

from shapely.geometry import Polygon
from ezdxf.entities import LWPolyline, Polyline, DXFEntity
from typing import List, Optional

# Tolerância para considerar polyline como "quase fechada" (metros)
CLOSE_TOLERANCE = 0.01


def _is_nearly_closed(points: List[tuple]) -> bool:
    """Verifica se primeiro e último ponto são praticamente o mesmo."""
    if len(points) < 3:
        return False
    dx = points[0][0] - points[-1][0]
    dy = points[0][1] - points[-1][1]
    return (dx * dx + dy * dy) ** 0.5 < CLOSE_TOLERANCE


def lwpolyline_to_polygon(entity: LWPolyline) -> Optional[Polygon]:
    """Converte uma LWPOLYLINE fechada ou quase-fechada em polígono Shapely."""
    points = [(p[0], p[1]) for p in entity.get_points(format="xy")]
    if len(points) < 3:
        return None

    if not entity.closed and not _is_nearly_closed(points):
        return None

    polygon = Polygon(points)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return polygon


def polyline_to_polygon(entity: Polyline) -> Optional[Polygon]:
    """Converte uma POLYLINE fechada ou quase-fechada em polígono Shapely."""
    points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
    if len(points) < 3:
        return None

    if not entity.is_closed and not _is_nearly_closed(points):
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


def extract_polygons(
    entities: List[DXFEntity],
    min_area: float = 0.0,
) -> List[Polygon]:
    """Extrai polígonos de uma lista de entidades DXF.

    Args:
        entities: Lista de entidades DXF.
        min_area: Área mínima em m² para incluir (filtra shapes pequenos).
    """
    polygons = []
    for entity in entities:
        polygon = entity_to_polygon(entity)
        if polygon is not None and polygon.area >= min_area:
            polygons.append(polygon)
    return polygons
