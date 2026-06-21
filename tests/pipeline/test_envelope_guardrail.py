"""Normalização da métrica kg/m³ (follow-up).

kg/m³ NÃO é mais gate de requires_review — a banda [12,16]/[8,20] não casa com a
base do motor (vertical-only / volume escorado; até CFL=6.7, CVS=5.1 ficam
abaixo). Vira diagnóstico (`consumption_diagnostics`). requires_review fica só
para casos inequívocos (BLOCKED/SPECIAL_REVIEW via routing, e resultado vazio
via `degenerate_result_review_reason`).
"""

from types import SimpleNamespace as NS

from src.pipeline.runner import (
    consumption_diagnostics,
    degenerate_result_review_reason,
)


def _result(n_shores=0, weight=0.0, area=0.0, shore_count=None):
    return NS(
        shores=[NS() for _ in range(n_shores)],
        shore_count=(shore_count if shore_count is not None else n_shores),
        shores_weight_kg=weight,
        area_m2=area,
    )


def _calc(volume_m3, slabs=(), beams=()):
    return NS(total_volume_m3=volume_m3, slab_results=list(slabs), beam_results=list(beams))


# --- Diagnóstico (sem alarme, base honesta) ---

def test_consumption_diagnostics_values_and_basis():
    calc = _calc(100.0, slabs=[_result(n_shores=50, weight=600.0, area=60.0)])
    d = consumption_diagnostics(calc)
    assert d["basis"] == "vertical_shores_over_shored_volume"
    assert d["vertical_kg_m3"] == 6.0                 # 600 / 100 (volume escorado)
    assert d["total_shores"] == 50
    # nomes explícitos: área é só de lajes, peso/escoras inclui vigas (#3 codex)
    assert d["shores_per_slab_m2"] == round(50 / 60, 3)
    assert d["vertical_kg_per_slab_m2"] == round(600 / 60, 2)
    assert d["total_volume_m3"] == 100.0


def test_consumption_diagnostics_none_calc():
    assert consumption_diagnostics(None) == {}


def test_consumption_diagnostics_zero_volume_safe():
    d = consumption_diagnostics(_calc(0.0, slabs=[_result(n_shores=1, weight=10.0, area=1.0)]))
    assert d["vertical_kg_m3"] is None  # não divide por zero
    assert d["total_shores"] == 1


# --- Resultado vazio / 0 escoras (ex.: 110749) — esse SIM continua gate ---

def test_degenerate_zero_volume_flags():
    assert degenerate_result_review_reason(_calc(0.0)) is not None


def test_degenerate_no_results_flags():
    assert degenerate_result_review_reason(_calc(100.0)) is not None


def test_degenerate_real_result_not_flagged_even_if_shore_count_zero():
    # Regressão 105475: tem volume, peso e 36 escoras na lista, mas shore_count=0.
    calc = _calc(1484.7, slabs=[_result(n_shores=36, weight=5686.0, shore_count=0)])
    assert degenerate_result_review_reason(calc) is None


def test_degenerate_shores_but_zero_weight_flags():
    # Gap codex #4 (ex.: 101112 = 225 escoras, peso 0 por catálogo/inventário):
    # escoras posicionadas mas peso/BOM não calculável → revisão.
    calc = _calc(100.0, slabs=[_result(n_shores=225, weight=0.0, area=60.0)])
    reason = degenerate_result_review_reason(calc)
    assert reason is not None
    assert "peso" in reason.lower() or "bom" in reason.lower()


def test_degenerate_none_calc_no_flag():
    assert degenerate_result_review_reason(None) is None
