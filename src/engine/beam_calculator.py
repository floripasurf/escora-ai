"""Cálculo de escoramento para vigas conforme NBR 15696:2009 e NBR 6120:2019."""

import math
from typing import List, Tuple
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
) -> Tuple[List[PositionedShore], int, float]:
    """
    Distribui escoras ao longo de uma viga conforme NBR 6118/15696.

    Multi-span aware: splits beam at support positions and distributes
    shores independently per span, then merges results.

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

    # Deduplicate positions that are too close (from adjacent spans)
    if all_positions:
        all_positions.sort()
        deduped = [all_positions[0]]
        for pos in all_positions[1:]:
            if pos - deduped[-1] >= ESPACAMENTO_MIN:
                deduped.append(pos)
        all_positions = deduped

    if not all_positions:
        return [], 0, 0.0

    # Calculate load per shore based on total count
    n_effective = len(all_positions)
    load_per_shore = total_load / n_effective
    utilization = load_per_shore / shore.load_capacity_kn

    shores: List[PositionedShore] = []
    for pos in all_positions:
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

    actual_spacing = beam_length_m / max(n_effective - 1, 1)
    return shores, n_effective, actual_spacing


def estimate_beam_shore_height(pe_direito_m: float, beam_height_m: float) -> float:
    """
    Altura efetiva da escora sob uma viga.
    A escora vai do piso até o fundo da viga.
    """
    return pe_direito_m - beam_height_m
