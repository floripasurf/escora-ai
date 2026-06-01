"""Tests for slab detection from beam pairs and edge closure."""

import pytest
from src.engine.slab_builder import (
    derive_slabs_from_beam_pairs,
    _close_open_beam_cells,
)
from src.models.pipeline_models import ClassifiedElement, ElementType
from shapely.geometry import LineString


def _make_beam(x1, y1, x2, y2, name="V1"):
    """Create a minimal ClassifiedElement beam."""
    return ClassifiedElement(
        element_type=ElementType.BEAM,
        name=name,
        layer="BEAM",
        geometry=[(x1, y1), (x2, y2)],
        section_width_m=0.14,
        section_height_m=0.40,
    )


class TestBeamPairSlabs:
    def test_two_parallel_h_beams(self):
        """Two horizontal beams should produce one slab."""
        beams = [
            _make_beam(0, 0, 10, 0, "V1"),
            _make_beam(0, 5, 10, 5, "V2"),
        ]
        slabs = derive_slabs_from_beam_pairs(beams)
        assert len(slabs) == 1
        assert slabs[0].area == pytest.approx(50.0, abs=0.1)

    def test_two_parallel_v_beams(self):
        """Two vertical beams should produce one slab."""
        beams = [
            _make_beam(0, 0, 0, 8, "P1"),
            _make_beam(5, 0, 5, 8, "P2"),
        ]
        slabs = derive_slabs_from_beam_pairs(beams)
        assert len(slabs) == 1
        assert slabs[0].area == pytest.approx(40.0, abs=0.1)

    def test_partial_overlap(self):
        """Beams with partial overlap produce slab of overlap area."""
        beams = [
            _make_beam(0, 0, 10, 0, "V1"),
            _make_beam(5, 4, 15, 4, "V2"),
        ]
        slabs = derive_slabs_from_beam_pairs(beams)
        assert len(slabs) == 1
        assert slabs[0].area == pytest.approx(20.0, abs=0.1)

    def test_no_overlap(self):
        """Non-overlapping beams produce no slab."""
        beams = [
            _make_beam(0, 0, 5, 0, "V1"),
            _make_beam(10, 4, 15, 4, "V2"),
        ]
        slabs = derive_slabs_from_beam_pairs(beams)
        assert len(slabs) == 0

    def test_too_far_apart(self):
        """Beams > max_span apart produce no slab."""
        beams = [
            _make_beam(0, 0, 10, 0, "V1"),
            _make_beam(0, 12, 10, 12, "V2"),
        ]
        slabs = derive_slabs_from_beam_pairs(beams, max_span=8.0)
        assert len(slabs) == 0

    def test_short_beams_filtered(self):
        """Beams shorter than 1.5m are filtered (pillar outlines)."""
        beams = [
            _make_beam(0, 0, 1.0, 0, "V1"),
            _make_beam(0, 5, 1.0, 5, "V2"),
        ]
        slabs = derive_slabs_from_beam_pairs(beams)
        assert len(slabs) == 0

    def test_intermediate_beam_splits(self):
        """An intermediate beam prevents pairing across it."""
        beams = [
            _make_beam(0, 0, 10, 0, "V1"),
            _make_beam(0, 3, 10, 3, "V2"),
            _make_beam(0, 6, 10, 6, "V3"),
        ]
        slabs = derive_slabs_from_beam_pairs(beams)
        assert len(slabs) == 2
        areas = sorted(s.area for s in slabs)
        assert areas[0] == pytest.approx(30.0, abs=0.1)
        assert areas[1] == pytest.approx(30.0, abs=0.1)

    def test_grid_produces_multiple_slabs(self):
        """A 2x2 grid of beams should produce at least 1 slab per cell."""
        beams = [
            _make_beam(0, 0, 10, 0, "H1"),
            _make_beam(0, 5, 10, 5, "H2"),
            _make_beam(0, 0, 0, 5, "V1"),
            _make_beam(5, 0, 5, 5, "V2"),
        ]
        slabs = derive_slabs_from_beam_pairs(beams)
        assert len(slabs) >= 1


class TestEdgeClosure:
    def test_closes_u_shape(self):
        """Free endpoints at same Y get connected."""
        lines = [
            LineString([(0, 0), (0, 5)]),
            LineString([(4, 0), (4, 5)]),
            LineString([(0, 0), (4, 0)]),
        ]
        closed = _close_open_beam_cells(lines)
        assert len(closed) == len(lines) + 1

    def test_no_closure_when_closed(self):
        """Fully closed grid needs no closures."""
        lines = [
            LineString([(0, 0), (0, 5)]),
            LineString([(4, 0), (4, 5)]),
            LineString([(0, 0), (4, 0)]),
            LineString([(0, 5), (4, 5)]),
        ]
        closed = _close_open_beam_cells(lines)
        assert len(closed) == len(lines)

    def test_gap_too_large(self):
        """Free endpoints too far apart should not be closed."""
        lines = [
            LineString([(0, 0), (0, 5)]),
            LineString([(20, 0), (20, 5)]),
            LineString([(0, 0), (20, 0)]),
        ]
        closed = _close_open_beam_cells(lines, max_gap=10.0)
        assert len(closed) == len(lines)
