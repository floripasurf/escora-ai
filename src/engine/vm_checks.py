"""Verificacoes auxiliares do grid de VMs (cortante e emendas de compensado).

Extraido de ``vm_grid_builder`` para manter os modulos <500 linhas.

Pendencia 17 (manual §21 item 17 / NBR 15696 Anexo B e item 4.4): alem de
momento e flecha, cada VM deve ser verificada a CORTANTE, com valor
admissivel declarado pelo FABRICANTE. Quando o catalogo nao publica o
valor (caso VM80/VM130 Orguel/Mecanor — sem cortante publicado em ficha
tecnica, pesquisa 2026-06-11 sem fonte oficial), a verificacao e PULADA
(mesmo padrao backward-compat do EI/deflection: nunca inventar valor).

Valores rastreaveis conhecidos (Manual JAU p.20/33, manual §13.3):
- ALU14 / JAU VA140 (perfil identico): 2100 kgf = 20.6 kN
- JAU VA165: 3350 kgf ; JAU TJ3: 3160 kgf ; JAU PT2: 1978 kgf

Pendencia 18 (manual §11.2 / Orguel p.115): cada linha de emenda de
compensado exige +1 barrote (transpasse de barrotes lado a lado), MESMO
quando a emenda coincide com um barrote do grid regular.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple


def compute_segment_load_and_moment(
    span_m: float,
    q_kn_m: float,
    moment_adm_kn_m: float,
    ei_kn_m2: float,
    deflection_limit_denominator: int = 500,
) -> Tuple[float, float, float, float, bool, bool]:
    """Retorna (M, M_adm, flecha_mm, flecha_adm_mm, passes_M, passes_flecha).

    Manual §22.2 (M=qL²/8) + §22.3 (flecha = 5qL⁴/384EI). Extraido de
    ``vm_grid_builder`` (re-exportado la como ``_compute_segment_load_and_moment``
    para retro-compatibilidade com o pipeline).
    """
    M = q_kn_m * span_m * span_m / 8.0
    # Flecha bi-apoiada: f = 5qL^4 / (384 EI) -> em metros, converter mm
    if ei_kn_m2 > 0:
        flecha_m = 5 * q_kn_m * span_m ** 4 / (384.0 * ei_kn_m2)
    else:
        flecha_m = 0.0
    flecha_mm = flecha_m * 1000.0
    # Flecha admissivel: 1 + L/X (manual §22.3, NBR 15696 §4.3.2)
    flecha_adm_mm = 1.0 + (span_m * 1000.0) / deflection_limit_denominator
    passes_M = moment_adm_kn_m <= 0 or M <= moment_adm_kn_m
    passes_flecha = flecha_adm_mm <= 0 or flecha_mm <= flecha_adm_mm
    return M, moment_adm_kn_m, flecha_mm, flecha_adm_mm, passes_M, passes_flecha


def snapped_positions(lo: float, hi: float, origin: float, step: float) -> List[float]:
    """Posicoes >= lo, <= hi, snap-adas a ``origin + k * step`` (k inteiro).

    Manual §28.7 (2026-05-30): snap dos barrotes ao grid GLOBAL para
    eliminar sobreposicao entre lajes adjacentes.
    """
    if step <= 0 or hi - lo < step * 0.5:
        # Painel muito estreito: cair no comportamento anterior (2 pontos)
        return [lo, hi] if hi > lo else [lo]
    k_first = math.ceil((lo - origin) / step)
    k_last = math.floor((hi - origin) / step)
    positions = [origin + k * step for k in range(k_first, k_last + 1)]
    if not positions:
        # Bbox menor que step: ainda colocar 1 barrote no centro
        return [(lo + hi) / 2]
    return positions

# Coeficiente de cortante no apoio interno de viga continua de 2 vaos
# (caso mais desfavoravel entre isostatico V=qL/2 e continuo V=0.625qL —
# NBR 15696 Anexo B.2.1: adotar o pior entre os dois esquemas).
CONTINUOUS_SHEAR_COEF = 0.625
ISOSTATIC_SHEAR_COEF = 0.5


def compute_max_shear_kn(
    q_kn_m: float,
    span_m: float,
    continuous: bool = False,
) -> float:
    """Cortante maximo de viga sob carga distribuida.

    - Bi-apoiada (isostatica): V = q.L/2.
    - Continua (>= 3 apoios): V = 0.625.q.L no primeiro apoio interno
      (caso mais desfavoravel, NBR 15696 Anexo B).
    """
    coef = CONTINUOUS_SHEAR_COEF if continuous else ISOSTATIC_SHEAR_COEF
    return coef * q_kn_m * span_m


def check_shear(
    span_m: float,
    q_kn_m: float,
    shear_adm_kn: Optional[float],
    continuous: bool = False,
) -> Tuple[float, float, bool]:
    """Verifica cortante de um segmento de VM.

    Retorna ``(V_kn, V_adm_kn, passes)``.

    Backward compat (pendencia 17): se ``shear_adm_kn`` for None ou <= 0,
    o catalogo nao publica o valor -> verificacao PULADA (passes=True,
    V_adm registrado como 0.0). Nunca inventar valor de fabricante.
    """
    V = compute_max_shear_kn(q_kn_m, span_m, continuous)
    if shear_adm_kn is None or shear_adm_kn <= 0:
        return V, 0.0, True
    return V, shear_adm_kn, V <= shear_adm_kn


def seam_positions(
    lo: float,
    hi: float,
    sheet_length_m: float,
    tol: float = 1e-6,
) -> List[float]:
    """Posicoes das linhas de emenda de compensado dentro de ``(lo, hi)``.

    Pendencia 18 (manual §11.2 / Orguel p.115): as chapas sao assentadas a
    partir da borda do painel (``lo``); as emendas caem em multiplos do
    COMPRIMENTO da chapa: ``lo + k * sheet_length_m`` (k >= 1). Emendas
    coincidentes com a borda final (``hi``) nao contam (nao ha transpasse
    na borda da laje).
    """
    if sheet_length_m <= 0 or hi - lo <= sheet_length_m + tol:
        return []
    positions: List[float] = []
    k = 1
    while True:
        pos = lo + k * sheet_length_m
        if pos >= hi - tol:
            break
        positions.append(pos)
        k += 1
    return positions
