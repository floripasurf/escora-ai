"""Tests for manual técnico Orguel audit — TIER 1 + TIER 2 corrections.

Covers:
- T1.1: Piso mínimo 4.0 kN/m² in calculate_linear_load
- T1.2: VM deflection check (dual moment + deflection)
- T1.3: Bonus hiperestático 25% for 3+ supports
- T1.4: Tower capacity derating by height
- T2.1: Cruzetas viga vs laje separation (already implemented, regression test)
- T2.5: Rule 14 central support × 10/8 (already implemented, regression test)
- T2.6: Consumption rate warnings (already implemented, regression test)
- T3.1: Secondary spacing table registration
"""

import math

from src.parser.region_filter import (
    _find_gap_splits, _is_in_detail_zone, DETAIL_EXCLUSION_RADIUS,
)
from src.engine.slab_builder import (
    _is_slab_layer, _points_to_polygon, MAX_SLAB_AREA,
    derive_slabs_from_boundaries,
)
from src.engine.load_calculator import (
    CARGA_PISO_MINIMO_KN_M2,
    calculate_linear_load,
)
from src.models.shore import (
    DistributionBeamEntry,
    TowerCatalogEntry,
)
from src.engine.tower_selector import (
    _passes_deflection_check,
    select_distribution_beam,
    select_tower,
    count_cruzetas_viga,
    count_cruzetas_laje,
    CRUZETA_VIGA_SPACING_M,
)
from src.utils.constants import ESPACAMENTO_SECUNDARIAS_MANUAL, GAMMA_F


# ─── Region Filter fixes ──────────────────────────────────────────────


class TestRegionFilterGapThreshold:
    def test_small_gaps_kept_together(self):
        """Limiar conservador 10%/5m (decisao 2026-04-09, mantida no
        codigo): gap de 300 em range 6000 NAO divide — plantas com
        patios/shafts/vaos internos longos devem permanecer uma regiao
        unica (caso CFL-SUB). Teste antigo esperava limiar de 3%, que
        contradiz a decisao documentada em _find_gap_splits."""
        values = list(range(0, 3000, 10)) + list(range(3300, 6000, 10))
        splits = _find_gap_splits(values, 6000.0)
        assert len(splits) == 0, "Gap de 300 < 10% de 6000 nao deve dividir"

    def test_large_gap_splits(self):
        """Gap acima de 10% do range divide regioes."""
        values = list(range(0, 2000, 10)) + list(range(3000, 6000, 10))
        splits = _find_gap_splits(values, 6000.0)
        assert len(splits) >= 1, "Gap de 1000 > 10% de 6000 deve dividir"

    def test_no_false_splits_on_continuous(self):
        """Continuous data with small gaps should NOT split."""
        values = list(range(0, 1000, 5))
        splits = _find_gap_splits(values, 1000.0)
        assert len(splits) == 0


class TestDetailExclusionRadius:
    def test_radius_is_8m(self):
        assert DETAIL_EXCLUSION_RADIUS == 8.0

    def test_entity_within_8m_excluded(self):
        """Entity 7m from a DETALHE label should be in detail zone."""
        from dataclasses import dataclass

        @dataclass
        class FakeText:
            content: str
            x: float
            y: float

        texts = [FakeText(content="DETALHE 01", x=100.0, y=100.0)]
        assert _is_in_detail_zone(107.0, 100.0, texts) is True

    def test_entity_beyond_8m_not_excluded(self):
        from dataclasses import dataclass

        @dataclass
        class FakeText:
            content: str
            x: float
            y: float

        texts = [FakeText(content="DETALHE 01", x=100.0, y=100.0)]
        assert _is_in_detail_zone(109.0, 100.0, texts) is False


# ─── Slab Builder fixes ──────────────────────────────────────────────


