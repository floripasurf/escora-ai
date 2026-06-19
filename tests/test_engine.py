"""Testes do módulo engine."""

import pytest
import math
from shapely.geometry import Polygon

from src.engine.load_calculator import (
    calculate_self_weight,
    calculate_live_load,
    calculate_total_load,
    calculate_linear_load,
)
from src.engine.shore_selector import load_catalog, select_shore
from src.engine.grid_distributor import distribute_shores, calculate_grid_dimensions
from src.engine.validator import validate_result
from src.models.slab import Slab
from src.utils.constants import GAMMA_CONCRETO, Q_SOBRECARGA_DEFAULT, GAMMA_F


@pytest.fixture
def simple_slab():
    """Laje retangular 4x6m, espessura 12cm."""
    polygon = Polygon([(0, 0), (6, 0), (6, 4), (0, 4)])
    return Slab.from_polygon(polygon, "LAJE_12CM", 0.12)


@pytest.fixture
def thick_slab():
    """Laje espessa 8x10m, espessura 25cm."""
    polygon = Polygon([(0, 0), (10, 0), (10, 8), (0, 8)])
    return Slab.from_polygon(polygon, "LAJE_25CM", 0.25)


@pytest.fixture
def catalog():
    return load_catalog()


class TestLoadCalculator:
    def test_self_weight(self, simple_slab):
        # 24m² × 0.12m × 25 kN/m³ = 72 kN
        weight = calculate_self_weight(simple_slab)
        assert weight == pytest.approx(72.0)

    def test_live_load(self, simple_slab):
        # NBR 15696 §4.2.e: sobrecarga minima 2.0 kN/m² (era 1.5; corrigido 2026-05-27).
        # 24m² × 2.0 kN/m² = 48 kN
        load = calculate_live_load(simple_slab)
        assert load == pytest.approx(48.0)

    def test_total_load(self, simple_slab):
        # (72 concreto + 12 forma + 48 sobrecarga) × 1.4 = 184.8 kN
        # (sobrecarga: 24m² × 2.0 kN/m² per NBR 15696)
        total = calculate_total_load(simple_slab)
        assert total == pytest.approx(184.8)

    def test_total_load_custom_sobrecarga(self, simple_slab):
        # (72 + 12 forma + 24×2.5) × 1.4 = (72 + 12 + 60) × 1.4 = 201.6 kN
        total = calculate_total_load(simple_slab, q_sobrecarga=2.5)
        assert total == pytest.approx(201.6)

    def test_linear_load(self):
        # (0.12 × 25 + 0.5 forma + 2.0) × 1.4 = (3.0 + 0.5 + 2.0) × 1.4 = 7.7 kN/m²
        # NBR 15696 §4.2.e: sobrecarga minima 2.0 kN/m²
        q = calculate_linear_load(0.12)
        assert q == pytest.approx(7.7)

    def test_thick_slab_self_weight(self, thick_slab):
        # 80m² × 0.25m × 25 kN/m³ = 500 kN
        weight = calculate_self_weight(thick_slab)
        assert weight == pytest.approx(500.0)


class TestShoreSelector:
    def test_load_catalog(self, catalog):
        assert len(catalog) >= 3

    def test_select_light_shore(self, catalog):
        shore = select_shore(catalog, required_height_m=2.8, required_capacity_kn=10.0)
        assert shore is not None
        assert shore.load_capacity_kn >= 10.0
        assert shore.height_min_m <= 2.8 <= shore.height_max_m

    def test_select_medium_shore(self, catalog):
        shore = select_shore(catalog, required_height_m=3.0, required_capacity_kn=18.0)
        assert shore is not None
        assert shore.load_capacity_kn >= 18.0

    def test_select_heavy_shore(self, catalog):
        # At 3.0m the heavy shore is not yet derated (curve starts at 3.0m/30kN)
        shore = select_shore(catalog, required_height_m=3.0, required_capacity_kn=25.0)
        assert shore is not None
        assert shore.effective_capacity(3.0) >= 25.0

    def test_select_most_economical(self, catalog):
        shore = select_shore(catalog, required_height_m=2.8, required_capacity_kn=5.0)
        assert shore is not None
        # Catalog atualizado §13.1: capacidades convertidas de kgf reais Orguel.
        # ESC2000-3100 a 2.80m capacidade 17.7 kN (legacy 15.0 era estimativa).
        # ESC Junior tem 11.3 kN mas e for_sale_only - nao selecionada.
        assert shore.load_capacity_kn >= 17.0  # tipo ESC2000-3100 ou similar

    def test_no_suitable_shore(self, catalog):
        shore = select_shore(catalog, required_height_m=2.8, required_capacity_kn=999.0)
        assert shore is None


