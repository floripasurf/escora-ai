"""Result models for the calculation pipeline bridge."""

from typing import List, Any, Optional
from pydantic import BaseModel, Field
from src.models.pipeline_models import ClassifiedElement
from src.models.shore import ShoreCatalogEntry, PositionedShore


class BeamShoringResult(BaseModel):
    """Shoring result for a single beam."""
    beam: ClassifiedElement
    support_positions: List[float] = Field(description="Pillar distances along beam axis (m)")
    is_cantilever_start: bool = False
    is_cantilever_end: bool = False
    total_linear_load_kn_m: float = Field(description="Majorized load per meter (kN/m)")
    shores: List[PositionedShore]
    shore_count: int
    spacing_m: float
    selected_shore: ShoreCatalogEntry
    shore_height_m: float = Field(description="Actual shore height used (m)")


class SlabShoringResult(BaseModel):
    """Shoring result for a single slab panel."""
    model_config = {"arbitrary_types_allowed": True}

    polygon: Any = Field(description="Shapely polygon of slab panel")
    thickness_m: float
    thickness_is_default: bool = False
    area_m2: float
    is_cantilever: bool = False
    total_load_kn: float = Field(description="Majorized total load (kN)")
    shores: List[PositionedShore]
    grid_nx: int = 0
    grid_ny: int = 0
    spacing_x_m: float = 0.0
    spacing_y_m: float = 0.0
    selected_shore: Optional[ShoreCatalogEntry] = None
    exclusions: List[Any] = Field(default_factory=list, description="PillarExclusion zones applied")


class CalculationResult(BaseModel):
    """Complete calculation result for one level."""
    beam_results: List[BeamShoringResult] = Field(default_factory=list)
    slab_results: List[SlabShoringResult] = Field(default_factory=list)
    shore_catalog_used: List[ShoreCatalogEntry] = Field(default_factory=list)
    total_shores: int = 0
    total_load_kn: float = 0.0
    pe_direito_m: float = 2.80
    pe_direito_is_default: bool = False
    warnings: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    is_valid: bool = True
