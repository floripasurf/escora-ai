"""Test that classify_elements populates geometry on beams and pillars."""

import pytest
from src.pipeline.stage_classify import classify_elements
from src.pipeline.stage_segment import LevelSegment
from src.pipeline.stage_parse import SegmentEntity, RectEntity, CircleEntity
from src.models.pipeline_models import ElementType


def _make_beam_segments(y1, y2, x_min, x_max, layer="BEAM"):
    """Create a pair of horizontal segments that form a beam."""
    return [
        SegmentEntity(type="H", y=y1, x_min=x_min, x_max=x_max, layer=layer),
        SegmentEntity(type="H", y=y2, x_min=x_min, x_max=x_max, layer=layer),
    ]


def test_beam_geometry_has_axis_endpoints():
    segs = _make_beam_segments(4.9, 5.1, 0.0, 10.0)
    level = LevelSegment(level_name="TEST", segments=segs)
    elements = classify_elements(level, scale=1.0)
    beams = [e for e in elements if e.element_type == ElementType.BEAM]
    assert len(beams) >= 1
    beam = beams[0]
    assert len(beam.geometry) == 2, "Beam geometry should have 2 points (start, end)"
    start_pt, end_pt = beam.geometry
    assert start_pt[1] == pytest.approx(end_pt[1], abs=0.01), "Both points should share axis Y"
    assert start_pt[0] < end_pt[0], "Start X should be less than end X"


def test_rect_pillar_geometry_has_center():
    rects = [
        RectEntity(cx=5.0, cy=5.0, width=0.20, height=0.40, area=0.08, layer="PIL"),
    ]
    level = LevelSegment(level_name="TEST", rects=rects)
    elements = classify_elements(level, scale=1.0)
    pillars = [e for e in elements if e.element_type == ElementType.PILLAR]
    assert len(pillars) >= 1
    pillar = pillars[0]
    assert len(pillar.geometry) == 1, "Pillar geometry should have 1 point (center)"
    assert pillar.geometry[0] == pytest.approx((5.0, 5.0), abs=0.01)


def test_circle_pillar_geometry_has_center():
    circles = [
        CircleEntity(cx=float(i), cy=float(i), radius=0.15, layer="COL")
        for i in range(6)
    ]
    level = LevelSegment(level_name="TEST", circles=circles)
    elements = classify_elements(level, scale=1.0)
    pillars = [e for e in elements if e.element_type == ElementType.PILLAR]
    assert len(pillars) >= 5
    for p in pillars:
        assert len(p.geometry) == 1, "Circular pillar geometry should have 1 point"
