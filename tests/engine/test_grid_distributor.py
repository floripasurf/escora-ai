"""Tests for grid_distributor — corridor detection and linear distribution."""

import math
import pytest
from shapely.geometry import Polygon

from src.models.slab import Slab, BoundingBox
from src.engine.grid_distributor import (
    _is_narrow_corridor,
    _distribute_linear,
    distribute_shores,
)
from src.models.shore import ShoreCatalogEntry, PositionedShore


def _make_slab(coords, thickness=0.12):
    """Create a Slab from polygon coordinates."""
    poly = Polygon(coords)
    return Slab.from_polygon(poly, layer_name="LAJE", thickness_m=thickness)


def _make_shore():
    """Create a minimal ShoreCatalogEntry for testing."""
    return ShoreCatalogEntry(
        id="ESC310",
        manufacturer="Orguel",
        model="ESC310",
        height_min_m=1.80,
        height_max_m=3.10,
        load_capacity_kn=30.0,
        weight_kg=10.0,
        tube_external_mm=48.3,
        tube_internal_mm=38.1,
        base_plate_mm=120.0,
        price_reference_brl=15.0,
    )


class TestNarrowCorridorDetection:
    def test_narrow_corridor_detected(self):
        """A 1.5m × 10m slab with spacing 1.1m should be a corridor."""
        slab = _make_slab([(0, 0), (10, 0), (10, 1.5), (0, 1.5)])
        assert _is_narrow_corridor(slab, 1.1) is True

    def test_wide_slab_not_corridor(self):
        """A 5m × 5m slab should NOT be a corridor."""
        slab = _make_slab([(0, 0), (5, 0), (5, 5), (0, 5)])
        assert _is_narrow_corridor(slab, 1.1) is False

    def test_threshold_boundary(self):
        """Width exactly 2× spacing should NOT be a corridor."""
        slab = _make_slab([(0, 0), (10, 0), (10, 2.2), (0, 2.2)])
        assert _is_narrow_corridor(slab, 1.1) is False


class TestLinearDistribution:
    def test_corridor_produces_linear_shores(self):
        """Shores in a corridor should be collinear along the long axis."""
        slab = _make_slab([(0, 0), (10, 0), (10, 1.5), (0, 1.5)])
        shore = _make_shore()
        shores, nx, ny, sx, sy = _distribute_linear(slab, shore, 50.0, 1.1)

        assert len(shores) >= 2
        # All shores should be at approximately y=0.75 (center of corridor)
        ys = [s.y for s in shores]
        assert all(abs(y - 0.75) < 0.5 for y in ys), f"Y values not centered: {ys}"

    def test_corridor_shores_evenly_spaced(self):
        """Shores should be approximately evenly spaced along the axis."""
        slab = _make_slab([(0, 0), (10, 0), (10, 1.5), (0, 1.5)])
        shore = _make_shore()
        shores, *_ = _distribute_linear(slab, shore, 50.0, 1.1)

        if len(shores) >= 3:
            xs = sorted(s.x for s in shores)
            spacings = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
            # Spacings should be roughly equal
            avg = sum(spacings) / len(spacings)
            for sp in spacings:
                assert abs(sp - avg) < 0.2, f"Uneven spacing: {spacings}"

    def test_very_short_corridor_gets_at_least_one_shore(self):
        """A very small corridor should still get at least 1 shore."""
        slab = _make_slab([(0, 0), (0.5, 0), (0.5, 0.3), (0, 0.3)])
        shore = _make_shore()
        shores, *_ = _distribute_linear(slab, shore, 50.0, 1.1)
        assert len(shores) >= 1


class TestZeroCapacityShoreGuard:
    """Escora com load_capacity_kn==0 (ex.: entrada sintetica/custom) nao deve
    causar ZeroDivisionError — bug visto no projeto 101112 (diagnostico codex)."""

    def _zero_cap_shore(self):
        return _make_shore().model_copy(update={"load_capacity_kn": 0.0})

    def test_distribute_linear_no_zerodivision(self):
        slab = _make_slab([(0, 0), (10, 0), (10, 1.5), (0, 1.5)])  # corredor → _distribute_linear
        shores, *_ = _distribute_linear(slab, self._zero_cap_shore(), 50.0, 1.1)
        assert len(shores) >= 1
        assert all(s.utilization_ratio == 0.0 for s in shores)

    def test_distribute_shores_wide_grid_no_zerodivision(self):
        slab = _make_slab([(0, 0), (5, 0), (5, 5), (0, 5)])  # largo → grid (linha 376)
        shores, *_ = distribute_shores(
            slab, self._zero_cap_shore(), total_load_kn=50.0, max_spacing=1.1,
        )
        assert len(shores) >= 1
        assert all(s.utilization_ratio == 0.0 for s in shores)


class TestDistributeShoresCorridorIntegration:
    def test_narrow_slab_uses_linear_distribution(self):
        """distribute_shores should detect a narrow slab and use linear mode."""
        slab = _make_slab([(0, 0), (10, 0), (10, 1.5), (0, 1.5)])
        shore = _make_shore()
        shores, nx, ny, sx, sy = distribute_shores(
            slab, shore, total_load_kn=50.0, max_spacing=1.1,
        )
        # Should produce shores in a line (ny=1 for linear)
        assert ny == 1
        assert len(shores) >= 2

    def test_wide_slab_uses_grid_distribution(self):
        """distribute_shores on a wide slab should use normal grid."""
        slab = _make_slab([(0, 0), (5, 0), (5, 5), (0, 5)])
        shore = _make_shore()
        shores, nx, ny, sx, sy = distribute_shores(
            slab, shore, total_load_kn=100.0, max_spacing=1.1,
        )
        # Should use grid mode (ny > 1)
        assert ny > 1
        assert len(shores) >= 4
