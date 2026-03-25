"""Test slab derivation from beam grid via Shapely polygonize."""

import pytest
from shapely.geometry import LineString, box
from src.engine.slab_builder import derive_slabs_from_beams, detect_cantilever_slabs
from src.models.pipeline_models import ClassifiedElement, ElementType


def _beam(x1, y1, x2, y2, **kwargs):
    return ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[(x1, y1), (x2, y2)],
        score_geometric=0.85, score_textual=0.0, score_final=0.75,
        section_width_m=kwargs.get("width", 0.14),
        section_height_m=kwargs.get("height", 0.40),
        length_m=((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5,
    )


def _pillar(cx, cy):
    return ClassifiedElement(
        element_type=ElementType.PILLAR,
        geometry=[(cx, cy)],
        score_geometric=0.80, score_textual=0.0, score_final=0.70,
        section_width_m=0.20, section_height_m=0.40,
    )


class TestDeriveSlabs:
    def test_simple_rectangle_grid(self):
        """4 beams forming a rectangle -> 1 slab panel."""
        beams = [
            _beam(0, 0, 10, 0),
            _beam(0, 6, 10, 6),
            _beam(0, 0, 0, 6),
            _beam(10, 0, 10, 6),
        ]
        slabs = derive_slabs_from_beams(beams)
        assert len(slabs) == 1
        assert slabs[0].area > 50

    def test_two_panel_grid(self):
        """5 beams forming 2 adjacent panels -> 2 slab panels."""
        beams = [
            _beam(0, 0, 10, 0),
            _beam(0, 6, 10, 6),
            _beam(0, 0, 0, 6),
            _beam(5, 0, 5, 6),
            _beam(10, 0, 10, 6),
        ]
        slabs = derive_slabs_from_beams(beams)
        assert len(slabs) == 2

    def test_no_closed_regions(self):
        """Open beams (not forming closed polygon) -> 0 slabs."""
        beams = [
            _beam(0, 0, 10, 0),
            _beam(0, 0, 0, 6),
        ]
        slabs = derive_slabs_from_beams(beams)
        assert len(slabs) == 0

    def test_three_by_two_grid(self):
        """Grid of 3x2 panels -> 6 slab panels."""
        beams = []
        for y in [0, 4, 8]:
            beams.append(_beam(0, y, 15, y))
        for x in [0, 5, 10, 15]:
            beams.append(_beam(x, 0, x, 8))
        slabs = derive_slabs_from_beams(beams)
        assert len(slabs) == 6


class TestCantileverSlabs:
    def test_slab_outside_pillar_hull_is_cantilever(self):
        pillars = [
            _pillar(2, 2), _pillar(8, 2),
            _pillar(2, 6), _pillar(8, 6),
        ]
        slabs = [box(8, 0, 12, 6)]
        result = detect_cantilever_slabs(slabs, pillars)
        assert len(result) == 1
        assert result[0] is True

    def test_slab_inside_pillar_hull_is_not_cantilever(self):
        pillars = [
            _pillar(0, 0), _pillar(10, 0),
            _pillar(0, 8), _pillar(10, 8),
        ]
        slabs = [box(2, 2, 8, 6)]
        result = detect_cantilever_slabs(slabs, pillars)
        assert len(result) == 1
        assert result[0] is False
