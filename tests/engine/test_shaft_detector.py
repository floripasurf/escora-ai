"""Tests for shaft/void detection."""

import pytest
from dataclasses import dataclass
from src.engine.shaft_detector import (
    detect_shafts_from_x_patterns,
    detect_shafts_from_text,
    detect_shafts_from_layers,
    detect_all_shafts,
    filter_slab_polygons_by_shafts,
    ShaftRegion,
    _merge_nearby_shafts,
)
from shapely.geometry import box


@dataclass
class FakeDiagonal:
    x1: float
    y1: float
    x2: float
    y2: float
    layer: str = "0"


@dataclass
class FakeText:
    content: str
    x: float
    y: float
    layer: str = "0"


@dataclass
class FakeHatch:
    points: list
    layer: str = "0"
    pattern_name: str = ""
    is_solid: bool = False
    area: float = 0.0


@dataclass
class FakePolyline:
    points: list
    layer: str = "0"
    is_closed: bool = False


class TestXPatternDetection:
    def test_detects_x_pattern(self):
        """Two crossing diagonals should be detected as a shaft."""
        diags = [
            FakeDiagonal(x1=0, y1=0, x2=2, y2=2),  # bottom-left to top-right
            FakeDiagonal(x1=2, y1=0, x2=0, y2=2),  # bottom-right to top-left
        ]
        shafts = detect_shafts_from_x_patterns(diags, scale=1.0)
        assert len(shafts) == 1
        assert shafts[0].detection_method == "x_pattern"
        assert shafts[0].area_m2 == pytest.approx(4.0, abs=0.1)

    def test_ignores_small_x(self):
        """X patterns smaller than MIN_SHAFT_AREA should be ignored."""
        diags = [
            FakeDiagonal(x1=0, y1=0, x2=0.3, y2=0.3),
            FakeDiagonal(x1=0.3, y1=0, x2=0, y2=0.3),
        ]
        shafts = detect_shafts_from_x_patterns(diags, scale=1.0)
        assert len(shafts) == 0

    def test_ignores_horizontal_lines(self):
        """Parallel lines shouldn't form an X."""
        diags = [
            FakeDiagonal(x1=0, y1=0, x2=2, y2=0.5),  # near horizontal
            FakeDiagonal(x1=0, y1=1, x2=2, y2=1.5),  # near horizontal
        ]
        shafts = detect_shafts_from_x_patterns(diags, scale=1.0)
        assert len(shafts) == 0

    def test_multiple_x_patterns(self):
        """Two separate X patterns should produce two shafts."""
        diags = [
            # Shaft 1 at (0,0)
            FakeDiagonal(x1=0, y1=0, x2=2, y2=2),
            FakeDiagonal(x1=2, y1=0, x2=0, y2=2),
            # Shaft 2 at (10,10)
            FakeDiagonal(x1=10, y1=10, x2=12, y2=12),
            FakeDiagonal(x1=12, y1=10, x2=10, y2=12),
        ]
        shafts = detect_shafts_from_x_patterns(diags, scale=1.0)
        assert len(shafts) == 2

    def test_scale_applied(self):
        """Scale factor should be applied to shaft dimensions."""
        diags = [
            FakeDiagonal(x1=0, y1=0, x2=100, y2=100),
            FakeDiagonal(x1=100, y1=0, x2=0, y2=100),
        ]
        shafts = detect_shafts_from_x_patterns(diags, scale=0.02)
        assert len(shafts) == 1
        assert shafts[0].area_m2 == pytest.approx(4.0, abs=0.1)


class TestTextDetection:
    def test_detects_elevator_text(self):
        texts = [FakeText(content="ELEVADOR", x=5, y=5)]
        shafts = detect_shafts_from_text(texts, scale=1.0)
        assert len(shafts) == 1
        assert shafts[0].detection_method == "text"
        assert shafts[0].label == "ELEVADOR"

    def test_detects_poco_text(self):
        texts = [FakeText(content="POÇO DE ELEVADOR", x=5, y=5)]
        shafts = detect_shafts_from_text(texts, scale=1.0)
        assert len(shafts) == 1

    def test_detects_furo_text(self):
        texts = [FakeText(content="FURO F1", x=5, y=5)]
        shafts = detect_shafts_from_text(texts, scale=1.0)
        assert len(shafts) == 1

    def test_ignores_unrelated_text(self):
        texts = [FakeText(content="V1 14x40", x=5, y=5)]
        shafts = detect_shafts_from_text(texts, scale=1.0)
        assert len(shafts) == 0


