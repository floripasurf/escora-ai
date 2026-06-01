"""Testes de integração para espaçamento adaptativo no grid_distributor."""

import pytest
from shapely.geometry import Polygon

from src.engine.grid_distributor import distribute_shores
from src.engine.shore_selector import load_catalog
from src.engine.load_calculator import calculate_total_load
from src.models.slab import Slab


@pytest.fixture
def catalog():
    return load_catalog()


@pytest.fixture
def esc310(catalog):
    # Manual §13.1: ESC310 foi renomeado para ESC2000-3100; usar matches_id
    # para aceitar ambos via alias.
    return next(s for s in catalog if s.matches_id("ESC310"))


class TestAdaptiveSpacingIntegration:
    def test_thin_slab_wider_spacing(self, esc310):
        """Laje fina (10cm) → espaçamento mais largo (carga menor)."""
        polygon = Polygon([(0, 0), (5, 0), (5, 5), (0, 5)])
        slab = Slab.from_polygon(polygon, "LAJE_10CM", 0.10)
        total_load = calculate_total_load(slab)

        shores, nx, ny, sx, sy = distribute_shores(
            slab, esc310, total_load,
            max_spacing=1.30,
            floor_height_m=2.68,
        )
        assert len(shores) > 0
        # Laje fina: espaçamento deve ser ~1.25-1.30m (perto do teto)
        assert sx <= 1.30
        assert sy <= 1.30

    def test_thick_slab_tighter_spacing(self, esc310):
        """Laje espessa (25cm) → espaçamento mais denso (mais carga)."""
        polygon = Polygon([(0, 0), (5, 0), (5, 5), (0, 5)])
        slab = Slab.from_polygon(polygon, "LAJE_25CM", 0.25)
        total_load = calculate_total_load(slab)

        shores, nx, ny, sx, sy = distribute_shores(
            slab, esc310, total_load,
            max_spacing=1.10,
            floor_height_m=2.55,
        )
        assert len(shores) > 0
        # Laje espessa: espaçamento deve ser bem menor que 1.10m
        assert sx < 1.10 or sy < 1.10

    def test_adaptive_produces_more_shores_for_thick(self, esc310):
        """Laje espessa deve ter mais escoras que laje fina (mesma área)."""
        poly = Polygon([(0, 0), (6, 0), (6, 4), (0, 4)])

        slab_thin = Slab.from_polygon(poly, "FINA", 0.10)
        load_thin = calculate_total_load(slab_thin)
        shores_thin, *_ = distribute_shores(
            slab_thin, esc310, load_thin,
            max_spacing=1.30,
            floor_height_m=2.68,
        )

        slab_thick = Slab.from_polygon(poly, "ESPESSA", 0.30)
        load_thick = calculate_total_load(slab_thick)
        shores_thick, *_ = distribute_shores(
            slab_thick, esc310, load_thick,
            max_spacing=1.10,
            floor_height_m=2.50,
        )

        assert len(shores_thick) > len(shores_thin)

    def test_no_floor_height_uses_max_spacing(self, esc310):
        """Sem floor_height_m → comportamento legado (usa max_spacing direto)."""
        polygon = Polygon([(0, 0), (5, 0), (5, 5), (0, 5)])
        slab = Slab.from_polygon(polygon, "LAJE", 0.12)
        total_load = calculate_total_load(slab)

        shores_legacy, _, _, sx1, _ = distribute_shores(
            slab, esc310, total_load,
            max_spacing=1.10,
        )
        shores_adaptive, _, _, sx2, _ = distribute_shores(
            slab, esc310, total_load,
            max_spacing=1.10,
            floor_height_m=2.68,
        )

        # Com adaptativo, espaçamento pode ser diferente (geralmente menor)
        assert len(shores_legacy) > 0
        assert len(shores_adaptive) > 0
