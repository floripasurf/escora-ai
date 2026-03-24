"""Cálculo de cargas conforme NBR 15696:2009."""

from src.models.slab import Slab
from src.utils.constants import GAMMA_CONCRETO, Q_SOBRECARGA_DEFAULT, GAMMA_F


def calculate_self_weight(slab: Slab) -> float:
    """
    Peso próprio da laje (kN).
    P = A × e × γ_concreto
    """
    return slab.area_m2 * slab.thickness_m * GAMMA_CONCRETO


def calculate_live_load(slab: Slab, q_sobrecarga: float = Q_SOBRECARGA_DEFAULT) -> float:
    """
    Sobrecarga de trabalho (kN).
    Q = A × q_sobrecarga
    """
    return slab.area_m2 * q_sobrecarga


def calculate_total_load(
    slab: Slab,
    q_sobrecarga: float = Q_SOBRECARGA_DEFAULT,
    gamma_f: float = GAMMA_F,
) -> float:
    """
    Carga total majorada (kN).
    P_total = (P_proprio + Q_sobrecarga) × γ_f
    """
    self_weight = calculate_self_weight(slab)
    live_load = calculate_live_load(slab, q_sobrecarga)
    return (self_weight + live_load) * gamma_f


def calculate_linear_load(
    thickness_m: float,
    q_sobrecarga: float = Q_SOBRECARGA_DEFAULT,
    gamma_f: float = GAMMA_F,
) -> float:
    """
    Carga linear por m² (kN/m²) — usada para calcular espaçamento.
    q = (e × γ_concreto + q_sobrecarga) × γ_f
    """
    return (thickness_m * GAMMA_CONCRETO + q_sobrecarga) * gamma_f