class TestSlabLargeAreaNotDropped:
    def test_1000m2_slab_passes(self):
        """1000m² slab should NOT be dropped (MAX now 2000)."""
        # 100m x 10m rectangle
        points = [(0, 0), (100, 0), (100, 10), (0, 10)]
        poly = _points_to_polygon(points)
        assert poly is not None
        assert abs(poly.area - 1000.0) < 1.0

    def test_2500m2_slab_dropped(self):
        """2500m² slab SHOULD be dropped (> 2000)."""
        points = [(0, 0), (50, 0), (50, 50), (0, 50)]
        poly = _points_to_polygon(points)
        assert poly is None

    def test_max_slab_area_is_2000(self):
        assert MAX_SLAB_AREA == 2000.0


class TestSlabCoberturaLayer:
    def test_cobertura_recognized(self):
        assert _is_slab_layer("COBERTURA") is True

    def test_cob_recognized(self):
        assert _is_slab_layer("COB-STRUCT") is True

    def test_estrutura_recognized(self):
        assert _is_slab_layer("ESTRUTURA-LAJE") is True

    def test_concreto_recognized(self):
        assert _is_slab_layer("CONCRETO") is True

    def test_pav_recognized(self):
        assert _is_slab_layer("PAV-01") is True

    def test_random_layer_rejected(self):
        assert _is_slab_layer("EIXOS") is False


class TestSlabNearClosedPolyline:
    def test_near_closed_polyline_accepted(self):
        """Polyline with first≈last (gap 0.05m) should be treated as closed."""
        polylines = [
            {
                "points": [(0, 0), (10, 0), (10, 5), (0.05, 0.05)],
                "layer": "LAJE",
                "is_closed": False,
            }
        ]
        result = derive_slabs_from_boundaries([], polylines)
        assert len(result) >= 1

    def test_open_polyline_rejected(self):
        """Polyline with large gap (>0.1m) and is_closed=False should be rejected."""
        polylines = [
            {
                "points": [(0, 0), (10, 0), (10, 5), (5, 5)],
                "layer": "LAJE",
                "is_closed": False,
            }
        ]
        result = derive_slabs_from_boundaries([], polylines)
        assert len(result) == 0


# ─── T1.1: Piso mínimo 4.0 kN/m² ──────────────────────────────────────

class TestLoadFloor:
    def test_normal_slab_no_floor_effect(self):
        """Laje 12cm: p_char = 0.12×25 + 0.50 + 2.0 = 5.5 > 4.0 → no floor.
        Sobrecarga atualizada para 2.0 kN/m² (NBR 15696 §4.2.e, 2026-05-27).
        """
        result = calculate_linear_load(0.12)
        expected = (0.12 * 25 + 0.50 + 2.0) * 1.4
        assert abs(result - expected) < 0.01

    def test_thin_slab_floor_applies(self):
        """Laje 2cm: p_char = 0.02×25 + 0.50 + 2.0 = 3.0 < 4.0 → floor at 4.0."""
        result = calculate_linear_load(0.02)
        expected = 4.0 * GAMMA_F
        assert abs(result - expected) < 0.01

    def test_zero_thickness_floor_applies(self):
        """Espessura 0: p_char = 0 + 0.50 + 2.0 = 2.5 < 4.0 → floor."""
        result = calculate_linear_load(0.0)
        assert abs(result - CARGA_PISO_MINIMO_KN_M2 * GAMMA_F) < 0.01

    def test_exact_floor_boundary(self):
        """p_char exactly 4.0 → should not change.
        e×25 + 0.50 + 2.0 = 4.0 → e = (4.0 - 2.5)/25 = 0.06
        """
        result = calculate_linear_load(0.06)
        expected = 4.0 * GAMMA_F
        assert abs(result - expected) < 0.01


# ─── T1.2: VM deflection check ─────────────────────────────────────────

def _make_beam(moment=5.0, max_span=3.0, ei=None, available=True):
    return DistributionBeamEntry(
        id="VD-TEST",
        manufacturer="Test",
        model="TEST",
        height_mm=130,
        moment_capacity_knm=moment,
        max_span_m=max_span,
        weight_per_m_kg=6.5,
        price_per_m_brl=8.0,
        available=available,
        EI_knm2=ei,
    )


