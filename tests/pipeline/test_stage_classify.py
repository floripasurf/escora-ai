import pytest
from src.pipeline.stage_segment import LevelSegment
from src.pipeline.stage_parse import SegmentEntity, RectEntity, TextEntity
from src.pipeline.stage_classify import classify_elements
from src.models.pipeline_models import ElementType


def test_classify_beam_from_segments():
    """Parallel segments -> beam classified with geometric score (real meters)."""
    level = LevelSegment(
        level_name="TEST",
        segments=[
            SegmentEntity("H", y=10.00, x_min=0, x_max=6.0, layer="11"),
            SegmentEntity("H", y=10.14, x_min=0, x_max=6.0, layer="11"),
        ],
        texts=[TextEntity("V1 14x40", 3.0, 10.2, "TEXTO")],
    )
    elements = classify_elements(level, scale=1.0)
    beams = [e for e in elements if e.element_type == ElementType.BEAM]
    assert len(beams) >= 1
    assert beams[0].score_final >= 0.70


def test_classify_pillar_from_rect():
    """Small SOLID rectangle -> pillar classified (real meters)."""
    level = LevelSegment(
        level_name="TEST",
        rects=[RectEntity(cx=5.0, cy=10.0, width=0.20, height=0.40, area=0.08, layer="21")],
        texts=[TextEntity("P1", 5.1, 10.2, "21")],
    )
    elements = classify_elements(level, scale=1.0)
    pillars = [e for e in elements if e.element_type == ElementType.PILLAR]
    assert len(pillars) >= 1
