"""Construction materials database — real Brazilian building materials.

Every element in BuildingModel references a material from this module,
which determines thickness, weight, hatch pattern, structural properties,
and cost estimation data.

Sources: NBR 6120 (cargas), NBR 15961 (alvenaria estrutural),
         NBR 6118 (concreto armado), tabelas de fabricantes.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .nbr import HatchMaterial


# ---------------------------------------------------------------------------
# Wall Materials
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WallMaterial:
    """Physical properties of a wall material."""
    id: str
    name: str
    name_pt: str
    block_thickness_cm: float      # Raw block/panel thickness
    plaster_cm: float = 1.5        # Revestimento each side (0 for drywall)
    is_structural: bool = True
    weight_kn_m2: float = 0.0      # Per m² of wall area (NBR 6120)
    compressive_strength_mpa: float = 0.0  # fbk for structural masonry
    hatch: HatchMaterial = HatchMaterial.BRICK

    @property
    def total_thickness_cm(self) -> float:
        return self.block_thickness_cm + 2 * self.plaster_cm

    @property
    def total_thickness_m(self) -> float:
        return self.total_thickness_cm / 100.0


# Standard wall materials (Brazilian market)
WALL_MATERIALS = {
    "bloco_ceramico_9": WallMaterial(
        id="bloco_ceramico_9",
        name="Ceramic Block 9cm",
        name_pt="Bloco Cerâmico 9cm",
        block_thickness_cm=9,
        plaster_cm=1.5,
        is_structural=False,
        weight_kn_m2=1.30,
        hatch=HatchMaterial.BRICK,
    ),
    "bloco_ceramico_14": WallMaterial(
        id="bloco_ceramico_14",
        name="Ceramic Block 14cm",
        name_pt="Bloco Cerâmico 14cm",
        block_thickness_cm=14,
        plaster_cm=1.5,
        is_structural=True,
        weight_kn_m2=1.80,
        compressive_strength_mpa=3.0,
        hatch=HatchMaterial.BRICK,
    ),
    "bloco_ceramico_19": WallMaterial(
        id="bloco_ceramico_19",
        name="Ceramic Block 19cm",
        name_pt="Bloco Cerâmico 19cm",
        block_thickness_cm=19,
        plaster_cm=1.5,
        is_structural=True,
        weight_kn_m2=2.30,
        compressive_strength_mpa=4.0,
        hatch=HatchMaterial.BRICK,
    ),
    "bloco_concreto_14": WallMaterial(
        id="bloco_concreto_14",
        name="Concrete Block 14cm",
        name_pt="Bloco de Concreto 14cm",
        block_thickness_cm=14,
        plaster_cm=1.5,
        is_structural=True,
        weight_kn_m2=2.20,
        compressive_strength_mpa=4.5,
        hatch=HatchMaterial.CONCRETE,
    ),
    "bloco_concreto_19": WallMaterial(
        id="bloco_concreto_19",
        name="Concrete Block 19cm",
        name_pt="Bloco de Concreto 19cm",
        block_thickness_cm=19,
        plaster_cm=1.5,
        is_structural=True,
        weight_kn_m2=2.80,
        compressive_strength_mpa=6.0,
        hatch=HatchMaterial.CONCRETE,
    ),
    "drywall_simples": WallMaterial(
        id="drywall_simples",
        name="Drywall Single",
        name_pt="Drywall Simples",
        block_thickness_cm=7.0,
        plaster_cm=1.25,  # gypsum board each side
        is_structural=False,
        weight_kn_m2=0.25,
        hatch=HatchMaterial.GENERIC,
    ),
    "drywall_duplo": WallMaterial(
        id="drywall_duplo",
        name="Drywall Double",
        name_pt="Drywall Duplo",
        block_thickness_cm=7.0,
        plaster_cm=2.5,
        is_structural=False,
        weight_kn_m2=0.50,
        hatch=HatchMaterial.GENERIC,
    ),
    "concreto_armado_10": WallMaterial(
        id="concreto_armado_10",
        name="Reinforced Concrete 10cm",
        name_pt="Concreto Armado 10cm",
        block_thickness_cm=10,
        plaster_cm=0,
        is_structural=True,
        weight_kn_m2=2.50,
        compressive_strength_mpa=25.0,
        hatch=HatchMaterial.CONCRETE,
    ),
    "concreto_armado_15": WallMaterial(
        id="concreto_armado_15",
        name="Reinforced Concrete 15cm",
        name_pt="Concreto Armado 15cm",
        block_thickness_cm=15,
        plaster_cm=0,
        is_structural=True,
        weight_kn_m2=3.75,
        compressive_strength_mpa=25.0,
        hatch=HatchMaterial.CONCRETE,
    ),
    "concreto_armado_20": WallMaterial(
        id="concreto_armado_20",
        name="Reinforced Concrete 20cm",
        name_pt="Concreto Armado 20cm",
        block_thickness_cm=20,
        plaster_cm=0,
        is_structural=True,
        weight_kn_m2=5.00,
        compressive_strength_mpa=25.0,
        hatch=HatchMaterial.CONCRETE,
    ),
}


# ---------------------------------------------------------------------------
# Slab Materials
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SlabMaterial:
    """Physical properties of a slab type."""
    id: str
    name: str
    name_pt: str
    total_thickness_cm: float
    weight_kn_m2: float          # Self weight per m²
    is_structural: bool = True
    hatch: HatchMaterial = HatchMaterial.CONCRETE

    @property
    def total_thickness_m(self) -> float:
        return self.total_thickness_cm / 100.0


SLAB_MATERIALS = {
    "pre_moldada_12": SlabMaterial(
        id="pre_moldada_12",
        name="Precast Slab h=8+4",
        name_pt="Laje Pré-Moldada h=8+4cm",
        total_thickness_cm=12,
        weight_kn_m2=1.65,
    ),
    "pre_moldada_16": SlabMaterial(
        id="pre_moldada_16",
        name="Precast Slab h=12+4",
        name_pt="Laje Pré-Moldada h=12+4cm",
        total_thickness_cm=16,
        weight_kn_m2=2.10,
    ),
    "pre_moldada_20": SlabMaterial(
        id="pre_moldada_20",
        name="Precast Slab h=16+4",
        name_pt="Laje Pré-Moldada h=16+4cm",
        total_thickness_cm=20,
        weight_kn_m2=2.50,
    ),
    "macica_10": SlabMaterial(
        id="macica_10",
        name="Solid Slab 10cm",
        name_pt="Laje Maciça e=10cm",
        total_thickness_cm=10,
        weight_kn_m2=2.50,
    ),
    "macica_12": SlabMaterial(
        id="macica_12",
        name="Solid Slab 12cm",
        name_pt="Laje Maciça e=12cm",
        total_thickness_cm=12,
        weight_kn_m2=3.00,
    ),
    "macica_15": SlabMaterial(
        id="macica_15",
        name="Solid Slab 15cm",
        name_pt="Laje Maciça e=15cm",
        total_thickness_cm=15,
        weight_kn_m2=3.75,
    ),
    "steel_deck_12": SlabMaterial(
        id="steel_deck_12",
        name="Steel Deck 12cm",
        name_pt="Steel Deck 12cm",
        total_thickness_cm=12,
        weight_kn_m2=2.00,
        hatch=HatchMaterial.METAL,
    ),
    "steel_deck_15": SlabMaterial(
        id="steel_deck_15",
        name="Steel Deck 15cm",
        name_pt="Steel Deck 15cm",
        total_thickness_cm=15,
        weight_kn_m2=2.50,
        hatch=HatchMaterial.METAL,
    ),
}


# ---------------------------------------------------------------------------
# Foundation Materials
# ---------------------------------------------------------------------------

class FoundationType(Enum):
    """Foundation types for Brazilian residential construction."""
    SAPATA_CORRIDA = "sapata_corrida"
    RADIER = "radier"
    SAPATA_ISOLADA = "sapata_isolada"
    ESTACA = "estaca"
    BALDRAME_BLOCO = "baldrame_bloco"


@dataclass(frozen=True)
class FoundationMaterial:
    """Foundation type properties."""
    id: str
    name_pt: str
    type: FoundationType
    min_depth_cm: float
    typical_width_cm: float
    hatch: HatchMaterial = HatchMaterial.CONCRETE
    suitable_soil_kpa_min: float = 50.0  # Minimum soil capacity

    @property
    def depth_m(self) -> float:
        return self.min_depth_cm / 100.0

    @property
    def width_m(self) -> float:
        return self.typical_width_cm / 100.0


FOUNDATION_MATERIALS = {
    "sapata_corrida": FoundationMaterial(
        id="sapata_corrida",
        name_pt="Sapata Corrida",
        type=FoundationType.SAPATA_CORRIDA,
        min_depth_cm=40,
        typical_width_cm=60,
        suitable_soil_kpa_min=80,
    ),
    "radier": FoundationMaterial(
        id="radier",
        name_pt="Radier",
        type=FoundationType.RADIER,
        min_depth_cm=15,
        typical_width_cm=0,  # Full footprint
        suitable_soil_kpa_min=40,
    ),
    "sapata_isolada": FoundationMaterial(
        id="sapata_isolada",
        name_pt="Sapata Isolada",
        type=FoundationType.SAPATA_ISOLADA,
        min_depth_cm=40,
        typical_width_cm=80,
        suitable_soil_kpa_min=100,
    ),
    "baldrame_bloco": FoundationMaterial(
        id="baldrame_bloco",
        name_pt="Baldrame + Bloco",
        type=FoundationType.BALDRAME_BLOCO,
        min_depth_cm=50,
        typical_width_cm=30,
        suitable_soil_kpa_min=60,
    ),
    "estaca_broca": FoundationMaterial(
        id="estaca_broca",
        name_pt="Estaca Broca",
        type=FoundationType.ESTACA,
        min_depth_cm=300,
        typical_width_cm=25,
        suitable_soil_kpa_min=20,
    ),
}


# ---------------------------------------------------------------------------
# Roof Materials
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoofMaterial:
    """Roof covering material properties."""
    id: str
    name_pt: str
    weight_kn_m2: float
    min_slope_pct: float           # Minimum slope in %
    max_span_m: float = 6.0       # Max free span without intermediate support
    hatch: HatchMaterial = HatchMaterial.GENERIC

    @property
    def min_slope_deg(self) -> float:
        """Convert slope % to degrees."""
        import math
        return math.degrees(math.atan(self.min_slope_pct / 100.0))


ROOF_MATERIALS = {
    "ceramica_colonial": RoofMaterial(
        id="ceramica_colonial",
        name_pt="Telha Cerâmica Colonial",
        weight_kn_m2=0.60,
        min_slope_pct=30,
        max_span_m=4.0,
        hatch=HatchMaterial.BRICK,
    ),
    "ceramica_romana": RoofMaterial(
        id="ceramica_romana",
        name_pt="Telha Cerâmica Romana",
        weight_kn_m2=0.50,
        min_slope_pct=30,
        max_span_m=4.5,
        hatch=HatchMaterial.BRICK,
    ),
    "ceramica_portuguesa": RoofMaterial(
        id="ceramica_portuguesa",
        name_pt="Telha Cerâmica Portuguesa",
        weight_kn_m2=0.55,
        min_slope_pct=35,
        max_span_m=4.0,
        hatch=HatchMaterial.BRICK,
    ),
    "fibrocimento_6mm": RoofMaterial(
        id="fibrocimento_6mm",
        name_pt="Fibrocimento 6mm",
        weight_kn_m2=0.20,
        min_slope_pct=10,
        max_span_m=5.0,
        hatch=HatchMaterial.GENERIC,
    ),
    "fibrocimento_8mm": RoofMaterial(
        id="fibrocimento_8mm",
        name_pt="Fibrocimento 8mm",
        weight_kn_m2=0.30,
        min_slope_pct=10,
        max_span_m=6.0,
        hatch=HatchMaterial.GENERIC,
    ),
    "metalica_galvalume": RoofMaterial(
        id="metalica_galvalume",
        name_pt="Telha Metálica Galvalume",
        weight_kn_m2=0.07,
        min_slope_pct=5,
        max_span_m=8.0,
        hatch=HatchMaterial.METAL,
    ),
    "metalica_sanduiche": RoofMaterial(
        id="metalica_sanduiche",
        name_pt="Telha Metálica Sanduíche (c/ EPS)",
        weight_kn_m2=0.12,
        min_slope_pct=5,
        max_span_m=8.0,
        hatch=HatchMaterial.METAL,
    ),
    "concreto_impermeabilizado": RoofMaterial(
        id="concreto_impermeabilizado",
        name_pt="Laje Impermeabilizada",
        weight_kn_m2=2.50,
        min_slope_pct=1,
        max_span_m=5.0,
        hatch=HatchMaterial.CONCRETE,
    ),
}


# ---------------------------------------------------------------------------
# Column/Beam Materials
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StructuralMember:
    """Structural column or beam material."""
    id: str
    name_pt: str
    width_cm: float
    height_cm: float              # Depth for beams
    material: str = "concreto"    # concreto | metalico | madeira
    fck_mpa: float = 25.0        # Concrete strength
    weight_kn_m: float = 0.0     # Per linear meter
    hatch: HatchMaterial = HatchMaterial.CONCRETE

    @property
    def width_m(self) -> float:
        return self.width_cm / 100.0

    @property
    def height_m(self) -> float:
        return self.height_cm / 100.0


COLUMN_PRESETS = {
    "pilar_14x30": StructuralMember(
        id="pilar_14x30", name_pt="Pilar 14×30cm",
        width_cm=14, height_cm=30, weight_kn_m=1.05,
    ),
    "pilar_19x40": StructuralMember(
        id="pilar_19x40", name_pt="Pilar 19×40cm",
        width_cm=19, height_cm=40, weight_kn_m=1.90,
    ),
    "pilar_25x25": StructuralMember(
        id="pilar_25x25", name_pt="Pilar 25×25cm",
        width_cm=25, height_cm=25, weight_kn_m=1.56,
    ),
    "pilar_circular_25": StructuralMember(
        id="pilar_circular_25", name_pt="Pilar Circular Ø25cm",
        width_cm=25, height_cm=25, weight_kn_m=1.23,
    ),
}

BEAM_PRESETS = {
    "viga_14x40": StructuralMember(
        id="viga_14x40", name_pt="Viga 14×40cm",
        width_cm=14, height_cm=40, weight_kn_m=1.40,
    ),
    "viga_14x50": StructuralMember(
        id="viga_14x50", name_pt="Viga 14×50cm",
        width_cm=14, height_cm=50, weight_kn_m=1.75,
    ),
    "viga_19x40": StructuralMember(
        id="viga_19x40", name_pt="Viga 19×40cm",
        width_cm=19, height_cm=40, weight_kn_m=1.90,
    ),
    "viga_baldrame_14x30": StructuralMember(
        id="viga_baldrame_14x30", name_pt="Viga Baldrame 14×30cm",
        width_cm=14, height_cm=30, weight_kn_m=1.05,
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_wall_material(material_id: str) -> WallMaterial:
    """Get wall material by ID, with fallback to bloco_ceramico_14."""
    return WALL_MATERIALS.get(material_id, WALL_MATERIALS["bloco_ceramico_14"])


def get_slab_material(material_id: str) -> SlabMaterial:
    return SLAB_MATERIALS.get(material_id, SLAB_MATERIALS["pre_moldada_12"])


def get_foundation_material(material_id: str) -> FoundationMaterial:
    return FOUNDATION_MATERIALS.get(material_id, FOUNDATION_MATERIALS["sapata_corrida"])


def get_roof_material(material_id: str) -> RoofMaterial:
    return ROOF_MATERIALS.get(material_id, ROOF_MATERIALS["ceramica_colonial"])