class TestInventoryMode:
    @pytest.fixture
    def inv_no_esc310(self):
        from src.engine.inventory import InventoryAvailability
        return InventoryAvailability(
            locadora="Test",
            updated_at="2026-04-07",
            items={"ESC310": 0, "ESC450": 50, "ESC-PESADA": 5},
        )

    @pytest.fixture
    def inv_only_esc310(self):
        from src.engine.inventory import InventoryAvailability
        return InventoryAvailability(
            locadora="Test",
            updated_at="2026-04-07",
            items={"ESC310": 100, "ESC450": 0, "ESC-PESADA": 0},
        )

    @pytest.fixture
    def inv_no_towers(self):
        from src.engine.inventory import InventoryAvailability
        return InventoryAvailability(
            locadora="Test",
            updated_at="2026-04-07",
            items={"ESC310": 100, "ESC450": 50},
        )

    def test_select_shore_inventory_mode_skips_out_of_stock(
        self, catalog, inv_no_esc310,
    ):
        # height/load that ESC310 would otherwise satisfy as cheapest pick
        shore = select_shore(
            catalog,
            required_height_m=2.8,
            required_capacity_kn=8.0,
            mode="inventory",
            inventory=inv_no_esc310,
        )
        assert shore is not None
        assert shore.id != "ESC310"

    def test_select_shore_inventory_fallback_with_warning(
        self, catalog, inv_only_esc310, caplog,
    ):
        # Requires ESC450 height range, but only ESC310 is in stock
        with caplog.at_level("WARNING"):
            shore = select_shore(
                catalog,
                required_height_m=4.0,
                required_capacity_kn=10.0,
                mode="inventory",
                inventory=inv_only_esc310,
            )
        assert shore is not None
        assert any("Sem estoque" in rec.message for rec in caplog.records)

    def test_select_shore_inventory_matches_legacy_alias(
        self, catalog, inv_only_esc310, caplog,
    ):
        with caplog.at_level("WARNING"):
            shore = select_shore(
                catalog,
                required_height_m=2.8,
                required_capacity_kn=8.0,
                mode="inventory",
                inventory=inv_only_esc310,
            )
        assert shore is not None
        assert shore.id == "ESC2000-3100"
        assert not any("Sem estoque" in rec.message for rec in caplog.records)

    def test_decide_support_type_inventory_no_towers_falls_back_to_shores(
        self, catalog, inv_no_towers,
    ):
        from src.engine.tower_selector import decide_support_type
        from src.models.shore import SupportType

        # Heavy slab that would normally trigger MIXED (Rule 4, ≥20cm)
        # but no towers in inventory → falls back to TELESCOPIC.
        # Manual §8 (2026-05-27): pe-direito padrao expandido para 3.50m.
        # Usar 3.60m para garantir bypass de Rule 0.
        support, fraction, reasons, _rule = decide_support_type(
            required_height_m=3.60,
            load_per_point_kn=10.0,
            slab_thickness_m=0.25,
            slab_area_m2=60.0,
            element_type="slab",
            shore_catalog=catalog,
            mode="inventory",
            inventory=inv_no_towers,
        )
        assert support == SupportType.TELESCOPIC
        assert fraction == 0.0
        assert any("Sem torres em estoque" in r for r in reasons)


class TestGridDistributor:
    def test_grid_dimensions_small(self):
        nx, ny, sx, sy = calculate_grid_dimensions(4.0, 6.0, max_spacing=1.5)
        assert nx >= 2
        assert ny >= 2
        assert sx <= 1.5
        assert sy <= 1.5

    def test_grid_dimensions_large(self):
        nx, ny, sx, sy = calculate_grid_dimensions(10.0, 8.0, max_spacing=1.5)
        assert nx >= 7
        assert ny >= 6
        assert sx <= 1.5
        assert sy <= 1.5

    def test_distribute_simple_slab(self, simple_slab, catalog):
        shore = catalog[0]  # Escora Leve
        total_load = 151.2  # kN

        shores, nx, ny, sx, sy = distribute_shores(
            simple_slab, shore, total_load, max_spacing=1.5
        )

        assert len(shores) == nx * ny
        assert len(shores) > 0
        assert sx <= 1.5
        assert sy <= 1.5

        # Todas as escoras dentro da bounding box
        bb = simple_slab.bounding_box
        for s in shores:
            assert bb.min_x <= s.x <= bb.max_x
            assert bb.min_y <= s.y <= bb.max_y


