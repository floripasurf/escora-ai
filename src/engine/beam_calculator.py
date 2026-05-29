"""Cálculo de escoramento para vigas conforme NBR 15696:2009 e NBR 6120:2019."""

import math
from typing import List, Optional, Tuple
from src.models.shore import ShoreCatalogEntry, PositionedShore
from src.utils.constants import (
    GAMMA_CONCRETO, Q_SOBRECARGA_DEFAULT, Q_FORMA_DEFAULT, GAMMA_F,
    ESPACAMENTO_MIN, ESPACAMENTO_MAX_VIGA, CONTRA_FLECHA,
)


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
    q_forma: float = Q_FORMA_DEFAULT,
    gamma_f: float = GAMMA_F,
) -> float:
    """
    Carga linear total majorada sobre a viga (kN/m).

    Inclui (NBR 6120:2019 + NBR 15696:2009):
    - Peso próprio da viga (concreto armado 25 kN/m³)
    - Carga da laje transferida (faixa de influência)
    - Peso próprio das fôrmas (0.5 kN/m²)
    - Sobrecarga de trabalho (operários + equipamentos)
    """
    g_viga = calculate_beam_self_weight(width_m, height_m)
    g_laje_transfer = slab_thickness_m * GAMMA_CONCRETO * influence_width_m
    g_forma = q_forma * influence_width_m
    q_transfer = q_sobrecarga * influence_width_m

    return (g_viga + g_laje_transfer + g_forma + q_transfer) * gamma_f


def _split_into_spans(
    beam_length_m: float,
    support_positions: List[float],
    is_cantilever_start: bool,
    is_cantilever_end: bool,
) -> List[Tuple[float, float, bool, bool]]:
    """Split a beam into independent spans between supports.

    Returns list of (start, end, is_cant_start, is_cant_end) tuples.
    Each span is treated independently for shore distribution.

    A 15m beam with supports at [0, 5, 10, 15] produces 3 spans:
    (0, 5, False, False), (5, 10, False, False), (10, 15, False, False)
    """
    if not support_positions:
        return [(0.0, beam_length_m, is_cantilever_start, is_cantilever_end)]

    # Deduplicate and sort supports, clamp to beam range
    supports = sorted(set(
        max(0.0, min(beam_length_m, sp)) for sp in support_positions
    ))

    # Build span boundaries: [0, support1, support2, ..., beam_length]
    boundaries = []
    if supports[0] > 0.01:  # beam starts before first support
        boundaries.append(0.0)
    boundaries.extend(supports)
    if supports[-1] < beam_length_m - 0.01:  # beam extends past last support
        boundaries.append(beam_length_m)

    if len(boundaries) < 2:
        return [(0.0, beam_length_m, is_cantilever_start, is_cantilever_end)]

    spans = []
    for i in range(len(boundaries) - 1):
        span_start = boundaries[i]
        span_end = boundaries[i + 1]
        span_len = span_end - span_start
        if span_len < 0.10:  # skip negligible spans
            continue

        # Cantilever flags: first span inherits start, last inherits end
        cant_start = is_cantilever_start if span_start < 0.01 else False
        cant_end = is_cantilever_end if span_end > beam_length_m - 0.01 else False

        spans.append((span_start, span_end, cant_start, cant_end))

    return spans if spans else [(0.0, beam_length_m, is_cantilever_start, is_cantilever_end)]


def _distribute_single_span(
    span_start: float,
    span_end: float,
    is_cant_start: bool,
    is_cant_end: bool,
    max_spacing: float,
) -> List[float]:
    """Distribute shore positions along a single span (relative to beam start).

    Returns absolute positions along the beam axis.
    """
    DIST_MIN_APOIO = 0.70
    span_len = span_end - span_start

    n = math.ceil(span_len / max_spacing) + 1
    n = max(n, 2)
    spacing = span_len / (n - 1)

    # Generate candidate positions (absolute along beam)
    candidates = []
    for i in range(n):
        pos = span_start + i * spacing
        candidates.append(pos)

    # Filter positions too close to span boundaries (which are supports)
    filtered = []
    for pos in candidates:
        # Distance to start support (skip if cantilever — no support there)
        if not is_cant_start and abs(pos - span_start) < DIST_MIN_APOIO:
            continue
        # Distance to end support (skip if cantilever — no support there)
        if not is_cant_end and abs(pos - span_end) < DIST_MIN_APOIO:
            continue
        filtered.append(pos)
    candidates = filtered

    # Cantilever: ensure shore near free end
    if is_cant_start and candidates:
        if candidates[0] > span_start + 0.20:
            candidates.insert(0, span_start + 0.10)
    if is_cant_end and candidates:
        if candidates[-1] < span_end - 0.20:
            candidates.append(span_end - 0.10)

    # Enforce minimum inter-shore spacing
    if len(candidates) > 1:
        candidates.sort()
        spaced = [candidates[0]]
        for pos in candidates[1:]:
            if pos - spaced[-1] >= ESPACAMENTO_MIN:
                spaced.append(pos)
        candidates = spaced

    return candidates