class TestLayerDetection:
    def test_detects_abertura_layer(self):
        hatches = [FakeHatch(
            points=[(0, 0), (2, 0), (2, 2), (0, 2)],
            layer="LJ_SIMB_ABER",
        )]
        shafts = detect_shafts_from_layers(hatches, [], scale=1.0)
        assert len(shafts) == 1
        assert shafts[0].detection_method == "layer"

    def test_detects_furo_layer_polyline(self):
        polylines = [FakePolyline(
            points=[(0, 0), (1.5, 0), (1.5, 1.5), (0, 1.5)],
            layer="FURO_LAJE",
            is_closed=True,
        )]
        shafts = detect_shafts_from_layers([], polylines, scale=1.0)
        assert len(shafts) == 1

    def test_ignores_open_polyline(self):
        polylines = [FakePolyline(
            points=[(0, 0), (1.5, 0), (1.5, 1.5)],
            layer="FURO_LAJE",
            is_closed=False,
        )]
        shafts = detect_shafts_from_layers([], polylines, scale=1.0)
        assert len(shafts) == 0

    def test_ignores_non_shaft_layer(self):
        hatches = [FakeHatch(
            points=[(0, 0), (2, 0), (2, 2), (0, 2)],
            layer="VIGA_EIXO",
        )]
        shafts = detect_shafts_from_layers(hatches, [], scale=1.0)
        assert len(shafts) == 0


class TestMerge:
    def test_merges_overlapping_shafts(self):
        s1 = ShaftRegion(x_min=0, y_min=0, x_max=2, y_max=2,
                         area_m2=4, detection_method="x_pattern", confidence=0.9)
        s2 = ShaftRegion(x_min=0.5, y_min=0.5, x_max=2.5, y_max=2.5,
                         area_m2=4, detection_method="text", confidence=0.7, label="ELEVADOR")
        merged = _merge_nearby_shafts([s1, s2])
        assert len(merged) == 1
        assert merged[0].x_min == 0
        assert merged[0].x_max == 2.5
        assert merged[0].confidence == 0.9  # keeps highest
        assert merged[0].label == "ELEVADOR"  # keeps label

    def test_keeps_distant_shafts_separate(self):
        s1 = ShaftRegion(x_min=0, y_min=0, x_max=2, y_max=2,
                         area_m2=4, detection_method="x_pattern")
        s2 = ShaftRegion(x_min=10, y_min=10, x_max=12, y_max=12,
                         area_m2=4, detection_method="x_pattern")
        merged = _merge_nearby_shafts([s1, s2])
        assert len(merged) == 2


class TestSlabFiltering:
    def test_removes_slab_overlapping_shaft(self):
        slabs = [box(0, 0, 2, 2), box(5, 5, 10, 10)]
        shafts = [ShaftRegion(
            x_min=0, y_min=0, x_max=2, y_max=2,
            area_m2=4, detection_method="x_pattern",
        )]
        filtered, removed = filter_slab_polygons_by_shafts(slabs, shafts)
        assert len(filtered) == 1
        assert len(removed) == 1
        assert removed[0] == 0

    def test_keeps_non_overlapping_slabs(self):
        slabs = [box(5, 5, 10, 10)]
        shafts = [ShaftRegion(
            x_min=0, y_min=0, x_max=2, y_max=2,
            area_m2=4, detection_method="x_pattern",
        )]
        filtered, removed = filter_slab_polygons_by_shafts(slabs, shafts)
        assert len(filtered) == 1
        assert len(removed) == 0

    def test_no_shafts_returns_all(self):
        slabs = [box(0, 0, 5, 5)]
        filtered, removed = filter_slab_polygons_by_shafts(slabs, [])
        assert len(filtered) == 1


class TestIntegration:
    def test_detect_all_combines_methods(self):
        diags = [
            FakeDiagonal(x1=0, y1=0, x2=2, y2=2),
            FakeDiagonal(x1=2, y1=0, x2=0, y2=2),
        ]
        texts = [FakeText(content="ELEVADOR", x=1, y=1)]
        # Should merge the X-pattern and text into one shaft
        shafts = detect_all_shafts(diags, texts, [], [], scale=1.0)
        assert len(shafts) == 1
        assert shafts[0].confidence == 0.9  # X-pattern confidence wins
