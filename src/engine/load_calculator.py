"""Cálculo de cargas conforme NBR 15696:2009 e NBR 6120:2019."""

from src.models.slab import Slab
from src.utils.constants import (
    GAMMA_CONCRETO, Q_SOBRECARGA_DEFAULT, Q_FORMA_DEFAULT, GAMMA_F,
)


def calculate_self_weight(slab: Slab) -> float:
    """
    Peso próprio da laje (kN).
    P = A × e × γ_concreto
    """
    return slab.area_m2 * slab.thickness_m * GAMMA_CONCRETO


def calculate_formwork_weight(slab: Slab, q_forma: float = Q_FORMA_DEFAULT) -> float:
    """
    Peso próprio do sistema de fôrmas (kN) — NBR 6120:2019.
    Q_forma = A × q_forma
    """
    return slab.area_m2 * q_forma


def calculate_live_load(slab: Slab, q_sobrecarga: float = Q_SOBRECARGA_DEFAULT) -> float:
    """
    Sobrecarga de trabalho (kN).
    Q = A × q_sobrecarga
    """
    return slab.area_m2 * q_sobrecarga


def calculate_total_load(
    slab: Slab,
    q_sobrecarga: float = Q_SOBRECARGA_DEFAULT,
    q_forma: float = Q_FORMA_DEFAULT,
    gamma_f: float = GAMMA_F,
) -> float:
    """
    Carga total majorada (kN) — NBR 15696:2009.
    P_total = (P_concreto + Q_forma + Q_sobrecarga) × γ_f
    """
    self_weight = calculate_self_weight(slab)
    formwork_weight = calculate_formwork_weight(slab, q_forma)
    live_load = calculate_live_load(slab, q_sobrecarga)
    return (self_weight + formwork_weight + live_load) * gamma_f


def calculate_linear_load(
    thickness_m: float,
    q_sobrecarga: float = Q_SOBRECARGA_DEFAULT,
    q_forma: float = Q_FORMA_DEFAULT,
    gamma_f: float = GAMMA_F,
) -> float:
    """
    Carga linear por m² (kN/m²) — usada para calcular espaçamento.
    q = (e × γ_concreto + q_forma + q_sobrecarga) × γ_f
    """
    return (thickness_m * GAMMA_CONCRETO + q_forma + q_sobrecarga) * gamma_f
