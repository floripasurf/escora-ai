"""Modelo Pydantic para laje."""

from pydantic import BaseModel, Field
from shapely.geometry import Polygon
from typing import Any


class BoundingBox(BaseModel):
    """Bounding box de uma geometria."""
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y


class Slab(BaseModel):
    """Representa uma laje extraída do DXF."""
    model_config = {"arbitrary_types_allowed": True}

    layer_name: str = Field(description="Nome do layer de origem")
    polygon: Any = Field(description="Polígono Shapely da laje")
    area_m2: float = Field(description="Área em m²")
    perimeter_m: float = Field(description="Perímetro em m")
    thickness_m: float = Field(description="Espessura em metros")
    bounding_box: BoundingBox = Field(description="Bounding box")
    level: float = Field(default=0.0, description="Nível/cota da laje em metros")

    @classmethod
    def from_polygon(
        cls,
        polygon: Polygon,
        layer_name: str,
        thickness_m: float,
        level: float = 0.0,
    ) -> "Slab":
        bounds = polygon.bounds  # (minx, miny, maxx, maxy)
        return cls(
            layer_name=layer_name,
            polygon=polygon,
            area_m2=polygon.area,
            perimeter_m=polygon.length,
            thickness_m=thickness_m,
            bounding_box=BoundingBox(
                min_x=bounds[0],
                min_y=bounds[1],
                max_x=bounds[2],
                max_y=bounds[3],
            ),
            level=level,
        )
