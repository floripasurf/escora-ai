import pytest
from src.parser.segment_classifier import (
    find_beam_candidates, BeamCandidate,
    find_pillar_candidates, PillarCandidate,
)


class TestBeamCandidates:
    def test_horizontal_pair(self):
        """Two horizontal segments close together -> beam candidate."""
        segments = [
            {"type": "H", "y": 5.00, "x_min": 0, "x_max": 6.0},
            {"type": "H", "y": 5.14, "x_min": 0, "x_max": 6.0},
        ]
        beams = find_beam_candidates(segments)
        assert len(beams) == 1
        assert beams[0].width_m == pytest.approx(0.14, abs=0.02)
        assert beams[0].length_m == pytest.approx(6.0, abs=0.1)
        assert beams[0].direction == "x"

    def test_vertical_pair(self):
        """Two vertical segments close together -> beam candidate."""
        segments = [
            {"type": "V", "x": 3.00, "y_min": 0, "y_max": 5.0},
            {"type": "V", "x": 3.14, "y_min": 0, "y_max": 5.0},
        ]
        beams = find_beam_candidates(segments)
        assert len(beams) == 1
        assert beams[0].direction == "y"

    def test_no_pair_far_apart(self):
        """Segments too far apart -> not a beam."""
        segments = [
            {"type": "H", "y": 5.00, "x_min": 0, "x_max": 6.0},
            {"type": "H", "y": 6.00, "x_min": 0, "x_max": 6.0},
        ]
        beams = find_beam_candidates(segments)
        assert len(beams) == 0

    def test_min_length_filter(self):
        """Very short segment pair -> filtered out (not a beam)."""
        segments = [
            {"type": "H", "y": 5.00, "x_min": 0, "x_max": 0.20},
            {"type": "H", "y": 5.14, "x_min": 0, "x_max": 0.20},
        ]
        beams = find_beam_candidates(segments, min_length=0.5)
        assert len(beams) == 0


class TestPillarCandidates:
    def test_small_rectangle(self):
        """Small closed rectangle -> pillar candidate."""
        rects = [
            {"cx": 5.0, "cy": 10.0, "width": 0.20, "height": 0.40, "area": 0.08},
        ]
        pillars = find_pillar_candidates(rects)
        assert len(pillars) == 1
        assert pillars[0].width_m == pytest.approx(0.20)
        assert pillars[0].depth_m == pytest.approx(0.40)

    def test_large_rectangle_filtered(self):
        """Large rectangle -> not a pillar (area > 0.5m2)."""
        rects = [
            {"cx": 5.0, "cy": 10.0, "width": 2.0, "height": 3.0, "area": 6.0},
        ]
        pillars = find_pillar_candidates(rects)
        assert len(pillars) == 0
