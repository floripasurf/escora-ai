"""Modelo de compensado (plywood) - manual §26 item 5.

O formato do compensado deve ser PARAMETRO DE ENTRADA, nao default rigido.
O mercado brasileiro trabalha com 1100 x 2200 mm e 1220 x 2440 mm, alem de
variacoes por fabricante.

Quando nao informado, default e 1220 x 2440 (compatibilidade com Orguel).
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# Formatos padrao de mercado (manual §26 item 5).
PLYWOOD_FORMAT_INTL_MM = (1220, 2440)   # padrao internacional / Orguel
PLYWOOD_FORMAT_BR_MM = (1100, 2200)     # padrao mercado brasileiro
DEFAULT_PLYWOOD_FORMAT_MM = PLYWOOD_FORMAT_INTL_MM


class PlywoodSpec(BaseModel):
    """Especificacao do compensado usado no projeto.

    Campos:
    - thickness_mm: espessura nominal (12, 14, 15, 17, 18, 20 ou 21 mm).
    - width_mm: largura util da chapa.
    - length_mm: comprimento da chapa.
    - seam_multiple_mm: passo de espacamento de barrotes para emenda no
      eixo (default = width_mm / 5, normalmente 220 ou 244).
    - manufacturer: opcional, para rastreabilidade.

    Manual §11.2: emenda de compensado deve cair no eixo do barrote, com
    espacamento multiplo do `seam_multiple_mm`.
    """

    thickness_mm: float = Field(
        default=18.0,
        description="Espessura nominal do compensado em mm",
    )
    width_mm: int = Field(
        default=DEFAULT_PLYWOOD_FORMAT_MM[0],
        description="Largura util da chapa (1100, 1220, 1500...)",
    )
    length_mm: int = Field(
        default=DEFAULT_PLYWOOD_FORMAT_MM[1],
        description="Comprimento da chapa (2200, 2440, 3000...)",
    )
    seam_multiple_mm: Optional[int] = Field(
        default=None,
        description=(
            "Passo de emenda em mm. Se omitido, derivado da largura: "
            "1220 -> 244, 1100 -> 220, 1500 -> 250."
        ),
    )
    manufacturer: str = Field(
        default="",
        description="Fabricante (opcional, para rastreabilidade)",
    )

    def effective_seam_multiple_mm(self) -> int:
        """Retorna o passo de emenda; deriva se nao especificado."""
        if self.seam_multiple_mm is not None:
            return self.seam_multiple_mm
        # Derivacao padrao Orguel: 1/5 da largura
        return int(self.width_mm / 5)

    def is_standard_format(self) -> bool:
        """True se a chapa for um dos formatos de mercado documentados."""
        fmt = (self.width_mm, self.length_mm)
        return fmt in (PLYWOOD_FORMAT_INTL_MM, PLYWOOD_FORMAT_BR_MM)

    def format_label(self) -> str:
        """Retorna 'WIDTH x LENGTH mm' para uso em relatorios."""
        return f"{self.width_mm} x {self.length_mm} mm"


def default_plywood_spec(thickness_mm: float = 18.0) -> PlywoodSpec:
    """Helper para criar PlywoodSpec padrao (1220 x 2440 / espessura indicada)."""
    return PlywoodSpec(thickness_mm=thickness_mm)
