"""Capacidade derateada de escoras telescópicas por abertura real.

Escoras telescópicas comportam-se como colunas de Euler: P_crit ∝ 1/L².
A capacidade nominal (na mínima extensão) cai significativamente quando a
escora é estendida. Este módulo fornece tabelas de derating extraídas do
Manual Técnico Orguel e funções auxiliares para o cálculo adaptativo de
espaçamento.

Referências:
- Manual Técnico Orguel (p.35-40): tabelas de carga x abertura
- NBR 15696:2009: ações em fôrmas e escoramentos
"""

import math
from typing import Literal

from src.utils.constants import (
    GAMMA_CONCRETO, Q_FORMA_DEFAULT, Q_SOBRECARGA_DEFAULT, GAMMA_F,
    ESPACAMENTO_POR_ALTURA, ESPACAMENTO_MIN, GAMMA_M_ESCORAS_TORRES,
)


CapacityBasis = Literal["admissible", "characteristic"]


def design_capacity_kn(
    capacity_kn: float,
    capacity_basis: CapacityBasis = "admissible",
) -> float:
    """Capacidade de cálculo (Rd) de escora/torre conforme a base de entrada.

    NBR 15696 §4.3.1.2 (manual §3, pendência 27): gamma_m = 1.5 MINORA a
    resistência (Rd = Rk/1.5), aplicado simultaneamente com GAMMA_F = 1.4
    nas ações.

    NÃO DUPLA-CONTAR: as capacidades de catálogo (tabelas Orguel
    §13.1/§13.2) já são cargas ADMISSÍVEIS (ruptura ensaiada / coeficiente
    >= 2.0 do Anexo A) — para elas usar capacity_basis="admissible"
    (default), que retorna o valor inalterado. O gamma_m = 1.5 só se
    aplica quando a entrada for resistência CARACTERÍSTICA/de ruptura
    (capacity_basis="characteristic").
    """
    if capacity_basis == "characteristic":
        return capacity_kn / GAMMA_M_ESCORAS_TORRES
    if capacity_basis != "admissible":
        raise ValueError(
            f"capacity_basis inválido: {capacity_basis!r}. "
            "Use 'admissible' ou 'characteristic'."
        )
    return capacity_kn


def get_max_spacing_by_thickness(slab_thickness_m: float) -> float:
    """Retorna o espaçamento máximo (TETO) pela tabela ESPACAMENTO_POR_ALTURA.

    Se a espessura não cair em nenhuma faixa, retorna 1.10m (default).
    """
    thickness_cm = round(slab_thickness_m * 100)
    for (min_cm, max_cm), spacing in ESPACAMENTO_POR_ALTURA.items():
        if min_cm <= thickness_cm <= max_cm:
            return spacing
    return 1.10


def compute_adaptive_spacing(
    slab_thickness_m: float,
    floor_height_m: float,
    shore_capacity_kn: float,
    capacity_basis: CapacityBasis = "admissible",
) -> float:
    """Calcula espaçamento adaptativo baseado na carga real do projeto.

    Em vez de usar um espaçamento fixo (ESPACAMENTO_MAX_DEFAULT), calcula
    a área tributária que uma escora consegue suportar e deriva o espaçamento
    de um grid quadrado equivalente.

    Args:
        slab_thickness_m: Espessura da laje em metros.
        floor_height_m: Pé-direito do pavimento em metros (não usado diretamente
            no cálculo de carga, mas a capacidade da escora já é derateada
            pela altura antes de ser passada aqui).
        shore_capacity_kn: Capacidade efetiva da escora em kN, já derateada
            pela abertura real (via ShoreCatalogEntry.effective_capacity).
        capacity_basis: base da capacidade informada. "admissible" (default)
            para capacidades de catálogo (já admissíveis — Orguel §13.1/13.2,
            Anexo A); "characteristic" quando a entrada for resistência
            característica/de ruptura — nesse caso aplica-se Rd = Rk/1.5
            (gamma_m, NBR 15696 §4.3.1.2; manual §3, pendência 27).

    Returns:
        Espaçamento em metros, limitado pelo teto da tabela por espessura
        e pelo piso ESPACAMENTO_MIN.
    """
    shore_capacity_kn = design_capacity_kn(shore_capacity_kn, capacity_basis)

    # Carga por m² (kN/m²)
    peso_concreto = GAMMA_CONCRETO * slab_thickness_m
    carga_total = peso_concreto + Q_FORMA_DEFAULT + Q_SOBRECARGA_DEFAULT
    carga_majorada = carga_total * GAMMA_F

    if carga_majorada <= 0 or shore_capacity_kn <= 0:
        return get_max_spacing_by_thickness(slab_thickness_m)

    # Área tributária que uma escora suporta (m²)
    area_trib = shore_capacity_kn / carga_majorada

    # Espaçamento (grid quadrado): lado = sqrt(área)
    spacing = math.sqrt(area_trib)

    # Limitar pelo teto da tabela por espessura
    max_from_table = get_max_spacing_by_thickness(slab_thickness_m)
    spacing = min(spacing, max_from_table)

    # Piso: evitar acúmulo excessivo
    spacing = max(spacing, ESPACAMENTO_MIN)

    return round(spacing, 3)
