import pytest
from src.models.pipeline_models import (
    RawEntity, ClassifiedElement, ElementType, LevelGroup, PipelineResult
)


def test_raw_entity_creation():
    e = RawEntity(
        entity_type="LWPOLYLINE",
        layer="11",
        points=[(0, 0), (5, 0), (5, 1), (0, 1)],
        color=7,
        texts_nearby=[],
    )
    assert e.entity_type == "LWPOLYLINE"
    assert e.layer == "11"
    assert len(e.points) == 4


def test_classified_element_beam():
    el = ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[(0, 0), (5, 0), (5, 0.14), (0, 0.14)],
        score_geometric=0.85,
        score_textual=0.90,
        score_final=0.95,
        name="V1",
        section_width_m=0.14,
        section_height_m=0.40,
        length_m=5.0,
        source_layer="11",
    )
    assert el.element_type == ElementType.BEAM
    assert el.score_final == 0.95
    assert el.needs_review is False


def test_classified_element_needs_review():
    el = ClassifiedElement(
        element_type=ElementType.SLAB,
        geometry=[(0, 0), (5, 0), (5, 4), (0, 4)],
        score_geometric=0.60,
        score_textual=0.0,
        score_final=0.51,
        source_layer="UNKNOWN",
    )
    assert el.needs_review is True


def test_level_group():
    lg = LevelGroup(level_name="COBERTURA", level_height_m=1330.40)
    assert lg.level_name == "COBERTURA"
    assert len(lg.entities) == 0
    assert len(lg.elements) == 0


def test_pipeline_result():
    pr = PipelineResult(filename="test.dxf", scale=0.02)
    assert pr.filename == "test.dxf"
    assert len(pr.levels) == 0
    assert len(pr.warnings) == 0
