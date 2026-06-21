"""shore_reviewer: recálculo de carga não deve crashar com capacidade 0.

Bug visto no 101112 (diagnóstico codex): escora selecionada com
load_capacity_kn==0 → ZeroDivisionError em _recalc_*_loads (util = load/cap).
"""

from types import SimpleNamespace as NS

from src.engine.shore_reviewer import _recalc_beam_loads, _recalc_slab_loads


def _shore(cap):
    return NS(load_capacity_kn=cap)


def _pos():
    return NS(load_applied_kn=0.0, utilization_ratio=0.0)


def test_recalc_slab_loads_zero_capacity_no_crash():
    sr = NS(shores=[_pos()], total_load_kn=50.0, selected_shore=_shore(0.0))
    _recalc_slab_loads(sr)  # não pode levantar ZeroDivisionError
    assert sr.shores[0].utilization_ratio == 0.0


def test_recalc_beam_loads_zero_capacity_no_crash():
    br = NS(
        shores=[_pos()],
        beam=NS(length_m=5.0),
        total_linear_load_kn_m=10.0,
        selected_shore=_shore(0.0),
    )
    _recalc_beam_loads(br)  # não pode levantar ZeroDivisionError
    assert br.shores[0].utilization_ratio == 0.0


def test_recalc_slab_loads_normal_capacity_still_works():
    sr = NS(shores=[_pos()], total_load_kn=10.0, selected_shore=_shore(20.0))
    _recalc_slab_loads(sr)
    assert sr.shores[0].load_applied_kn == 10.0
    assert 0 < sr.shores[0].utilization_ratio <= 1.0