def distribute_beam_shores(
    beam_length_m: float,
    beam_width_m: float,
    beam_height_m: float,
    shore: ShoreCatalogEntry,
    total_linear_load_kn_m: float,
    max_spacing: float = ESPACAMENTO_MAX_VIGA,
    start_x: float = 0.0,
    start_y: float = 0.0,
    direction: str = "x",
    support_positions: List[float] = None,
    is_cantilever_start: bool = False,
    is_cantilever_end: bool = False,
    forced_positions: Optional[List[float]] = None,
) -> Tuple[List[PositionedShore], int, float]:
    """
    Distribui escoras ao longo de uma viga conforme NBR 6118/15696.

    Multi-span aware: splits beam at support positions and distributes
    shores independently per span, then merges results.

    Args:
        forced_positions: posições (m ao longo da viga) onde é obrigatório
            existir uma escora — usadas para garantir escora em interseções
            de viga sem pilar (regra Orguel Q3/A4). Se já houver escora
            próxima (< ESPACAMENTO_MIN), a posição é descartada.

    Retorna: (shores, n_shores, spacing_efetivo)
    """
    total_load = total_linear_load_kn_m * beam_length_m

    # Split beam into independent spans
    spans = _split_into_spans(
        beam_length_m,
        support_positions or [],
        is_cantilever_start,
        is_cantilever_end,
    )

    # Distribute shores per span, collect all positions
    all_positions: List[float] = []
    for span_start, span_end, cant_s, cant_e in spans:
        span_positions = _distribute_single_span(
            span_start, span_end, cant_s, cant_e, max_spacing,
        )
        all_positions.extend(span_positions)

    # Merge forced positions (e.g. beam intersections without pillar).
    # Only injected if not already within ESPACAMENTO_MIN of an existing shore.
    if forced_positions:
        for fp in forced_positions:
            fp_clamped = max(0.0, min(beam_length_m, fp))
            if all_positions and min(
                abs(fp_clamped - p) for p in all_positions
            ) < ESPACAMENTO_MIN - 1e-6:
                continue
            all_positions.append(fp_clamped)

    # Deduplicate positions that are too close (from adjacent spans).
    # Use small tolerance to avoid floating-point edge cases at boundaries.
    if all_positions:
        all_positions.sort()
        deduped = [all_positions[0]]
        for pos in all_positions[1:]:
            if pos - deduped[-1] >= ESPACAMENTO_MIN - 1e-6:
                deduped.append(pos)
        all_positions = deduped

    if not all_positions:
        # Fallback: all candidate positions were filtered out (proximity to
        # supports). Place at least 1 shore at beam midpoint — a beam always
        # needs shoring regardless of support proximity rules.
        all_positions = [beam_length_m / 2.0]

    # Calculate load per shore based on total count
    n_effective = len(all_positions)
    load_per_shore = total_load / n_effective

    # Rule 14 (Orguel manual, NBR 6120 — continuous beam on 3 supports):
    # central support reaction = 10/8·q·L vs 1.0·q·L in biapoiado analysis.
    # Practical effect: shore closest to the central apoio must be dimensioned
    # for 25% more load. Applied ONLY for exactly 3 supports (confirmed scope).
    central_support_x: Optional[float] = None
    if support_positions and len(support_positions) == 3:
        sorted_sp = sorted(
            max(0.0, min(beam_length_m, sp)) for sp in support_positions
        )
        central_support_x = sorted_sp[1]

    shores: List[PositionedShore] = []
    central_shore_idx: Optional[int] = None
    if central_support_x is not None:
        central_shore_idx = min(
            range(len(all_positions)),
            key=lambda i: abs(all_positions[i] - central_support_x),
        )

    for i, pos in enumerate(all_positions):
        if direction == "x":
            x = start_x + pos
            y = start_y
        else:
            x = start_x
            y = start_y + pos

        # Rule 14 amplification for the shore nearest the central apoio
        shore_load = load_per_shore
        if i == central_shore_idx:
            shore_load = load_per_shore * 10.0 / 8.0
        utilization = shore_load / shore.load_capacity_kn

        shores.append(
            PositionedShore(
                x=round(x, 4),
                y=round(y, 4),
                shore=shore,
                load_applied_kn=round(shore_load, 2),
                utilization_ratio=round(utilization, 4),
            )
        )

    actual_spacing = beam_length_m / max(n_effective - 1, 1)
    return shores, n_effective, actual_spacing