class TestVMDeflectionCheck:
    def test_no_ei_passes(self):
        """No EI data → deflection check skipped (backward compat)."""
        b = _make_beam(ei=None)
        assert _passes_deflection_check(b, 2.0, 10.0) is True

    def test_high_ei_passes(self):
        """High EI → deflection OK."""
        b = _make_beam(ei=1000.0)
        assert _passes_deflection_check(b, 1.0, 5.0) is True

    def test_low_ei_fails(self):
        """Very low EI with long span → deflection fails."""
        b = _make_beam(ei=10.0)
        # 5 * 20 * 3^4 / (384 * 10) = 5*20*81/3840 = 8100/3840 ≈ 2.109
        # f_max = 3.0 / 429 ≈ 0.007 → fails
        assert _passes_deflection_check(b, 3.0, 20.0) is False

    def test_vm80_typical_span(self):
        """VM80 at 1.5m span with typical slab load should pass."""
        b = _make_beam(moment=2.08, max_span=1.55, ei=146.8)
        # q = 7.0 kN/m (typical for 12cm slab)
        assert _passes_deflection_check(b, 1.5, 7.0) is True


class TestSelectDistributionBeamDualCheck:
    def test_rejects_beam_failing_deflection(self):
        """Beam that passes moment but fails deflection should be rejected
        from primary candidates — fallback picks by moment only."""
        weak_ei = _make_beam(moment=10.0, max_span=3.5, ei=5.0)  # very low EI
        strong_ei = _make_beam(moment=10.0, max_span=3.5, ei=500.0)
        strong_ei.id = "VD-STRONG"
        strong_ei.price_per_m_brl = 6.0  # cheaper than weak_ei

        result = select_distribution_beam(
            [weak_ei, strong_ei], span_m=3.0, load_kn_m=5.0
        )
        # Both pass moment, but weak_ei fails deflection → primary path selects strong_ei
        assert result is not None
        assert result.id == "VD-STRONG"

    def test_deflection_check_filters_primary(self):
        """When all beams fail deflection, fallback to moment-only."""
        weak = _make_beam(moment=10.0, max_span=3.5, ei=5.0)
        result = select_distribution_beam([weak], span_m=3.0, load_kn_m=5.0)
        # Falls through to moment-only fallback → still selected
        assert result is not None


# ─── T1.3: Bonus hiperestático 25% ─────────────────────────────────────

class TestHiperestaticBonus:
    def test_2_supports_uses_div8(self):
        """Default n_supports=2 → divisor=8."""
        b = _make_beam(moment=5.06, max_span=3.1, ei=461.8)
        # m_required = 10 * 2^2 / 8 = 5.0 → passes with 5.06
        result = select_distribution_beam([b], span_m=2.0, load_kn_m=10.0, n_supports=2)
        assert result is not None

    def test_3_supports_uses_div10(self):
        """n_supports=3 → divisor=10, allows longer spans."""
        b = _make_beam(moment=5.06, max_span=3.1, ei=461.8)
        # With /8: m_required = 10 * 2^2 / 8 = 5.0
        # With /10: m_required = 10 * 2^2 / 10 = 4.0 → easier to pass
        # Test: span where /8 fails but /10 passes
        # m_required(/8) = 10 * 2.1² / 8 = 5.5125 > 5.06 → FAIL
        # m_required(/10) = 10 * 2.1² / 10 = 4.41 < 5.06 → PASS
        result_2 = select_distribution_beam([b], span_m=2.1, load_kn_m=10.0, n_supports=2)
        result_3 = select_distribution_beam([b], span_m=2.1, load_kn_m=10.0, n_supports=3)
        assert result_2 is None  # fails with /8
        assert result_3 is not None  # passes with /10


# ─── T1.4: Tower capacity derating ─────────────────────────────────────

