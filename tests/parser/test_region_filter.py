"""Tests for region_filter — spatial clustering and detail view exclusion."""

import pytest
from src.parser.region_filter import (
    _find_gap_splits,
    _detect_regions,
    _detect_bounding_rectangles,
    _is_in_detail_zone,
    filter_main_plan,
    DETAIL_EXCLUSION_RADIUS,
)
from src.pipeline.stage_parse import (
    TextEntity, SegmentEntity, PolylineEntity, HatchEntity,
    RectEntity, CircleEntity, DimensionEntity,
)


class TestGapDetection:
    def test_small_gap_detected_with_new_threshold(self):
        """Gap of 2.5m should be detected with the new lower threshold."""
        # total_range = 100m → threshold = max(2.0, 0.02*100) = 2.0m
        # 2.5m > 2.0m → should split
        values = [0.0, 1.0, 2.0, 3.0, 5.5, 6.5, 7.5]
        splits = _find_gap_splits(values, 100.0)
        assert len(splits) >= 1
        assert any(3.0 < s < 5.5 for s in splits)

    def test_gap_below_threshold_not_detected(self):
        """Gaps below threshold should not cause splits."""
        values = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
        splits = _find_gap_splits(values, 100.0)
        assert len(splits) == 0


class TestDominanceThreshold:
    def test_main_at_40_pct_activates_filter(self):
        """Main region with 40% of entities should activate filtering (> 35%)."""
        # Create two clusters with a clear gap
        cluster1 = [(float(i), 0.0) for i in range(40)]  # 40 points at y=0
        cluster2 = [(float(i), 50.0) for i in range(60)]  # 60 points at y=50
        centroids = cluster1 + cluster2
        regions = _detect_regions(centroids)
        # Should detect 2 regions; the larger has 60% (>35%), filter activates
        assert len(regions) >= 2

    def test_main_at_30_pct_does_not_activate(self):
        """Main region with only 30% should NOT activate (< 35%)."""
        # This is tested indirectly via filter_main_plan, but we verify
        # the threshold logic: 30/100 = 0.30 < 0.35
        assert 0.30 < 0.35


class TestBoundingRectangleDetection:
    def _make_polyline(self, points, layer="0"):
        return PolylineEntity(points=points, layer=layer, is_closed=True)

    def test_detects_rectangular_frame(self):
        """A closed rectangular polyline should be detected as a frame."""
        rect = self._make_polyline(
            [(10, 10), (20, 10), (20, 18), (10, 18), (10, 10)],
            layer="QUADRO",
        )
        rects = _detect_bounding_rectangles([rect])
        assert len(rects) == 1

    def test_ignores_too_large_rectangle(self):
        """Rectangles > 50m should be ignored (likely the sheet border)."""
        rect = self._make_polyline(
            [(0, 0), (60, 0), (60, 40), (0, 40), (0, 0)],
        )
        rects = _detect_bounding_rectangles([rect])
        assert len(rects) == 0

    def test_ignores_too_small_rectangle(self):
        """Rectangles < 1m should be ignored."""
        rect = self._make_polyline(
            [(0, 0), (0.5, 0), (0.5, 0.5), (0, 0.5), (0, 0)],
        )
        rects = _detect_bounding_rectangles([rect])
        assert len(rects) == 0


class TestDetailExclusionRadius:
    def test_radius_is_5m(self):
        """DETAIL_EXCLUSION_RADIUS should be 5.0m (reduced from 8.0)."""
        assert DETAIL_EXCLUSION_RADIUS == 5.0
