"""Pydantic request/response schemas."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


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


class JobStatusResponse(BaseModel):
    id: str
    status: str
    filename: str
    error_message: Optional[str] = None
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
    diagnostics: Optional[dict] = None
    consumption_summary: Optional[List[ConsumptionSummaryRow]] = None

