"""Data model v2 — templates baseados em zonas compostas.

Substitui o modelo plano (rooms com rel_x/y/w/h num retângulo 0-1)
por um modelo de zonas semânticas que permite formas não-retangulares
(L, U, varanda, pátio) e validação topológica de circulação.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional


@dataclass
class Zone:
    """Região retangular semântica do edifício.

    Zonas compõem a forma do edifício. Uma casa retangular tem 1 zona;
    uma casa em L tem 2; uma casa com varanda tem zona principal + zona outdoor.
    """
    id: str
    anchor_x: float  # posição X em metros relativa à origem do edifício
    anchor_y: float  # posição Y em metros (Y=0 = frente/rua)
    width_m: float
    depth_m: float
    scalable_axis: str = "both"  # "width" | "depth" | "both" | "fixed"
    is_outdoor: bool = False     # varanda, porch — não conta na área construída

    @property
    def area_m2(self) -> float:
        return self.width_m * self.depth_m

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """(x0, y0, x1, y1) em metros."""
        return (self.anchor_x, self.anchor_y,
                self.anchor_x + self.width_m, self.anchor_y + self.depth_m)


@dataclass
class RoomDef:
    """Cômodo posicionado dentro de uma zona."""
    name: str
    type: str       # "bedroom", "living", "kitchen", "bathroom", "service", "circulation", "garage"
    zone_id: str    # ID da zona que contém este cômodo
    rel_x: float    # coordenadas relativas DENTRO da zona (0-1)
    rel_y: float
    rel_w: float
    rel_h: float
    is_wet: bool = False


@dataclass
class CirculationGraph:
    """Topologia explícita de acesso entre cômodos.

    O grafo define quais cômodos devem ter portas entre si.
    A validação verifica que todo cômodo é acessível a partir da
    entrada sem passar por quartos.
    """
    entrance: str                    # nome do cômodo de entrada
    edges: Dict[str, List[str]] = field(default_factory=dict)

    def is_reachable_without_bedrooms(self, target: str) -> bool:
        """BFS: target acessível a partir da entrada sem atravessar bedroom."""
        visited = set()
        queue = [self.entrance]
        visited.add(self.entrance)

        while queue:
            current = queue.pop(0)
            if current == target:
                return True
            for neighbor in self.edges.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    # Pode entrar em qualquer cômodo, mas só atravessa não-quartos
                    # (quartos são destinos, não corredores)
                    queue.append(neighbor)
        return target in visited

    def all_rooms(self) -> set:
        """Retorna todos os cômodos mencionados no grafo."""
        rooms = {self.entrance}
        for src, dsts in self.edges.items():
            rooms.add(src)
            rooms.update(dsts)
        return rooms


@dataclass
class LotPlacement:
    """Como o edifício se posiciona no lote."""
    street_facing_zone: str = "social"
    setback_front_m: float = 3.0
    setback_back_m: float = 2.0
    setback_side_m: float = 1.5
    building_coverage_max: float = 0.65
    garden_side: str = "back"
    driveway_side: Optional[str] = None  # "left" | "right" | None


@dataclass
class TemplateV2:
    """Template arquitetônico v2 — baseado em zonas compostas."""
    id: str
    name: str
    typology: str                         # "rectangle" | "l_shape" | "u_shape"
    target_area_range: Tuple[float, float]
    bedrooms: int
    bathrooms: int
    tags: List[str]
    zones: List[Zone]
    rooms: List[RoomDef]
    circulation: CirculationGraph
    lot_placement: LotPlacement = field(default_factory=LotPlacement)
    privacy_gradient: List[str] = field(default_factory=list)

    @property
    def built_area_m2(self) -> float:
        """Área construída (exclui zonas outdoor)."""
        return sum(z.area_m2 for z in self.zones if not z.is_outdoor)

    @property
    def total_area_m2(self) -> float:
        """Área total incluindo outdoor."""
        return sum(z.area_m2 for z in self.zones)

    @property
    def bounding_box(self) -> Tuple[float, float, float, float]:
        """(x0, y0, x1, y1) do bounding box de todas as zonas."""
        if not self.zones:
            return (0, 0, 0, 0)
        x0 = min(z.anchor_x for z in self.zones)
        y0 = min(z.anchor_y for z in self.zones)
        x1 = max(z.anchor_x + z.width_m for z in self.zones)
        y1 = max(z.anchor_y + z.depth_m for z in self.zones)
        return (x0, y0, x1, y1)

    def get_zone(self, zone_id: str) -> Optional[Zone]:
        for z in self.zones:
            if z.id == zone_id:
                return z
        return None
