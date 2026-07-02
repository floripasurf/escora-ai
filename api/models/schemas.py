"""Pydantic request/response schemas."""

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional, List
from datetime import datetime


class ReescoramentoInput(BaseModel):
    """Bloco opcional de reescoramento/desforma (docs/ux/reescoramento_input_block.md).

    Espelha o JSON Schema v1 (estrutura.app/schemas/reescoramento.v1.json),
    incluindo a regra condicional: desforma_dias < 14 (piso NBR 14931) exige
    justificativa E aprovacao do calculista.
    """

    model_config = ConfigDict(extra="forbid")

    multi_pavimento: bool = False
    num_niveis_reescoramento: int = Field(default=0, ge=0, le=6)
    fcj_aos_dias_mpa: Optional[float] = Field(default=None, ge=5, le=80)
    fcj_idade_dias: int = Field(default=14, ge=1, le=90)
    eci_mpa: Optional[float] = Field(default=None, ge=10000, le=60000)
    carga_final_kn_m2: Optional[float] = Field(default=None, ge=0, le=50)
    carga_estado_construcao_kn_m2: float = 1.5
    calculista_aprovacao: str = ""
    desforma_dias: int = Field(default=14, ge=1, le=90)
    desforma_justificativa: str = ""
    desforma_anexo_laudo: str = ""

    @model_validator(mode="after")
    def _desforma_antecipada_exige_justificativa(self):
        if self.desforma_dias < 14:
            if not self.desforma_justificativa.strip():
                raise ValueError(
                    "desforma_dias < 14 (piso NBR 14931) exige justificativa tecnica"
                )
            if len(self.calculista_aprovacao.strip()) < 5:
                raise ValueError(
                    "desforma_dias < 14 exige aprovacao do calculista (nome + CREA/CAU)"
                )
        return self


class JobCreateResponse(BaseModel):
    id: str
    status: str
    filename: str
    created_at: datetime


class ConsumptionSummaryRow(BaseModel):
    """Linha agregada de consumo por (pé-direito, categoria) (validação rápida)."""
    pe_direito_m: float
    rate_kg_m3_bruto: float
    rate_kg_m3_liquido: float
    area_m2: float
    volume_bruto_m3: float
    total_kg: float
    category_label: str = "Laje"


class DiagnosticsData(BaseModel):
    """Métricas de consumo de escoramento — DIAGNÓSTICO (não gate de revisão).

    Contrato tipado p/ não quebrar silenciosamente. kg/m³ NÃO é critério de
    aprovação: a banda [12,16] não casa com estas bases (recalibração = follow-up).
    Vertical = peso das escoras; bom_partial = escoras + acessórios. Bases de
    volume diferentes (líquido vs bruto) explícitas nos campos *_volume_basis.

    extra="forbid": chave nova no payload sem campo aqui → erro (não some
    silenciosamente). Ao adicionar métrica, adicionar o campo correspondente.
    """
    model_config = ConfigDict(extra="forbid")

    # Vertical (runner.consumption_diagnostics)
    vertical_kg_m3: Optional[float] = None
    vertical_kg_per_slab_m2: Optional[float] = None
    shores_per_slab_m2: Optional[float] = None
    total_shores: Optional[int] = None
    total_vertical_weight_kg: Optional[float] = None
    total_volume_m3: Optional[float] = None
    basis: Optional[str] = None
    vertical_volume_basis: Optional[str] = None
    # BOM parcial (report_data: escoras + acessórios / volume bruto)
    bom_partial_kg_m3: Optional[float] = None
    bom_partial_kg_m2: Optional[float] = None
    bom_partial_total_kg: Optional[float] = None
    bom_partial_basis: Optional[str] = None
    bom_partial_volume_basis: Optional[str] = None
    total_liquid_volume_m3: Optional[float] = None
    total_gross_volume_m3: Optional[float] = None


class JobStatusResponse(BaseModel):
    id: str
    status: str
    filename: str
    error_message: Optional[str] = None
    # Estágio corrente do pipeline enquanto status == "processing"
    status_detail: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Results (filled when status == "done")
    beam_count: Optional[int] = None
    pillar_count: Optional[int] = None
    slab_count: Optional[int] = None
    total_shores: Optional[int] = None
    warnings: Optional[List[str]] = None
    has_output_dxf: bool = False
    has_dwg: bool = False
    has_csv: bool = False
    has_consumption_csv: bool = False
    has_ifc: bool = False
    has_relatorio: bool = False
    has_memoria_calculo: bool = False
    has_orcamento: bool = False
    has_revision: bool = False
    revision_learnings: Optional[List[str]] = None
    has_validated: bool = False
    has_diagrams: bool = False
    optimization_mode: Optional[str] = None
    inventory_name: Optional[str] = None
    methodology: Optional[dict] = None
    requires_review: bool = False
    review_reasons: Optional[List[str]] = None
    diagnostics: Optional[DiagnosticsData] = None
    consumption_summary: Optional[List[ConsumptionSummaryRow]] = None
    # Geometria simplificada p/ preview SVG 2D ({slabs, beams, bbox, truncated})
    preview: Optional[dict] = None

