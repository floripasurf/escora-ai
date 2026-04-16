"""Modelos de domínio para projeto de alvenaria estrutural.

Referências:
- NBR 15961-1:2011 — Alvenaria estrutural — Blocos de concreto
- NBR 15575:2013 — Edificações habitacionais — Desempenho
- NBR 6118:2023 — Projeto de estruturas de concreto
"""

from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class LayoutType(str, Enum):
    OPEN_KITCHEN = "open_kitchen"      # sala + cozinha integradas
    SEPARATE_KITCHEN = "separate_kitchen"
    WITH_GARAGE = "with_garage"
    LINEAR = "linear"                  # corredor central
    L_SHAPED = "l_shaped"


class RoomType(str, Enum):
    BEDROOM = "bedroom"
    LIVING = "living"
    KITCHEN = "kitchen"
    BATHROOM = "bathroom"
    SERVICE = "service"           # área de serviço
    CIRCULATION = "circulation"   # corredor/hall
    GARAGE = "garage"
    VARANDA = "varanda"            # varanda/deck/porch


class BlockSize(str, Enum):
    B14 = "14"   # bloco 14cm, módulo 15cm
    B19 = "19"   # bloco 19cm, módulo 20cm


class OpeningType(str, Enum):
    DOOR = "door"
    WINDOW = "window"


class FoundationType(str, Enum):
    SAPATA_CORRIDA = "sapata_corrida"
    RADIER = "radier"


