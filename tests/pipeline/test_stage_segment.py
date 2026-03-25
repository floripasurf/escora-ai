import pytest
from src.pipeline.stage_parse import ParseResult, TextEntity, SegmentEntity
from src.pipeline.stage_segment import segment_by_level


def test_single_level():
    """DXF with one level -> 1 group with all entities."""
    parse = ParseResult(
        filename="test.dxf", layers=["11"], detected_scale=0.02,
        texts=[TextEntity("COBERTURA +1330.40", 10, 10, "TEXTO")],
        segments=[SegmentEntity("H", y=5.0, x_min=0, x_max=10, layer="11")],
    )
    levels = segment_by_level(parse)
    assert len(levels) == 1
    assert "COBERTURA" in levels[0].level_name or "+1330" in levels[0].level_name


def test_no_level_text():
    """DXF with no level text -> 1 default group."""
    parse = ParseResult(
        filename="test.dxf", layers=["11"], detected_scale=0.02,
        texts=[TextEntity("V1 14x40", 10, 10, "TEXTO")],
        segments=[SegmentEntity("H", y=5.0, x_min=0, x_max=10, layer="11")],
    )
    levels = segment_by_level(parse)
    assert len(levels) == 1
    assert levels[0].level_name == "DEFAULT"
