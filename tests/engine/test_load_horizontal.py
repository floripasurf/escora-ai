"""Tests — pendência 24 (esforço horizontal + bomba de concreto, NBR 15696
§4.2.l) e pendência 27 (gamma_m = 1.5 via capacity_basis em shore_capacity).
"""

import pytest

from src.engine.load_calculator import (
    PUMP_DYNAMIC_PENDENCY,
    HorizontalLoadResult,
    horizontal_load_kn,
)
from src.engine.shore_capacity import (
    compute_adaptive_spacing,
    design_capacity_kn,
)
from src.utils.constants import ESFORCO_HORIZONTAL_FRACAO, GAMMA_M_ESCORAS_TORRES


# ─── Pendência 24: esforço horizontal 5% + efeito dinâmico de bomba ────

class TestHorizontalLoad:
    def test_basic_5_percent(self):
        """Sem bomba: H = 5% da carga vertical (NBR 15696 §4.2.l)."""
        result = horizontal_load_kn(100.0)
        assert result.load_kn == pytest.approx(5.0)
        assert result.pendencias == ()

    def test_uses_constant_fraction(self):
        result = horizontal_load_kn(42.0)
        assert result.load_kn == pytest.approx(42.0 * ESFORCO_HORIZONTAL_FRACAO)

    def test_zero_vertical_load(self):
        result = horizontal_load_kn(0.0)
        assert result.load_kn == 0.0
        assert result.pendencias == ()

    def test_pump_dynamic_added(self):
        """Com bomba quantificada: SOMA o efeito dinâmico aos 5%."""
        result = horizontal_load_kn(100.0, has_pump=True, pump_dynamic_kn=3.0)
        assert result.load_kn == pytest.approx(5.0 + 3.0)
        assert result.pendencias == ()

    def test_pump_without_value_raises_pendency(self):
        """Bomba sem valor: NÃO inventar default — registrar pendência."""
        result = horizontal_load_kn(100.0, has_pump=True)
        assert result.load_kn == pytest.approx(5.0)
        assert result.pendencias == (PUMP_DYNAMIC_PENDENCY,)

    def test_pump_value_ignored_without_pump(self):
        """pump_dynamic_kn só entra quando has_pump=True."""
        result = horizontal_load_kn(100.0, has_pump=False, pump_dynamic_kn=3.0)
        assert result.load_kn == pytest.approx(5.0)
        assert result.pendencias == ()

    def test_negative_vertical_raises(self):
        with pytest.raises(ValueError):
            horizontal_load_kn(-1.0)

    def test_negative_pump_raises(self):
        with pytest.raises(ValueError):
            horizontal_load_kn(100.0, has_pump=True, pump_dynamic_kn=-2.0)

    def test_result_is_immutable(self):
        result = horizontal_load_kn(10.0)
        assert isinstance(result, HorizontalLoadResult)
        with pytest.raises(Exception):
            result.load_kn = 99.0


# ─── Pendência 27: Rd = Rk/1.5 só para resistência característica ──────

class TestDesignCapacityBasis:
    def test_admissible_unchanged(self):
        """Capacidade de catálogo (já admissível) NÃO recebe gamma_m de novo."""
        assert design_capacity_kn(30.0) == 30.0
        assert design_capacity_kn(30.0, "admissible") == 30.0

    def test_characteristic_divided_by_gamma_m(self):
        """Resistência característica/de ruptura: Rd = Rk / 1.5."""
        assert design_capacity_kn(30.0, "characteristic") == pytest.approx(
            30.0 / GAMMA_M_ESCORAS_TORRES
        )

    def test_invalid_basis_raises(self):
        with pytest.raises(ValueError):
            design_capacity_kn(30.0, "rupture")

    def test_adaptive_spacing_characteristic_tighter(self):
        """capacity_basis='characteristic' reduz a capacidade → espaçamento
        menor ou igual ao do mesmo valor tratado como admissível."""
        kwargs = dict(slab_thickness_m=0.30, floor_height_m=2.8)
        s_adm = compute_adaptive_spacing(shore_capacity_kn=10.0, **kwargs)
        s_chr = compute_adaptive_spacing(
            shore_capacity_kn=10.0, capacity_basis="characteristic", **kwargs
        )
        assert s_chr <= s_adm
        # Razão de espaçamentos (não saturados) = sqrt(1/1.5)
        assert s_chr == pytest.approx(s_adm / (GAMMA_M_ESCORAS_TORRES ** 0.5), abs=0.01)

    def test_adaptive_spacing_default_is_admissible(self):
        kwargs = dict(slab_thickness_m=0.30, floor_height_m=2.8)
        assert compute_adaptive_spacing(
            shore_capacity_kn=10.0, **kwargs
        ) == compute_adaptive_spacing(
            shore_capacity_kn=10.0, capacity_basis="admissible", **kwargs
        )