class SiteOrientation(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class ArchStyle(str, Enum):
    MODERN = "modern"
    COLONIAL = "colonial"
    MINIMAL = "minimal"
    TROPICAL = "tropical"
    CONTEMPORARY = "contemporary"


class RoofStyle(str, Enum):
    GABLE = "gable"         # duas águas
    HIP = "hip"             # quatro águas
    FLAT = "flat"           # laje impermeabilizada
    SHED = "shed"           # uma água (econômico)


class StructureType(str, Enum):
    MASONRY = "masonry"           # alvenaria estrutural (padrão)
    SELF_SUPPORTING = "self_supporting"  # autoportante


class RoofMaterial(str, Enum):
    CERAMIC = "ceramic"           # telha cerâmica
    FIBER_CEMENT = "fiber_cement"  # fibrocimento
    SANDWICH = "sandwich"          # telha sanduíche (econômico, térmico)
    METAL = "metal"               # telha metálica


class ProjectInput(BaseModel):
    """Dados de entrada do formulário do usuário."""
    floors: int = Field(default=1, ge=1, le=2, description="Número de pavimentos")
    target_area_m2: float = Field(ge=30.0, le=100.0, description="Área alvo (m²)")
    bedrooms: int = Field(ge=1, le=4, description="Número de quartos")
    bathrooms: int = Field(default=1, ge=1, le=2)
    layout_type: LayoutType = Field(default=LayoutType.OPEN_KITCHEN)
    has_garage: bool = Field(default=False)
    lot_width_m: float = Field(ge=5.0, le=20.0, description="Largura do lote (m)")
    lot_depth_m: float = Field(ge=10.0, le=40.0, description="Profundidade do lote (m)")
    block_size: BlockSize = Field(default=BlockSize.B14)
    region: str = Field(default="sudeste")
    soil_capacity_kpa: float = Field(default=100.0, ge=50.0, le=500.0)
    ceiling_height_m: float = Field(default=2.80, ge=2.50, le=3.20)
    roof_type: str = Field(default="wooden_truss")


class WallOpening(BaseModel):
    """Abertura (porta ou janela) em uma parede."""
    type: OpeningType
    width_m: float = Field(description="Largura da abertura (m)")
    height_m: float = Field(description="Altura da abertura (m)")
    sill_height_m: float = Field(default=0.0, description="Peitoril (m) — 0 para portas")
    position_m: float = Field(description="Posição ao longo da parede (m)")


class Wall(BaseModel):
    """Parede de alvenaria estrutural."""
    id: str = Field(description="Identificador da parede (ex: P1, P2)")
    start: Tuple[float, float] = Field(description="Ponto inicial (x, y) em metros")
    end: Tuple[float, float] = Field(description="Ponto final (x, y) em metros")
    thickness_m: float = Field(description="Espessura (m) — 0.14 ou 0.19")
    is_structural: bool = Field(default=True)
    height_m: float = Field(default=2.80)
    load_kn_per_m: float = Field(default=0.0, description="Carga linear acumulada (kN/m)")
    openings: List[WallOpening] = Field(default_factory=list)

    @property
    def length_m(self) -> float:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        return (dx**2 + dy**2) ** 0.5

    @property
    def net_area_m2(self) -> float:
        """Área líquida (descontando aberturas)."""
        gross = self.length_m * self.height_m
        openings_area = sum(o.width_m * o.height_m for o in self.openings)
        return gross - openings_area


class Room(BaseModel):
    """Cômodo do projeto."""
    name: str
    type: RoomType
    polygon: List[Tuple[float, float]] = Field(description="Vértices do polígono (x, y)")
    min_area_m2: float = Field(description="Área mínima NBR 15575")
    target_area_m2: float = Field(default=0.0)
    is_wet: bool = Field(default=False, description="Área molhada (banheiro, cozinha, serviço)")
    floor_level: int = Field(default=0)

    @property
    def area_m2(self) -> float:
        if len(self.polygon) < 3:
            return 0.0
        from shapely.geometry import Polygon as ShapelyPolygon
        return ShapelyPolygon(self.polygon).area


class Lintel(BaseModel):
    """Verga/contraverga sobre abertura."""
    wall_id: str
    opening_index: int
    width_m: float
    height_m: float = Field(default=0.15)
    span_m: float
    rebar: str = Field(default="2φ8mm")


class TieBeam(BaseModel):
    """Cinta de amarração (respaldo ou intermediária)."""
    level: str = Field(description="'respaldo' ou 'intermediaria'")
    path: List[Tuple[float, float]] = Field(description="Percurso da cinta")
    width_m: float
    height_m: float = Field(default=0.15)
    rebar: str = Field(default="4φ8mm + estr. φ5c/20")


class Foundation(BaseModel):
    """Fundação do projeto."""
    type: FoundationType
    width_m: float = Field(description="Largura da sapata corrida ou lado do radier")
    depth_m: float = Field(default=0.40, description="Profundidade")
    height_m: float = Field(default=0.30, description="Altura da base")
    soil_capacity_kpa: float = Field(default=100.0)
    load_per_m_kn: float = Field(default=0.0)
    rebar: str = Field(default="φ8c/20 ambas direções")


class FloorPlan(BaseModel):
    """Planta de um pavimento."""
    level: int = Field(default=0, description="0=térreo, 1=superior")
    rooms: List[Room] = Field(default_factory=list)
    walls: List[Wall] = Field(default_factory=list)
    lintels: List[Lintel] = Field(default_factory=list)
    tie_beams: List[TieBeam] = Field(default_factory=list)
    width_m: float = Field(default=0.0)
    depth_m: float = Field(default=0.0)


class MasonryProject(BaseModel):
    """Projeto completo de alvenaria estrutural."""
    input: ProjectInput
    floor_plans: List[FloorPlan] = Field(default_factory=list)
    foundations: List[Foundation] = Field(default_factory=list)
    block_fbk_mpa: float = Field(default=4.5, description="Resistência do bloco selecionada")
    total_block_count: int = Field(default=0)
    total_wall_area_m2: float = Field(default=0.0)
    warnings: List[str] = Field(default_factory=list)


class DesignInput(ProjectInput):
    """Extended input for interactive design mode."""
    street_side: SiteOrientation = Field(default=SiteOrientation.SOUTH, description="Lado da rua")
    sun_orientation_deg: float = Field(default=0.0, ge=0.0, le=360.0, description="Orientação norte (graus)")
    style: ArchStyle = Field(default=ArchStyle.MODERN)
    roof_style: RoofStyle = Field(default=RoofStyle.GABLE)
    privacy_priority: str = Field(default="balanced", description="max_privacy | balanced | open")
    country: str = Field(default="BR", description="ISO 3166-1 alpha-2 country code")
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    # Economic construction options
    economy_mode: bool = Field(default=False, description="Priorizar soluções econômicas")
    foundation_type: FoundationType = Field(default=FoundationType.SAPATA_CORRIDA)
    structure_type: StructureType = Field(default=StructureType.MASONRY)
    roof_material: RoofMaterial = Field(default=RoofMaterial.CERAMIC)


class SiteAnalysis(BaseModel):
    """Resultado da análise do terreno."""
    latitude: float
    longitude: float
    elevation_m: float = 0.0
    street_direction: str = "south"
    sun_morning_direction: str = "east"
    sun_afternoon_direction: str = "west"
    best_view_direction: Optional[str] = None
    climate_zone: str = "tropical"
    wind_predominant: Optional[str] = None