def _make_tower(capacity=200.0, curve=None, max_height=30.0, module_h=1.5):
    return TowerCatalogEntry(
        id="TWR-TEST",
        manufacturer="Test",
        model="TA-TEST",
        load_capacity_kn=capacity,
        module_height_m=module_h,
        base_dimension_m=1.54,
        max_height_m=max_height,
        weight_per_module_kg=38.0,
        price_per_module_brl=15.0,
        capacity_curve=curve,
    )


class TestTowerDerating:
    def test_no_curve_returns_static(self):
        t = _make_tower(capacity=200.0, curve=None)
        assert t.effective_capacity(10.0) == 200.0

    def test_curve_at_first_point(self):
        t = _make_tower(curve=[[1.5, 200.0], [30.0, 147.0]])
        assert t.effective_capacity(1.5) == 200.0

    def test_curve_at_last_point(self):
        t = _make_tower(curve=[[1.5, 200.0], [30.0, 147.0]])
        assert t.effective_capacity(30.0) == 147.0

    def test_curve_interpolation(self):
        t = _make_tower(curve=[[1.5, 200.0], [7.5, 177.0], [15.0, 167.0]])
        cap = t.effective_capacity(7.5)
        assert abs(cap - 177.0) < 0.1

    def test_curve_below_first_clamps(self):
        t = _make_tower(curve=[[1.5, 200.0], [30.0, 147.0]])
        assert t.effective_capacity(0.5) == 200.0

    def test_curve_above_last_clamps(self):
        t = _make_tower(curve=[[1.5, 200.0], [30.0, 147.0]])
        assert t.effective_capacity(50.0) == 147.0

    def test_select_tower_uses_effective_capacity(self):
        """Tower that passes statically but fails at height should be rejected."""
        # Tower with 200kN static but 147kN at 30m
        t_weak = _make_tower(
            capacity=200.0,
            curve=[[1.5, 200.0], [30.0, 147.0]],
            max_height=30.0,
        )
        # Need 160kN at 25m height
        # effective_capacity(25) ≈ 200 + (25-1.5)/(30-1.5)*(147-200) = 200 - 43.68 = 156.32
        # → fails for 160kN
        result = select_tower([t_weak], required_height_m=25.0, required_capacity_kn=160.0)
        assert result is None

    def test_select_tower_with_low_height_passes(self):
        """Same tower at low height passes (200kN > 160kN)."""
        t = _make_tower(
            capacity=200.0,
            curve=[[1.5, 200.0], [30.0, 147.0]],
            max_height=30.0,
        )
        result = select_tower([t], required_height_m=3.0, required_capacity_kn=160.0)
        assert result is not None


# ─── T2.1: Cruzetas separation (regression) ────────────────────────────

class TestCruzetaSeparation:
    def test_cruzeta_viga_by_spacing(self):
        """Viga 6m → ceil(6/0.80) = 8 cruzetas."""

        class FakeShore:
            id = "ESC310"

        class FakeBeam:
            length_m = 6.0

        class FakeBeamResult:
            selected_shore = FakeShore()
            beam = FakeBeam()

        counts = count_cruzetas_viga([FakeBeamResult()])
        assert counts["ESC310"] == math.ceil(6.0 / CRUZETA_VIGA_SPACING_M)

    def test_cruzeta_laje_by_ratio(self):
        """Laje: 100 escoras × 0.25 = 25 cruzetas."""
        counts = count_cruzetas_laje({"ESC310": 100})
        assert counts["ESC310"] == 25


# ─── T3.1: Secondary spacing table (canonical Orguel p.89 / manual §12.2) ──