class TestValidator:
    def test_valid_result(self, simple_slab, catalog):
        shore = select_shore(catalog, 2.8, 10.0)
        shores, nx, ny, sx, sy = distribute_shores(
            simple_slab, shore, 151.2, max_spacing=1.5
        )

        is_valid, errors = validate_result(shores, sx, sy, max_spacing=1.5)
        assert is_valid
        assert len(errors) == 0

    def test_empty_shores(self):
        is_valid, errors = validate_result([], 1.0, 1.0)
        assert not is_valid
        assert any("Nenhuma escora" in e for e in errors)


class TestDerating:
    def test_effective_capacity_interpolates(self, catalog):
        # Manual §13.1 (2026-05-28): ESC310 renomeado para ESC2000-3100.
        # Capacidades atualizadas para valores reais Orguel p.11:
        # 2.00m = 3200 kgf = 31.4 kN; 2.50m = 2250 kgf = 22.1 kN; 3.10m = 1500 kgf = 14.7 kN
        esc310 = next(s for s in catalog if s.matches_id("ESC310"))
        # Exact curve points
        assert esc310.effective_capacity(2.00) == pytest.approx(31.4)
        assert esc310.effective_capacity(2.50) == pytest.approx(22.1)
        assert esc310.effective_capacity(3.10) == pytest.approx(14.7)
        # Midpoint between 2.00 (31.4) and 2.10 (28.0): 2.05 → 29.7
        assert esc310.effective_capacity(2.05) == pytest.approx(29.7, rel=1e-3)
        # Clamping above range
        assert esc310.effective_capacity(3.50) == pytest.approx(14.7)
        # Clamping below range
        assert esc310.effective_capacity(1.50) == pytest.approx(31.4)

    def test_select_shore_respects_derating(self, catalog):
        # At 4.4 m with 15 kN load, ESC450 derated ≈ 9 kN → must not be returned.
        shore = select_shore(catalog, required_height_m=4.4, required_capacity_kn=15.0)
        assert shore is None or shore.id != "ESC450"
        # ESC-PESADA at 4.4m is ≈ 14.4 kN → still not enough at 15 kN.
        # Any returned shore must actually satisfy the derated capacity.
        if shore is not None:
            assert shore.effective_capacity(4.4) >= 15.0

    def test_decide_support_type_escalates_to_tower_by_load(self, catalog):
        from src.engine.tower_selector import decide_support_type
        from src.models.shore import SupportType

        # 4.4 m, 12 kN/point → no shore can take 12 × 1.4 = 16.8 kN at 4.4m
        support, fraction, reasons, _rule = decide_support_type(
            required_height_m=4.4,
            load_per_point_kn=12.0,
            slab_thickness_m=0.12,
            element_type="slab",
            shore_catalog=catalog,
        )
        assert support == SupportType.TOWER
        assert fraction == 1.0
        assert any("derateada" in r for r in reasons)

        # 2.8 m, 8 kN → well within ESC310/ESC450 capacity → telescopic
        support, fraction, reasons, _rule = decide_support_type(
            required_height_m=2.8,
            load_per_point_kn=8.0,
            slab_thickness_m=0.12,
            element_type="slab",
            shore_catalog=catalog,
        )
        assert support == SupportType.TELESCOPIC
        assert fraction == 0.0

    def test_decide_support_type_beam_short_light_is_telescopic(self, catalog):
        from src.engine.tower_selector import decide_support_type
        from src.models.shore import SupportType

        # Short beam, light load, thin slab (12cm < 15cm threshold):
        # No mixed support triggered → pure telescopic.
        support, fraction, _, _rule = decide_support_type(
            required_height_m=2.6,
            load_per_point_kn=6.0,
            slab_thickness_m=0.12,
            span_m=4.0,
            element_type="beam",
            shore_catalog=catalog,
        )
        assert support == SupportType.TELESCOPIC
        assert fraction == 0.0

    def test_decide_support_type_mixed_beam_thick_slab(self, catalog):
        from src.engine.tower_selector import decide_support_type
        from src.models.shore import SupportType

        # Beam with thick slab (≥15cm) → MIXED ~35% towers
        # Manual §8 (2026-05-27): Rule 0 expandido para 3.50m, usar 3.60m.
        support, fraction, reasons, _rule = decide_support_type(
            required_height_m=3.60,
            load_per_point_kn=8.0,
            slab_thickness_m=0.18,
            span_m=5.0,
            element_type="beam",
            shore_catalog=catalog,
        )
        assert support == SupportType.MIXED
        assert 0.0 < fraction < 1.0
        assert any("mista" in r.lower() or "misto" in r.lower() for r in reasons)

    def test_decide_support_type_mixed_slab_thick(self, catalog):
        from src.engine.tower_selector import decide_support_type
        from src.models.shore import SupportType

        # Thick slab ≥20cm → MIXED ~18% towers (not pure TOWER)
        # Manual §8 (2026-05-27): Rule 0 expandido para 3.50m, usar 3.60m.
        support, fraction, reasons, _rule = decide_support_type(
            required_height_m=3.60,
            load_per_point_kn=8.0,
            slab_thickness_m=0.22,
            element_type="slab",
            slab_area_m2=30.0,
            shore_catalog=catalog,
        )
        assert support == SupportType.MIXED
        assert 0.10 <= fraction <= 0.25
        assert any("misto" in r.lower() for r in reasons)

    def test_decide_support_type_mixed_slab_large_area(self, catalog):
        from src.engine.tower_selector import decide_support_type
        from src.models.shore import SupportType

        # Large slab ≥40m² with thin slab → MIXED ~15% towers
        # Manual §8 (2026-05-27): Rule 0 expandido para 3.50m, usar 3.60m.
        support, fraction, reasons, _rule = decide_support_type(
            required_height_m=3.60,
            load_per_point_kn=5.0,
            slab_thickness_m=0.12,
            element_type="slab",
            slab_area_m2=55.0,
            shore_catalog=catalog,
        )
        assert support == SupportType.MIXED
        assert 0.10 <= fraction <= 0.20
        assert any("misto" in r.lower() for r in reasons)

    def test_decide_support_type_pure_tower_height(self, catalog):
        from src.engine.tower_selector import decide_support_type
        from src.models.shore import SupportType

        # Manual §8 (2026-05-28): bloqueio acima de 4.50m e CONDICIONAL ao
        # catalogo. ESC-PESADA (legado) cobre 5.0m; ESC-ESTENDIDA esta
        # disabled. Usar 6.0m garante que nenhuma escora cobre -> TOWER.
        support, fraction, reasons, _rule = decide_support_type(
            required_height_m=6.0,
            load_per_point_kn=8.0,
            slab_thickness_m=0.12,
            element_type="slab",
            shore_catalog=catalog,
        )
        assert support == SupportType.TOWER
        assert fraction == 1.0


