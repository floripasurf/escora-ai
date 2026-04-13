"""Calculadora de fundações para alvenaria estrutural MCMV.

Dois tipos suportados:
1. Sapata corrida — padrão para MCMV térreo em solo razoável
2. Radier — alternativa para solos fracos ou quando a sapata ficaria muito larga

Referências:
- NBR 6122:2019 — Projeto e execução de fundações
- NBR 6118:2023 — Projeto de estruturas de concreto
"""

import logging
import math
from typing import List

from src.models.masonry import Foundation, FoundationType, FloorPlan, Wall
from src.utils.masonry_constants import (
    SOLO_CAPACIDADE_PADRAO,
    SAPATA_LARGURA_MIN, SAPATA_PROFUNDIDADE_MIN, SAPATA_ALTURA_MIN,
    SAPATA_ARMADURA_PADRAO,
    RADIER_ESPESSURA_MIN, RADIER_ARMADURA_PADRAO,
    GAMMA_F,
)

logger = logging.getLogger(__name__)


def design_sapata_corrida(
    load_per_m_kn: float,
    soil_capacity_kpa: float = SOLO_CAPACIDADE_PADRAO,
    wall_thickness_m: float = 0.14,
) -> Foundation:
    """Dimensiona sapata corrida para uma parede.

    Largura mínima: B = N / (σ_adm × 1m)
    onde N = carga linear (kN/m) e σ_adm = capacidade do solo (kPa = kN/m²)

    Args:
        load_per_m_kn: Carga linear na base da parede (kN/m) — já majorada
        soil_capacity_kpa: Capacidade de suporte do solo (kPa)
        wall_thickness_m: Espessura da parede acima (m)

    Returns:
        Foundation dimensionada
    """
    # Largura necessária
    b_required = load_per_m_kn / soil_capacity_kpa

    # Mínimo = espessura da parede + 10cm de cada lado, ou SAPATA_LARGURA_MIN
    b_min = max(wall_thickness_m + 0.20, SAPATA_LARGURA_MIN)
    b = max(b_required, b_min)

    # Arredondar para cima em 5cm
    b = math.ceil(b * 20) / 20.0

    # Altura da sapata (mínimo 20cm, ou B/4 para sapatas largas)
    h = max(SAPATA_ALTURA_MIN, b / 4.0)
    h = math.ceil(h * 20) / 20.0

    # Armadura (simplificado — para MCMV a armadura mínima geralmente atende)
    rebar = SAPATA_ARMADURA_PADRAO
    if b > 0.60:
        rebar = "φ10c/15 transversal + φ8c/20 longitudinal"

    logger.info(
        f"Sapata corrida: B={b:.2f}m, H={h:.2f}m, "
        f"N={load_per_m_kn:.1f} kN/m, σ_solo={soil_capacity_kpa:.0f} kPa"
    )

    return Foundation(
        type=FoundationType.SAPATA_CORRIDA,
        width_m=b,
        depth_m=SAPATA_PROFUNDIDADE_MIN,
        height_m=h,
        soil_capacity_kpa=soil_capacity_kpa,
        load_per_m_kn=load_per_m_kn,
        rebar=rebar,
    )


def design_radier(
    total_load_kn: float,
    area_m2: float,
    soil_capacity_kpa: float = SOLO_CAPACIDADE_PADRAO,
) -> Foundation:
    """Dimensiona radier (laje de fundação) quando sapata corrida não é viável.

    Verificação: σ_atuante = N / A ≤ σ_adm

    Args:
        total_load_kn: Carga total do edifício (kN) — já majorada
        area_m2: Área da edificação (m²)
        soil_capacity_kpa: Capacidade de suporte do solo (kPa)

    Returns:
        Foundation dimensionada
    """
    # Pressão atuante
    sigma = total_load_kn / area_m2 if area_m2 > 0 else 0

    if sigma > soil_capacity_kpa:
        logger.warning(
            f"Radier: σ={sigma:.1f} kPa > σ_adm={soil_capacity_kpa:.0f} kPa. "
            "Solo pode ser insuficiente."
        )

    # Espessura do radier
    espessura = max(RADIER_ESPESSURA_MIN, 0.15)
    if total_load_kn > 200:
        espessura = 0.20  # reforçar para cargas maiores

    # Largura = lado do radier (quadrado aproximado)
    lado = math.sqrt(area_m2)

    return Foundation(
        type=FoundationType.RADIER,
        width_m=round(lado, 2),
        depth_m=0.30,  # profundidade de assentamento
        height_m=espessura,
        soil_capacity_kpa=soil_capacity_kpa,
        load_per_m_kn=total_load_kn / (4 * lado) if lado > 0 else 0,
        rebar=RADIER_ARMADURA_PADRAO,
    )


def design_foundations(
    floor_plan: FloorPlan,
    soil_capacity_kpa: float = SOLO_CAPACIDADE_PADRAO,
) -> List[Foundation]:
    """Projeta fundações para todas as paredes estruturais.

    Estratégia:
    - Se todas as sapatas cabem dentro de largura razoável (< 0.80m): sapata corrida
    - Se alguma sapata excede 0.80m: considerar radier

    Args:
        floor_plan: Planta com cargas já calculadas
        soil_capacity_kpa: Capacidade do solo

    Returns:
        Lista de Foundation (uma por parede, ou uma única se radier)
    """
    foundations = []
    max_width = 0.0
    total_load = 0.0

    for wall in floor_plan.walls:
        if not wall.is_structural:
            continue

        load = wall.load_kn_per_m
        total_load += load * wall.length_m

        sapata = design_sapata_corrida(
            load_per_m_kn=load,
            soil_capacity_kpa=soil_capacity_kpa,
            wall_thickness_m=wall.thickness_m,
        )
        max_width = max(max_width, sapata.width_m)
        foundations.append(sapata)

    # Se sapata ficou muito larga, sugerir radier (mas manter sapatas calculadas)
    if max_width > 0.80:
        logger.info(
            f"Sapata mais larga: {max_width:.2f}m > 0.80m — "
            "considerar radier como alternativa"
        )
        area = floor_plan.width_m * floor_plan.depth_m
        radier = design_radier(total_load, area, soil_capacity_kpa)
        # Prepend radier as first option
        foundations.insert(0, radier)

    return foundations
