"""Guardrail: consumo kg/m³ fora de [12,16] exige revisão (AGENTS.md envelope).

O motor pode sub/superdimensionar (ex.: 105475=3.8, 35412=3.1, 59428=4.7 kg/m³).
Sem guardrail isso sai como job 'concluído' normal. Aqui validamos que esse
resultado passa a ser marcado para revisão, em vez de entregue como confiável.
"""

from types import SimpleNamespace

from src.pipeline.runner import (
    envelope_review_reason,
    degenerate_result_review_reason,
)


def _calc(volume_m3, slab_weights=(), beam_weights=()):
    return SimpleNamespace(
        total_volume_m3=volume_m3,
        slab_results=[SimpleNamespace(shores_weight_kg=w) for w in slab_weights],
        beam_results=[SimpleNamespace(shores_weight_kg=w) for w in beam_weights],
    )


def test_below_envelope_flags_review():
    # 105475 real: 5686 kg / 1484.7 m³ ≈ 3.8 kg/m³
    reason = envelope_review_reason(_calc(1484.7, slab_weights=[5686.0]))
    assert reason is not None
    assert "3.8" in reason
    assert "12" in reason and "16" in reason


def test_above_envelope_flags_review():
    reason = envelope_review_reason(_calc(100.0, slab_weights=[2000.0]))  # 20 kg/m³
    assert reason is not None
    assert "20" in reason


def test_within_envelope_no_review():
    # 1400 kg / 100 m³ = 14 kg/m³ → dentro de [12,16]
    assert envelope_review_reason(_calc(100.0, slab_weights=[1400.0])) is None


def test_no_volume_no_review():
    # volume 0 → indeterminado, não dá para avaliar envelope (não é o caso deste guard)
    assert envelope_review_reason(_calc(0.0, slab_weights=[1400.0])) is None


def test_no_weight_no_review():
    assert envelope_review_reason(_calc(100.0)) is None


def test_none_calculation_no_review():
    assert envelope_review_reason(None) is None


# --- Gap: resultado vazio / 0 escoras (ex.: 110749 = 0 lajes/0 vigas/0 volume) ---

def _result(n_shores=0, weight=0.0, shore_count=None):
    from types import SimpleNamespace as NS
    return NS(
        shores=[NS() for _ in range(n_shores)],
        shore_count=(shore_count if shore_count is not None else n_shores),
        shores_weight_kg=weight,
    )


def _calc_d(volume_m3, slabs=(), beams=()):
    from types import SimpleNamespace as NS
    return NS(total_volume_m3=volume_m3, slab_results=list(slabs), beam_results=list(beams))


def test_degenerate_zero_volume_flags():
    assert degenerate_result_review_reason(_calc_d(0.0)) is not None


def test_degenerate_no_results_flags():
    # volume > 0 mas nenhum painel/escora dimensionada (ex.: 110749)
    assert degenerate_result_review_reason(_calc_d(100.0)) is not None


def test_degenerate_real_result_not_flagged_even_if_shore_count_zero():
    # Regressão 105475: tem volume, peso e 36 escoras na lista, mas shore_count=0.
    # Não pode ser classificado como "vazio" (falso-positivo do diagnóstico codex).
    calc = _calc_d(1484.7, slabs=[_result(n_shores=36, weight=5686.0, shore_count=0)])
    assert degenerate_result_review_reason(calc) is None


def test_degenerate_none_calc_no_flag():
    assert degenerate_result_review_reason(None) is None
