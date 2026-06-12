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
    shores_weight_kg: float = Field(default=0.0, description="Soma do peso das escoras desta viga (kg)")
    is_perimeter: bool = Field(default=False, description="Viga externa (centroide além do casco convexo dos pilares por >0.5m)")
    decision_rule: str = Field(default="", description="Slug estável da regra de decisão aplicada (ex.: 'rule-16b-viga-media')")


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
    volume_m3: float = Field(default=0.0, description="Volume escorado bruto do painel (m³)")
    # Categorização didática e rotulagem
    category: str = Field(default="laje", description="Categoria do painel: laje | beiral | balanco | platibanda | marquise | cantilever")
    category_index: int = Field(default=0, description="Número sequencial dentro da categoria (1-based)")
    label: str = Field(default="", description="Rótulo final exibido (ex.: 'Laje L3', 'Beiral 1')")
    room_hint: Optional[str] = Field(default=None, description="Texto de cômodo extraído do DXF próximo ao polígono, se houver")
    structural_name: Optional[str] = Field(default=None, description="Nome estrutural extraído do DXF (ex.: 'L3')")
    shores_weight_kg: float = Field(default=0.0, description="Soma do peso das escoras desta laje (kg)")
    decision_rule: str = Field(default="", description="Slug estável da regra de decisão aplicada (ex.: 'rule-4-laje-espessa')")
    # Manual §28.8 (gold standard Orguel): modo de posicionamento das escoras
    # de laje. "grid" = grid de pontos legado; "line_first" = linhas de guia
    # com escoras ao longo da linha (src/engine/line_first_builder.py).
    layout_mode: str = Field(default="grid", description="Modo de posicionamento: grid | line_first")
    # Manual §28: grid completo de VMs (primarias + secundarias) sobre as
    # escoras posicionadas. Populated por stage_calculate via build_vm_grid().
    # Tipo real: src.engine.vm_grid_builder.VMGrid (dataclass).
    vm_grid: Optional[Any] = Field(
        default=None,
        description="VMGrid com vigas primarias/secundarias e BOM por modelo+comprimento",
    )


class VolumeBreakdownEntry(BaseModel):
    """Linha de breakdown de volume escorado por elemento (painel)."""
    category: str = Field(description="Categoria do painel (laje, beiral, etc.)")
    label: str = Field(description="Rótulo didático (ex.: 'Beiral 1')")
    area_m2: float
    pe_direito_m: float
    volume_m3: float
    centroid_x: float
    centroid_y: float
    shores_weight_kg: float = Field(default=0.0, description="Peso das escoras atribuído a este painel (kg)")


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
    total_volume_m3: float = Field(default=0.0, description="Volume escorado líquido (m³)")
    slab_volume_gross_m3: float = Field(default=0.0, description="Volume bruto de laje × pé-direito (m³)")
    beam_volume_deducted_m3: float = Field(default=0.0, description="Volume deduzido de vigas (m³)")
    pillar_volume_deducted_m3: float = Field(default=0.0, description="Volume deduzido de pilares (m³)")
    pillar_count: int = Field(default=0, description="Número de pilares detectados (para BOM de travamento VM50)")
    volume_breakdown: List[VolumeBreakdownEntry] = Field(
        default_factory=list,
        description="Breakdown de volume por painel (laje, beiral, platibanda...)",
    )
    passo_sob_viga_m: Optional[float] = Field(
        default=None,
        description=(
            "Passo escora+cruzeta sob viga vindo do perfil de metodologia "
            "(§28.9); None = legado (0.80 m DOCX para cruzetas)"
        ),
    )