class TestCruzetaBom:
    def _accs(self):
        from src.models.shore import AccessoryCatalogEntry
        return [
            AccessoryCatalogEntry(
                id="CRZ-ESC310", category="cruzeta",
                manufacturer="Mecanor", model="Cruzeta ESC310",
                associated_model_ids=["ESC310", "ESC360"],
                weight_kg=3.4, price_brl=6.5,
            ),
            AccessoryCatalogEntry(
                id="CRZ-ESC450", category="cruzeta",
                manufacturer="Mecanor", model="Cruzeta ESC450",
                associated_model_ids=["ESC450"],
                weight_kg=4.6, price_brl=8.2,
            ),
            AccessoryCatalogEntry(
                id="CRZ-TORRE", category="cruzeta",
                manufacturer="Orguel", model="Cruzeta TA",
                associated_model_ids=["TWR-TA100", "TWR-TA150"],
                weight_kg=5.8, price_brl=11.0,
            ),
        ]

    def test_compute_cruzeta_bom_telescopic_only(self):
        from src.engine.tower_selector import compute_cruzeta_bom, count_cruzetas_laje
        slab_cruzetas = count_cruzetas_laje({"ESC310": 100, "ESC450": 40})
        result = compute_cruzeta_bom(
            self._accs(),
            beam_cruzeta_counts={},
            slab_cruzeta_counts=slab_cruzetas,
            tower_count=0,
        )
        by_id = {acc.id: qty for acc, qty in result}
        assert by_id["CRZ-ESC310"] == 25
        assert by_id["CRZ-ESC450"] == 10
        assert "CRZ-TORRE" not in by_id

    def test_compute_cruzeta_bom_with_towers(self):
        from src.engine.tower_selector import compute_cruzeta_bom
        result = compute_cruzeta_bom(
            self._accs(),
            beam_cruzeta_counts={},
            slab_cruzeta_counts={"ESC310": 0},
            tower_count=5,
        )
        by_id = {acc.id: qty for acc, qty in result}
        assert by_id["CRZ-TORRE"] == 20
        assert "CRZ-ESC310" not in by_id

    def test_load_tower_catalog_returns_accessories(self):
        from src.engine.tower_selector import load_tower_catalog
        towers, beams, accessories = load_tower_catalog()
        assert len(towers) > 0
        assert len(beams) > 0
        cruzetas = [a for a in accessories if a.category == "cruzeta"]
        assert len(cruzetas) == 3
        assert {c.id for c in cruzetas} == {"CRZ-ESC310", "CRZ-ESC450", "CRZ-TORRE"}
