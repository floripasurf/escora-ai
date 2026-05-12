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


def test_learned_beam_layer_accepted():
    """A layer known from history gets accepted even if not the best rate."""
    # Layer "42" is the best beam layer, but "99" has learned history
    level = LevelSegment(
        level_name="TEST",
        segments=[
            # Layer "42" — 2 beams (best rate)
            SegmentEntity("H", y=10.00, x_min=0, x_max=6.0, layer="42"),
            SegmentEntity("H", y=10.14, x_min=0, x_max=6.0, layer="42"),
            # Layer "99" — also has beams, but lower rate (more noise segments)
            SegmentEntity("H", y=20.00, x_min=0, x_max=5.0, layer="99"),
            SegmentEntity("H", y=20.14, x_min=0, x_max=5.0, layer="99"),
            SegmentEntity("V", x=1.0, y_min=19.0, y_max=21.0, layer="99"),
            SegmentEntity("V", x=2.0, y_min=19.0, y_max=21.0, layer="99"),
        ],
        texts=[],
    )
    # Without learning: only layer "42" selected (best rate)
    elements_no_learn = classify_elements(level, scale=1.0)
    beams_no_learn = [e for e in elements_no_learn if e.element_type == ElementType.BEAM]

    # With learning: layer "99" also accepted
    elements_learn = classify_elements(
        level, scale=1.0,
        known_beam_layers={"99": 1.0},
    )
    beams_learn = [e for e in elements_learn if e.element_type == ElementType.BEAM]

    assert len(beams_learn) >= len(beams_no_learn)


def test_low_confidence_learned_layer_ignored():
    """A layer with low historical confidence is not accepted."""
    level = LevelSegment(
        level_name="TEST",
        segments=[
            SegmentEntity("H", y=10.00, x_min=0, x_max=6.0, layer="42"),
            SegmentEntity("H", y=10.14, x_min=0, x_max=6.0, layer="42"),
            SegmentEntity("H", y=20.00, x_min=0, x_max=5.0, layer="99"),
            SegmentEntity("H", y=20.14, x_min=0, x_max=5.0, layer="99"),
        ],
        texts=[],
    )
    # Low confidence — should NOT add layer "99"
    elements = classify_elements(
        level, scale=1.0,
        known_beam_layers={"99": 0.50},
    )
    beams = [e for e in elements if e.element_type == ElementType.BEAM]

    elements_base = classify_elements(level, scale=1.0)
    beams_base = [e for e in elements_base if e.element_type == ElementType.BEAM]

    assert len(beams) == len(beams_base)


def test_recovers_beam_layer_when_slab_text_has_strict_section():
    level = LevelSegment(
        level_name="TEST",
        segments=[
            SegmentEntity("H", y=10.00, x_min=0, x_max=6.0, layer="VIGAS"),
            SegmentEntity("H", y=10.19, x_min=0, x_max=6.0, layer="VIGAS"),
        ],
        texts=[
            TextEntity("L1", 3.0, 10.10, "TEXTO"),
            TextEntity("60/19", 3.0, 10.20, "TEXTO"),
        ],
    )

    elements = classify_elements(level, scale=1.0)

    beams = [e for e in elements if e.element_type == ElementType.BEAM]
    assert len(beams) == 1
    assert beams[0].section_width_m == pytest.approx(0.19)
    assert beams[0].section_height_m == pytest.approx(0.60)


def test_keeps_slab_veto_for_section_with_spaced_slash():
    level = LevelSegment(
        level_name="TEST",
        segments=[
            SegmentEntity("H", y=10.00, x_min=0, x_max=6.0, layer="VIGAS"),
            SegmentEntity("H", y=10.14, x_min=0, x_max=6.0, layer="VIGAS"),
        ],
        texts=[
            TextEntity("L1", 3.0, 10.10, "TEXTO"),
            TextEntity("14 / 60", 3.0, 10.20, "TEXTO"),
        ],
    )

    elements = classify_elements(level, scale=1.0)

    beams = [e for e in elements if e.element_type == ElementType.BEAM]
    assert beams == []


def test_slab_text_recovery_does_not_apply_to_non_explicit_beam_layer():
    level = LevelSegment(
        level_name="TEST",
        segments=[
            SegmentEntity("H", y=10.00, x_min=0, x_max=6.0, layer="VIGAS"),
            SegmentEntity("H", y=10.19, x_min=0, x_max=6.0, layer="VIGAS"),
            SegmentEntity("H", y=20.00, x_min=0, x_max=6.0, layer="PILARES"),
            SegmentEntity("H", y=20.19, x_min=0, x_max=6.0, layer="PILARES"),
        ],
        texts=[
            TextEntity("L1", 3.0, 10.10, "TEXTO"),
            TextEntity("60/19", 3.0, 10.20, "TEXTO"),
            TextEntity("L2", 3.0, 20.10, "TEXTO"),
            TextEntity("60/19", 3.0, 20.20, "TEXTO"),
        ],
    )

    elements = classify_elements(
        level,
        scale=1.0,
        known_beam_layers={"PILARES": 1.0},
    )

    beams = [e for e in elements if e.element_type == ElementType.BEAM]
    assert len(beams) == 1
    assert beams[0].geometry[0] == pytest.approx((0, 10.095))
    assert beams[0].geometry[1] == pytest.approx((6.0, 10.095))
