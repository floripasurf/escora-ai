"""Cálculo de escoramento para vigas conforme NBR 15696:2009."""

import math
from typing import List, Tuple
from src.models.shore import ShoreCatalogEntry, PositionedShore
from src.utils.constants import GAMMA_CONCRETO, Q_SOBRECARGA_DEFAULT, GAMMA_F


def calculate_beam_self_weight(width_m: float, height_m: float) -> float:
    """
    Peso próprio da viga por metro linear (kN/m).
    G = b × h × γ_concreto
    """
    return width_m * height_m * GAMMA_CONCRETO


def calculate_beam_total_linear_load(
    width_m: float,
    height_m: float,
    slab_thickness_m: float = 0.12,
    influence_width_m: float = 1.5,
    q_sobrecarga: float = Q_SOBRECARGA_DEFAULT,
    gamma_f: float = GAMMA_F,
) -> float:
    """
    Carga linear total majorada sobre a viga (kN/m).

    Inclui:
    - Peso próprio da viga
    - Carga da laje transferida (faixa de influência)
    - Sobrecarga
    """
    g_viga = calculate_beam_self_weight(width_m, height_m)
    g_laje_transfer = slab_thickness_m * GAMMA_CONCRETO * influence_width_m
    q_transfer = q_sobrecarga * influence_width_m

    return (g_viga + g_laje_transfer + q_transfer) * gamma_f


def distribute_beam_shores(
    beam_length_m: float,
    beam_width_m: float,
    beam_height_m: float,
    shore: ShoreCatalogEntry,
    total_linear_load_kn_m: float,
    max_spacing: float = 1.0,
    start_x: float = 0.0,
    start_y: float = 0.0,
    direction: str = "x",
) -> Tuple[List[PositionedShore], int, float]:
    """
    Distribui escoras ao longo de uma viga.

    Retorna: (shores, n_shores, spacing_efetivo)
    """
    n = math.ceil(beam_length_m / max_spacing) + 1
    n = max(n, 2)
    spacing = beam_length_m / (n - 1)

    total_load = total_linear_load_kn_m * beam_length_m
    load_per_shore = total_load / n
    utilization = load_per_shore / shore.load_capacity_kn

    shores: List[PositionedShore] = []
    for i in range(n):
        if direction == "x":
            x = start_x + i * spacing
            y = start_y
        else:
            x = start_x
            y = start_y + i * spacing

        shores.append(
            PositionedShore(
                x=round(x, 4),
                y=round(y, 4),
                shore=shore,
                load_applied_kn=round(load_per_shore, 2),
                utilization_ratio=round(utilization, 4),
            )
        )

    return shores, n, spacing


def estimate_beam_shore_height(pe_direito_m: float, beam_height_m: float) -> float:
    """
    Altura efetiva da escora sob uma viga.
    A escora vai do piso até o fundo da viga.
    """
    return pe_direito_m - beam_height_m
