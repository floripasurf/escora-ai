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
    support_positions: List[float] = None,
    is_cantilever_start: bool = False,
    is_cantilever_end: bool = False,
) -> Tuple[List[PositionedShore], int, float]:
    """
    Distribui escoras ao longo de uma viga conforme NBR 6118/15696.

    Condições de contorno (NBR 6118):
    - Apoio (pilar ou cruzamento de viga): não posicionar escora no apoio
    - Balanço: extremidade livre precisa de escora próxima à ponta
    - O espaçamento é mais denso em trechos em balanço

    support_positions: coordenadas ao longo do eixo (em metros desde o início)
        onde há apoios (pilares ou cruzamento de vigas). Escoras não devem
        ser posicionadas a menos de 0.15m destes pontos.
    is_cantilever_start: início da viga é extremidade livre (balanço)
    is_cantilever_end: fim da viga é extremidade livre (balanço)

    Retorna: (shores, n_shores, spacing_efetivo)
    """
    DIST_MIN_APOIO = 0.15  # distância mínima entre escora e ponto de apoio

    n = math.ceil(beam_length_m / max_spacing) + 1
    n = max(n, 2)
    spacing = beam_length_m / (n - 1)

    total_load = total_linear_load_kn_m * beam_length_m

    # Gerar posições candidatas ao longo do eixo da viga
    candidates = []
    for i in range(n):
        pos = i * spacing  # posição relativa ao início da viga
        candidates.append(pos)

    # Filtrar posições que caem sobre pontos de apoio
    if support_positions:
        filtered = []
        for pos in candidates:
            on_support = False
            for sp in support_positions:
                if abs(pos - sp) < DIST_MIN_APOIO:
                    on_support = True
                    break
            if not on_support:
                filtered.append(pos)
        candidates = filtered

    # Para balanço: garantir escora próxima à extremidade livre
    # NBR 6118 — extremidade livre deve ter suporte (concreto fresco)
    if is_cantilever_start and candidates:
        if candidates[0] > 0.20:  # se a primeira escora está longe da ponta
            candidates.insert(0, 0.10)  # adicionar escora a 10cm da ponta
    if is_cantilever_end and candidates:
        if candidates[-1] < beam_length_m - 0.20:
            candidates.append(beam_length_m - 0.10)

    if not candidates:
        # Viga curta totalmente apoiada — sem necessidade de escoras
        return [], 0, 0.0

    # Recalcular carga por escora
    n_effective = len(candidates)
    load_per_shore = total_load / n_effective
    utilization = load_per_shore / shore.load_capacity_kn

    shores: List[PositionedShore] = []
    for pos in candidates:
        if direction == "x":
            x = start_x + pos
            y = start_y
        else:
            x = start_x
            y = start_y + pos

        shores.append(
            PositionedShore(
                x=round(x, 4),
                y=round(y, 4),
                shore=shore,
                load_applied_kn=round(load_per_shore, 2),
                utilization_ratio=round(utilization, 4),
            )
        )

    actual_spacing = spacing  # espaçamento nominal do grid
    return shores, n_effective, actual_spacing


def estimate_beam_shore_height(pe_direito_m: float, beam_height_m: float) -> float:
    """
    Altura efetiva da escora sob uma viga.
    A escora vai do piso até o fundo da viga.
    """
    return pe_direito_m - beam_height_m
