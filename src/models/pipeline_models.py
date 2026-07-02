"""Data models for the DXF interpretation pipeline."""

from enum import Enum
from typing import Any, List, Optional, Tuple
from pydantic import BaseModel, Field, computed_field

from src.rules.schema import Violation


class ElementType(str, Enum):
    BEAM = "beam"
    SLAB = "slab"
    PILLAR = "pillar"
    UNKNOWN = "unknown"


class RawEntity(BaseModel):
    """Entity extracted from DXF in Stage 1 (raw parse)."""
    entity_type: str = Field(description="DXF entity type: LWPOLYLINE, POLYLINE, SOLID, etc.")
    layer: str = Field(description="Layer name from DXF")
    points: List[Tuple[float, float]] = Field(description="Vertex coordinates (already scaled)")
    color: int = Field(default=7, description="DXF color index")
    texts_nearby: List[str] = Field(default_factory=list, description="TEXT/MTEXT content near entity")
    block_name: Optional[str] = Field(default=None, description="Block reference name if applicable")


class ClassifiedElement(BaseModel):
    """Element after Stage 3 classification."""
    element_type: ElementType = Field(default=ElementType.UNKNOWN)
    geometry: List[Tuple[float, float]] = Field(description="Polygon vertices in real meters")
    score_geometric: float = Field(default=0.0, ge=0.0, le=1.0)
    score_textual: float = Field(default=0.0, ge=0.0, le=1.0)
    score_final: float = Field(default=0.0, ge=0.0, le=1.0)
    name: Optional[str] = Field(default=None, description="Element name (V1, L3, P5)")
    section_width_m: Optional[float] = Field(default=None, description="Beam/pillar section width")
    section_height_m: Optional[float] = Field(default=None, description="Beam/pillar section height")
    thickness_m: Optional[float] = Field(default=None, description="Slab thickness")
    length_m: Optional[float] = Field(default=None, description="Beam length")
    source_layer: str = Field(default="", description="Original DXF layer")
    support_positions: Optional[List[float]] = Field(default=None, description="Support positions along beam axis")
    is_cantilever_start: bool = Field(default=False)
    is_cantilever_end: bool = Field(default=False)

    @computed_field
    @property
    def needs_review(self) -> bool:
        return self.score_final < 0.90


class LevelGroup(BaseModel):
    """Group of entities belonging to the same floor level."""
    level_name: str = Field(description="Level identifier (e.g., 'COBERTURA', '+1330.40')")
    level_height_m: Optional[float] = Field(default=None, description="Absolute level in meters")
    pe_direito_m: Optional[float] = Field(default=None, description="Floor-to-ceiling height")
    entities: List[RawEntity] = Field(default_factory=list)
    elements: List[ClassifiedElement] = Field(default_factory=list)


class PipelineResult(BaseModel):
    """Complete result of the interpretation pipeline."""
    filename: str
    scale: float = Field(default=1.0, description="Drawing scale factor (DXF units -> meters)")
    scale_method: str = Field(
        default="",
        description=(
            "Como a escala foi determinada: insunits/dimension/range (confiaveis), "
            "override (chamador), text/default (fallback — gera violation GEOM)"
        ),
    )
    construction_type: Optional[str] = Field(default=None, description="Detected construction type")
    slab_type: Optional[str] = Field(default=None, description="Detected slab type")
    levels: List[LevelGroup] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    calculation: Optional[Any] = Field(default=None, description="CalculationResult when engine stage runs")
    violations: List[Violation] = Field(default_factory=list, description="Rule violations detected by the rule registry")
    methodology: Optional[dict] = Field(default=None, description="Perfil de metodologia efetivo (§28.9) — rastreabilidade do output")
    requires_review: bool = Field(default=False, description="True quando o sistema detectado esta fora de escopo / exige revisao de engenharia (manual §5.1)")
    review_reasons: List[str] = Field(default_factory=list, description="Motivos pelos quais o resultado exige revisao antes do uso")
    diagnostics: dict = Field(default_factory=dict, description="Métricas de diagnóstico (kg/m³ vertical, escoras/m², base) — NÃO são gate de revisão")
    # Bloco opcional de reescoramento/desforma (manual §26 items 9 e 10) —
    # fornecido pelo engenheiro no upload; consumido pelos verificadores
    # DECIDE-001/002 via RuleProject.from_pipeline_result (getattr).
    reescoramento_data: Optional[Any] = Field(default=None, description="ReescoramentoData (src.rules.project) quando o bloco foi preenchido")
    desforma_dias: Optional[int] = Field(default=None, description="Prazo de desforma adotado (dias); piso NBR 14931 = 14")
    desforma_justificativa: str = Field(default="", description="Justificativa obrigatoria quando desforma_dias < 14")
