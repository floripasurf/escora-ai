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
        # 24m² × 1.5 kN/m² = 36 kN
        load = calculate_live_load(simple_slab)
        assert load == pytest.approx(36.0)

    def test_total_load(self, simple_slab):
        # (72 concreto + 12 forma + 36 sobrecarga) × 1.4 = 168.0 kN
        total = calculate_total_load(simple_slab)
        assert total == pytest.approx(168.0)

    def test_total_load_custom_sobrecarga(self, simple_slab):
        # (72 + 12 forma + 24×2.5) × 1.4 = (72 + 12 + 60) × 1.4 = 201.6 kN
        total = calculate_total_load(simple_slab, q_sobrecarga=2.5)
        assert total == pytest.approx(201.6)

    def test_linear_load(self):
        # (0.12 × 25 + 0.5 forma + 1.5) × 1.4 = (3.0 + 0.5 + 1.5) × 1.4 = 7.0 kN/m²
        q = calculate_linear_load(0.12)
        assert q == pytest.approx(7.0)

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
        shore = select_shore(catalog, required_height_m=4.0, required_capacity_kn=25.0)
        assert shore is not None
        assert shore.load_capacity_kn >= 25.0

    def test_select_most_economical(self, catalog):
        shore = select_shore(catalog, required_height_m=2.8, required_capacity_kn=5.0)
        assert shore is not None
        # Should select lightest that fits
        assert shore.load_capacity_kn == 15.0

    def test_no_suitable_shore(self, catalog):
        shore = select_shore(catalog, required_height_m=2.8, required_capacity_kn=999.0)
        assert shore is None


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
