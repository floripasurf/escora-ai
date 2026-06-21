"""Modelo Pydantic para escoras e torres."""

from enum import Enum
from typing import List, Literal, Optional, Tuple
from pydantic import BaseModel, Field


class SupportType(str, Enum):
    """Type of shoring support."""
    TELESCOPIC = "telescopic"
    TOWER = "tower"
    MIXED = "mixed"


class ShoreCatalogEntry(BaseModel):
    """Entrada do catálogo de escoras telescópicas."""
    id: str
    aliases: List[str] = Field(
        default_factory=list,
        description="IDs legados aceitos como sinonimos para retro-compatibilidade",
    )
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
    capacity_curve: Optional[List[Tuple[float, float]]] = Field(
        default=None,
        description="List of [height_m, capacity_kn] pairs for Euler derating",
    )
    # Flags de selecao (manual §8 e §13.1)
    available: bool = Field(
        default=True,
        description="Se False, modelo nao deve ser selecionado pelo engine",
    )
    enabled: bool = Field(
        default=True,
        description="Para placeholders (ex: ESC Estendida) - locadora ativa quando cadastrar curve real",
    )
    for_sale_only: bool = Field(
        default=False,
        description="Modelo de venda; nao deve ser default em locacao (ex: ESC Junior)",
    )
    not_standard_rental: bool = Field(
        default=False,
        description="Nao usar como padrao de locacao se nao confirmado em estoque",
    )
    extended_shore: bool = Field(
        default=False,
        description="Escora telescopica estendida (>4.50 m) - permite selecao em pe-direito alto",
    )

    def matches_id(self, query: str) -> bool:
        """True quando ``query`` corresponde ao id principal OU a um alias.

        Manual §13.1: nomenclatura migrou de ESC310 -> ESC2000-3100 e
        ESC450 -> ESC3000-4500; aliases mantem retro-compatibilidade.
        """
        if query == self.id:
            return True
        return query in self.aliases

    def effective_capacity(self, height_m: float) -> float:
        """Return derated load capacity at the given extension height.

        Telescopic shores behave as Euler columns: P_crit ∝ 1/L². When a
        capacity_curve is defined, linearly interpolate between the provided
        [height, capacity] points. Outside the range, clamp to the nearest
        endpoint. If no curve is defined, fall back to the static rating
        (backward compat).
        """
        if not self.capacity_curve:
            return self.load_capacity_kn
        curve = sorted(self.capacity_curve, key=lambda p: p[0])
        if height_m <= curve[0][0]:
            return curve[0][1]
        if height_m >= curve[-1][0]:
            return curve[-1][1]
        for (h0, c0), (h1, c1) in zip(curve, curve[1:]):
            if h0 <= height_m <= h1:
                if h1 == h0:
                    return c0
                t = (height_m - h0) / (h1 - h0)
                return c0 + t * (c1 - c0)
        return curve[-1][1]


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
    capacity_curve: Optional[List[Tuple[float, float]]] = Field(
        default=None,
        description="List of [height_m, capacity_kn] pairs for derating by height",
    )

    def modules_for_height(self, required_height_m: float) -> int:
        """Calculate number of modules needed for a given height."""
        import math
        return max(1, math.ceil(required_height_m / self.module_height_m))

    def effective_capacity(self, height_m: float) -> float:
        """Return derated load capacity at the given height.

        Tower capacity decreases with height (more modules = more
        buckling risk). When a capacity_curve is defined, linearly
        interpolate between the provided [height, capacity] points.
        Outside the range, clamp to the nearest endpoint.
        If no curve is defined, fall back to the static rating.
        """
        if not self.capacity_curve:
            return self.load_capacity_kn
        curve = sorted(self.capacity_curve, key=lambda p: p[0])
        if height_m <= curve[0][0]:
            return curve[0][1]
        if height_m >= curve[-1][0]:
            return curve[-1][1]
        for (h0, c0), (h1, c1) in zip(curve, curve[1:]):
            if h0 <= height_m <= h1:
                if h1 == h0:
                    return c0
                t = (height_m - h0) / (h1 - h0)
                return c0 + t * (c1 - c0)
        return curve[-1][1]

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
    # Disponibilidade padrão da locadora. Se False, só é ofertada no modo
    # "preço" como alternativa técnica, nunca sugerida no modo "estoque"
    # (ADR Orguel B1 — ALU14/ALU20/H20 entram como opções técnicas).
    available: bool = True
    # Rigidez à flexão (kNm²) — manual Orguel p.45-55.
    # Usado para verificação de deflexão (dual check: momento + flecha).
    EI_knm2: Optional[float] = Field(
        default=None,
        description="Flexural rigidity EI in kNm² for deflection check",
    )
    # Cortante admissível do FABRICANTE (kN) — NBR 15696 Anexo B / item 4.4
    # (pendência 17, manual §13.3). None = valor não publicado em ficha
    # técnica: a verificação de cortante é PULADA (mesmo padrão backward-
    # compat do EI_knm2). NUNCA inventar valor. Rastreáveis (Manual JAU
    # p.20/33): ALU14/VA140 = 20.6 kN (2100 kgf); VA165 = 3350 kgf;
    # TJ3 = 3160 kgf; PT2 = 1978 kgf. VM80/VM130 sem cortante publicado.
    shear_capacity_kn: Optional[float] = Field(
        default=None,
        description=(
            "Cortante admissível do fabricante em kN (NBR 15696 Anexo B/4.4). "
            "None = não publicado — verificação pulada"
        ),
    )


class AccessoryCatalogEntry(BaseModel):
    """Equipment that is required by other equipment but not a primary support."""
    id: str
    category: Literal["cruzeta", "forcado", "sapata", "diagonal"]
    manufacturer: str
    model: str
    associated_model_ids: List[str] = Field(default_factory=list)
    weight_kg: float
    price_brl: float
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
