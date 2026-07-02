"""Calculadora de fundações para alvenaria estrutural MCMV.

Dois tipos suportados:
1. Sapata corrida — padrão para MCMV térreo em solo razoável
2. Radier — alternativa para solos fracos ou quando a sapata ficaria muito larga

Referências:
- NBR 6122:2019 — Projeto e execução de fundações
- NBR 6118:2023 — Projeto de estruturas de concreto

Verificacao de tensao no apoio (manual §4 / Orguel p.25):
- Torre de escoramento:  >= 16.53 kgf/cm² na placa-base
- ESC2000-3100:          >= 26.45 kgf/cm² na placa-base
- ESC3000-4500:          >= 17.35 kgf/cm² na placa-base
"""

import logging
import math
from dataclasses import dataclass
from typing import List, Literal, Optional

from src.models.masonry import Foundation, FoundationType, FloorPlan
from src.utils.masonry_constants import (
    SOLO_CAPACIDADE_PADRAO,
    SAPATA_LARGURA_MIN, SAPATA_PROFUNDIDADE_MIN, SAPATA_ALTURA_MIN,
    SAPATA_ARMADURA_PADRAO,
    RADIER_ESPESSURA_MIN, RADIER_ARMADURA_PADRAO,
)

logger = logging.getLogger(__name__)


# Tensoes minimas no apoio (kgf/cm²) - manual §4 / Orguel p.25
# Valores ja convertidos: 1 kN = 101.97 kgf, 1 m² = 10000 cm²
SUPPORT_STRESS_MIN_KGF_CM2 = {
    "torre": 16.53,
    "ESC2000-3100": 26.45,
    "ESC3000-4500": 17.35,
    # Aliases legados (manual §13.1)
    "ESC310": 26.45,
    "ESC450": 17.35,
    # Default conservador (usa o maior)
    "DEFAULT": 26.45,
}


@dataclass(frozen=True)
class SupportStressCheck:
    """Resultado da verificacao de tensao no apoio de uma escora/torre."""
    support_type: str           # "torre", "ESC2000-3100", etc.
    model_id: str               # ID do modelo (ex: "ESC2000-3100")
    load_kn: float              # Carga aplicada (kN, ja majorada)
    base_area_cm2: float        # Area de contato da placa-base (cm²)
    stress_kgf_cm2: float       # Tensao aplicada (kgf/cm²)
    stress_min_kgf_cm2: float   # Tensao minima requerida (manual §4)
    passes: bool                # True se solo/apoio resiste
    margin: float               # stress_min - stress (negativo = falha)
    note: str = ""              # Observacao para relatorio


def _resolve_support_min_stress(support_type: str, model_id: str) -> float:
    """Resolve a tensao minima requerida pelo tipo/modelo de apoio."""
    if model_id and model_id in SUPPORT_STRESS_MIN_KGF_CM2:
        return SUPPORT_STRESS_MIN_KGF_CM2[model_id]
    if support_type and support_type.lower() in SUPPORT_STRESS_MIN_KGF_CM2:
        return SUPPORT_STRESS_MIN_KGF_CM2[support_type.lower()]
    # Default conservador
    return SUPPORT_STRESS_MIN_KGF_CM2["DEFAULT"]


def check_support_stress(
    support_type: Literal["torre", "telescopic"],
    model_id: str,
    load_kn: float,
    base_plate_mm: float,
    base_shape: Literal["square", "circle"] = "square",
    sapata_area_cm2: Optional[float] = None,
) -> SupportStressCheck:
    """Verifica se a tensao no apoio supera a minima requerida (manual §4).

    Args:
        support_type: "torre" ou "telescopic".
        model_id: ID do modelo (ex: "ESC2000-3100", "ESC3000-4500", "TWR-TA150").
        load_kn: Carga aplicada na escora/torre (kN, ja com gamma_f).
        base_plate_mm: Lado da placa-base (ou diametro se circular), em mm.
        base_shape: "square" (padrao Orguel) ou "circle".
        sapata_area_cm2: Se fornecido, sobrescreve a area calculada da
            placa-base (ex: quando se usa sapata distribuidora maior).

    Returns:
        SupportStressCheck com a tensao calculada, requerida e se passa.

    Manual §4 / Orguel p.25:
        torre = 16.53 kgf/cm²
        ESC2000-3100 = 26.45 kgf/cm²
        ESC3000-4500 = 17.35 kgf/cm²
    """
    # Area de contato (cm²)
    if sapata_area_cm2 is not None:
        area_cm2 = sapata_area_cm2
        note = f"Area da sapata distribuidora: {area_cm2:.1f} cm²"
    else:
        side_cm = base_plate_mm / 10.0
        if base_shape == "circle":
            area_cm2 = math.pi * (side_cm / 2.0) ** 2
            note = f"Placa circular φ={side_cm:.1f}cm → A={area_cm2:.1f} cm²"
        else:
            area_cm2 = side_cm * side_cm
            note = f"Placa quadrada {side_cm:.1f}x{side_cm:.1f}cm → A={area_cm2:.1f} cm²"

    # Converte carga: 1 kN = 101.97 kgf
    load_kgf = load_kn * 101.97
    stress_kgf_cm2 = load_kgf / area_cm2 if area_cm2 > 0 else float("inf")

    stress_min = _resolve_support_min_stress(support_type, model_id)
    passes = stress_kgf_cm2 <= stress_min  # tensao aplicada deve estar abaixo da maxima

    margin = stress_min - stress_kgf_cm2

    return SupportStressCheck(
        support_type=support_type,
        model_id=model_id,
        load_kn=round(load_kn, 2),
        base_area_cm2=round(area_cm2, 1),
        stress_kgf_cm2=round(stress_kgf_cm2, 2),
        stress_min_kgf_cm2=stress_min,
        passes=passes,
        margin=round(margin, 2),
        note=note,
    )


def required_sapata_area_cm2(
    support_type: str,
    model_id: str,
    load_kn: float,
    safety_factor: float = 1.0,
) -> float:
    """Calcula a area minima de sapata distribuidora para atender §4.

    A = (load_kgf * safety_factor) / stress_min_kgf_cm2

    Args:
        support_type: "torre" ou "telescopic".
        model_id: ID do modelo de escora/torre.
        load_kn: Carga aplicada (kN, ja com gamma_f).
        safety_factor: Coeficiente adicional (1.0 = NBR; >1.0 = mais conservador).

    Returns:
        Area minima da sapata em cm².
    """
    load_kgf = load_kn * 101.97
    stress_min = _resolve_support_min_stress(support_type, model_id)
    return (load_kgf * safety_factor) / stress_min


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