def estimate_beam_shore_height(pe_direito_m: float, beam_height_m: float) -> float:
    """
    Altura efetiva da escora sob uma viga.
    A escora vai do piso até o fundo da viga.
    """
    return pe_direito_m - beam_height_m


# Limites de flecha admissivel por faixa de vao — manual §22.3 (Orguel p.81)
# Formula geral NBR 15696 §4.3.2: u_lim = 1 + L/500 (mm).
# Tabela de denominadores adotados pela Orguel para vaos curtos a medios:
DEFLECTION_LIMIT_RANGES = [
    (2.00, 400),   # L <= 2.00 m
    (2.50, 415),   # 2.00 < L <= 2.50 m
    (2.75, 423),   # 2.50 < L <= 2.75 m
    (3.00, 429),   # 2.75 < L <= 3.00 m
]


def deflection_limit_denominator(span_m: float) -> int:
    """Retorna o denominador X tal que flecha admissivel = L/X.

    Para vaos acima de 3.00 m adota o limite generico NBR 15696 (L/500).
    Manual §22.3.
    """
    for upper, denom in DEFLECTION_LIMIT_RANGES:
        if span_m <= upper:
            return denom
    return 500


def compute_max_span_bar(m_adm_kgf_m: float, point_load_kgf: float) -> float:
    """Vao maximo do barrote para carga concentrada no meio do vao.

    Manual §22.2 (Orguel p.72):
        M_max = P * L / 4
        L_max = 4 * M_adm / P
    """
    if point_load_kgf <= 0:
        return float("inf")
    return 4.0 * m_adm_kgf_m / point_load_kgf


def compute_max_span_by_moment(m_adm_kgf_m: float, q_kgf_m: float, n_apoios: int = 2) -> float:
    """Vao maximo por momento, viga bi-apoiada ou continua (3+ apoios).

    Manual §22.3:
        Bi-apoiada:   L_max = sqrt(8 * M_adm / q)
        3+ apoios:    L_max = sqrt(10 * M_adm / q)  (momento maximo no apoio)
    """
    if q_kgf_m <= 0:
        return float("inf")
    coef = 8.0 if n_apoios <= 2 else 10.0
    return math.sqrt(coef * m_adm_kgf_m / q_kgf_m)


def compute_max_span_by_deflection(
    ei_kgf_m2: float,
    q_kgf_m: float,
    n_apoios: int = 2,
    deflection_denominator: Optional[int] = None,
) -> float:
    """Vao maximo por verificacao de flecha.

    Manual §22.3:
        Bi-apoiada:   L_max = (384 * E.I / (5 * q * X))^(1/3)
        3+ apoios:    L_max = (581 * E.I / (4 * q * X))^(1/3)

    Onde X e o denominador do limite de flecha L/X. Se nao fornecido,
    aplica iterativamente a tabela DEFLECTION_LIMIT_RANGES.
    """
    if q_kgf_m <= 0 or ei_kgf_m2 <= 0:
        return float("inf")

    if deflection_denominator is not None:
        coef_num, coef_den = (384.0, 5.0) if n_apoios <= 2 else (581.0, 4.0)
        return (coef_num * ei_kgf_m2 / (coef_den * q_kgf_m * deflection_denominator)) ** (1.0 / 3.0)

    # Iterativo: comecar com L/500 e ajustar pelo denominador correto
    L = 5.0  # chute inicial
    for _ in range(6):
        denom = deflection_limit_denominator(L)
        coef_num, coef_den = (384.0, 5.0) if n_apoios <= 2 else (581.0, 4.0)
        L_new = (coef_num * ei_kgf_m2 / (coef_den * q_kgf_m * denom)) ** (1.0 / 3.0)
        if abs(L_new - L) < 0.01:
            return L_new
        L = L_new
    return L


def compute_max_beam_span(
    m_adm_kgf_m: float,
    ei_kgf_m2: float,
    q_kgf_m: float,
    n_apoios: int = 2,
) -> Tuple[float, str]:
    """Vao maximo verificando momento E flecha; adotar o menor.

    Manual §22.3 / §22.6: a regra obriga verificar ambos e adotar o menor
    resultado. Retorna (L_max, criterio_dominante).
    """
    L_moment = compute_max_span_by_moment(m_adm_kgf_m, q_kgf_m, n_apoios)
    L_deflection = compute_max_span_by_deflection(ei_kgf_m2, q_kgf_m, n_apoios)
    if L_moment <= L_deflection:
        return L_moment, "momento"
    return L_deflection, "flecha"


def compute_guide_moment(q_kgf_m: float, span_m: float) -> float:
    """Momento maximo de guia bi-apoiada submetida a carga distribuida.

    Manual §22.5: M = q * L^2 / 8.
    """
    return q_kgf_m * span_m * span_m / 8.0
