"""Modelo Pydantic para escoras."""

from pydantic import BaseModel, Field


class ShoreCatalogEntry(BaseModel):
    """Entrada do catálogo de escoras."""
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


class PositionedShore(BaseModel):
    """Escora posicionada na planta."""
    x: float = Field(description="Coordenada X em metros")
    y: float = Field(description="Coordenada Y em metros")
    shore: ShoreCatalogEntry = Field(description="Modelo da escora")
    load_applied_kn: float = Field(description="Carga aplicada nesta escora (kN)")
    utilization_ratio: float = Field(description="Taxa de utilização (0-1)")
