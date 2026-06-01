"""Cálculo de cargas conforme NBR 15696:2009 e NBR 6120:2019.

Contextos de carga (manual §3, §16):
    "concretagem":   sobrecarga 2.0 kN/m² (default — escoramento inicial).
    "plataforma":    sobrecarga 1.5 kN/m² (carga local de plataforma de
                     trabalho - aplicar apenas em zonas com plataforma).
    "reescoramento": sobrecarga 1.0 kN/m² (Anexo C.4.a - escoras
                     remanescentes durante construcao de niveis superiores).
    "flecha":        sobrecarga 1.0 kN/m² (§4.3.2 - verificacao de flecha
                     sem coeficiente de seguranca).
"""

from typing import Literal

from src.models.slab import Slab
from src.utils.constants import (
    GAMMA_CONCRETO, Q_SOBRECARGA_DEFAULT, Q_FORMA_DEFAULT, GAMMA_F,
    Q_PLATAFORMA_LOCAL_DEFAULT, Q_REESCORAMENTO_DEFAULT, Q_FLECHA_VERIFICACAO,
    CARGA_ESTATICA_MIN_TOTAL,
)


LoadContext = Literal["concretagem", "plataforma", "reescoramento", "flecha"]


_CONTEXT_TO_Q = {
    "concretagem": Q_SOBRECARGA_DEFAULT,
    "plataforma": Q_PLATAFORMA_LOCAL_DEFAULT,
    "reescoramento": Q_REESCORAMENTO_DEFAULT,
    "flecha": Q_FLECHA_VERIFICACAO,
}


def overload_for_context(context: LoadContext = "concretagem") -> float:
    """Retorna a sobrecarga (kN/m²) apropriada para o contexto.

    Manual §3 e §16. Contextos validos: "concretagem" (default, 2.0),
    "plataforma" (1.5), "reescoramento" (1.0), "flecha" (1.0).
    """
    if context not in _CONTEXT_TO_Q:
        raise ValueError(
            f"Contexto invalido: {context}. "
            f"Use: {list(_CONTEXT_TO_Q.keys())}"
        )
    return _CONTEXT_TO_Q[context]


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


def calculate_live_load(
    slab: Slab,
    q_sobrecarga: float | None = None,
    context: LoadContext = "concretagem",
) -> float:
    """
    Sobrecarga de trabalho (kN).
    Q = A × q_sobrecarga

    Se ``q_sobrecarga`` for fornecido, ele tem precedencia sobre o contexto.
    Caso contrario, usa o valor da NBR conforme contexto:
      - concretagem (default): 2.0 kN/m² (NBR 15696 §4.2.e)
      - plataforma: 1.5 kN/m² (§4.2.k)
      - reescoramento: 1.0 kN/m² (Anexo C.4.a)
      - flecha: 1.0 kN/m² (§4.3.2)
    """
    if q_sobrecarga is None:
        q_sobrecarga = overload_for_context(context)
    return slab.area_m2 * q_sobrecarga


def calculate_total_load(
    slab: Slab,
    q_sobrecarga: float | None = None,
    q_forma: float = Q_FORMA_DEFAULT,
    gamma_f: float = GAMMA_F,
    context: LoadContext = "concretagem",
) -> float:
    """
    Carga total majorada (kN) — NBR 15696:2009.
    P_total = (P_concreto + Q_forma + Q_sobrecarga) × γ_f

    Parametro ``context`` controla a sobrecarga aplicada (vide
    `overload_for_context`). ``q_sobrecarga`` explicito sobrescreve o
    contexto.
    """
    if q_sobrecarga is None:
        q_sobrecarga = overload_for_context(context)
    self_weight = calculate_self_weight(slab)
    formwork_weight = calculate_formwork_weight(slab, q_forma)
    live_load = calculate_live_load(slab, q_sobrecarga)
    return (self_weight + formwork_weight + live_load) * gamma_f


# Piso mínimo de carga (kN/m²) antes da majoração — NBR 15696:2009 §4.2.e
# (manual §3). "Carga estatica total nao pode ser inferior a 4.0 kN/m²"
# Tambem usado em manual p.31. Aliasing com CARGA_ESTATICA_MIN_TOTAL.
CARGA_PISO_MINIMO_KN_M2 = CARGA_ESTATICA_MIN_TOTAL


def calculate_linear_load(
    thickness_m: float,
    q_sobrecarga: float | None = None,
    q_forma: float = Q_FORMA_DEFAULT,
    gamma_f: float = GAMMA_F,
    context: LoadContext = "concretagem",
) -> float:
    """
    Carga linear por m² (kN/m²) — usada para calcular espaçamento.
    q = max(e × γ_concreto + q_forma + q_sobrecarga, 4.0) × γ_f

    NBR 15696 §4.2.e (manual p.31): piso mínimo de 4.0 kN/m² antes da
    majoração.

    Parametro ``context`` controla qual sobrecarga aplicar.
    """
    if q_sobrecarga is None:
        q_sobrecarga = overload_for_context(context)
    p_char = thickness_m * GAMMA_CONCRETO + q_forma + q_sobrecarga
    p_char = max(p_char, CARGA_PISO_MINIMO_KN_M2)
    return p_char * gamma_f