class TestSecondarySpacingTable:
    def test_table_complete(self):
        """21 lajes × 7 compensados × 2 n_apoios = 294 entradas."""
        assert len(ESPACAMENTO_SECUNDARIAS_MANUAL) == 21 * 7 * 2

    def test_all_lajes_present(self):
        lajes = {k[0] for k in ESPACAMENTO_SECUNDARIAS_MANUAL}
        assert lajes == {
            8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20,
            22, 25, 28, 30, 35, 40, 50, 60, 80, 100,
        }

    def test_all_compensados_present(self):
        comps = {k[1] for k in ESPACAMENTO_SECUNDARIAS_MANUAL}
        assert comps == {12, 14, 15, 17, 18, 20, 21}

    def test_laje_12cm_compensado_18mm(self):
        """Tabela canônica §12.2: laje 12 / 18mm = 57/67 cm (era 0.54 — errado)."""
        assert ESPACAMENTO_SECUNDARIAS_MANUAL[(12, 18, 2)] == 0.57
        assert ESPACAMENTO_SECUNDARIAS_MANUAL[(12, 18, 4)] == 0.67

    def test_canonical_corner_cells(self):
        """Cantos da tabela canônica §12.2 (verificada célula a célula)."""
        assert ESPACAMENTO_SECUNDARIAS_MANUAL[(8, 12, 2)] == 0.42
        assert ESPACAMENTO_SECUNDARIAS_MANUAL[(8, 21, 4)] == 0.84
        assert ESPACAMENTO_SECUNDARIAS_MANUAL[(100, 12, 2)] == 0.22
        assert ESPACAMENTO_SECUNDARIAS_MANUAL[(100, 21, 4)] == 0.47

    def test_canonical_sample_cells(self):
        """Amostra de células do miolo da tabela §12.2."""
        assert ESPACAMENTO_SECUNDARIAS_MANUAL[(10, 14, 2)] == 0.47
        assert ESPACAMENTO_SECUNDARIAS_MANUAL[(15, 18, 2)] == 0.54
        assert ESPACAMENTO_SECUNDARIAS_MANUAL[(15, 18, 4)] == 0.63
        assert ESPACAMENTO_SECUNDARIAS_MANUAL[(20, 17, 2)] == 0.49
        assert ESPACAMENTO_SECUNDARIAS_MANUAL[(25, 18, 2)] == 0.49
        assert ESPACAMENTO_SECUNDARIAS_MANUAL[(30, 20, 4)] == 0.62
        assert ESPACAMENTO_SECUNDARIAS_MANUAL[(50, 15, 4)] == 0.41

    def test_thicker_slab_smaller_spacing(self):
        """Thicker slab → smaller (or equal) spacing, every column/apoios."""
        lajes = sorted({k[0] for k in ESPACAMENTO_SECUNDARIAS_MANUAL})
        for mm in (12, 14, 15, 17, 18, 20, 21):
            for n in (2, 4):
                vals = [ESPACAMENTO_SECUNDARIAS_MANUAL[(c, mm, n)] for c in lajes]
                assert vals == sorted(vals, reverse=True), (mm, n)

    def test_4_apoios_never_smaller_than_2(self):
        """4 apoios (3 vãos) → vão >= 2 apoios em todas as células."""
        for (laje, mm, n), v in ESPACAMENTO_SECUNDARIAS_MANUAL.items():
            if n == 2:
                assert ESPACAMENTO_SECUNDARIAS_MANUAL[(laje, mm, 4)] >= v


# ─── Pendência 27: coeficientes gamma ──────────────────────────────────

class TestGammaCoefficients:
    def test_gamma_m_escoras_torres_value(self):
        """gamma_m = 1.5 minora a resistência (NBR 15696 §4.3.1.2)."""
        from src.utils.constants import GAMMA_M_ESCORAS_TORRES
        assert GAMMA_M_ESCORAS_TORRES == 1.5

    def test_deprecated_alias_kept(self):
        """Alias antigo GAMMA_F_FLAMBAGEM não deve quebrar imports."""
        from src.utils.constants import GAMMA_F_FLAMBAGEM, GAMMA_M_ESCORAS_TORRES
        assert GAMMA_F_FLAMBAGEM is GAMMA_M_ESCORAS_TORRES

    def test_gamma_f_unchanged(self):
        """gamma_Q = 1.4 segue majorando ações (simultâneo, não alternativo)."""
        assert GAMMA_F == 1.4
