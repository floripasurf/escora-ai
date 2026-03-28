"""Modelo Pydantic para escoras e torres."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SupportType(str, Enum):
    """Type of shoring support."""
    TELESCOPIC = "telescopic"
    TOWER = "tower"


class ShoreCatalogEntry(BaseModel):
    """Entrada do catálogo de escoras telescópicas."""
    id: str
    manufacturer: str
    model: str
    type: str = "telescopic"
    height_min_m: float
    height_max_m: float
    load_capacity_kn: float
    weight_kg: float
    tube_external_mm: float
    tube_internal_mm: float
    base_plate_mm: float
    price_reference_brl: float
    notes: str = ""


class TowerCatalogEntry(BaseModel):
    """Entrada do catálogo de torres de escoramento."""
    id: str
    manufacturer: str
    model: str
    system: str = "tubular"  # tubular, cuplock, ringlock, modular_roseta
    load_capacity_kn: float
    module_height_m: float
    base_dimension_m: float
    max_height_m: float
    weight_per_module_kg: float
    includes_bracing: bool = True
    price_per_module_brl: float
    notes: str = ""

    def modules_for_height(self, required_height_m: float) -> int:
        """Calculate number of modules needed for a given height."""
        import math
        return max(1, math.ceil(required_height_m / self.module_height_m))

    def total_weight_kg(self, required_height_m: float) -> float:
        """Total weight for the required height."""
        return self.modules_for_height(required_height_m) * self.weight_per_module_kg

    def total_price_brl(self, required_height_m: float) -> float:
        """Total price for the required height."""
        return self.modules_for_height(required_height_m) * self.price_per_module_brl


class DistributionBeamEntry(BaseModel):
    """Entrada do catálogo de vigas de distribuição."""
    id: str
    manufacturer: str
    model: str
    height_mm: int
    moment_capacity_knm: float
    max_span_m: float
    weight_per_m_kg: float
    price_per_m_brl: float
    notes: str = ""


class PositionedShore(BaseModel):
    """Escora ou torre posicionada na planta."""
    x: float = Field(description="Coordenada X em metros")
    y: float = Field(description="Coordenada Y em metros")
    shore: ShoreCatalogEntry = Field(description="Modelo da escora")
    load_applied_kn: float = Field(description="Carga aplicada nesta escora (kN)")
    utilization_ratio: float = Field(description="Taxa de utilização (0-1)")
    support_type: SupportType = Field(default=SupportType.TELESCOPIC)
    tower: Optional[TowerCatalogEntry] = Field(default=None, description="Torre quando support_type=TOWER")
    distribution_beam: Optional[DistributionBeamEntry] = Field(default=None, description="Viga de distribuição")
