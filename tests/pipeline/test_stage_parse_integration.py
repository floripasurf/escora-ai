import pytest
import ezdxf
from src.pipeline.stage_parse import parse_dxf


@pytest.fixture
def simple_dxf(tmp_path):
    """Create a minimal DXF with known entities for testing."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add("VIGAS", color=1)
    doc.layers.add("TEXTO", color=7)

    # Two parallel horizontal lines (beam edges)
    msp.add_line((0, 0), (100, 0), dxfattribs={"layer": "VIGAS"})
    msp.add_line((0, 2.8), (100, 2.8), dxfattribs={"layer": "VIGAS"})

    # A SOLID rectangle (pillar)
    msp.add_solid([(40, 40), (44, 40), (44, 48), (40, 48)], dxfattribs={"layer": "PILARES"})

    # Text annotations
    msp.add_text("V1 14x40", height=2.0, dxfattribs={"layer": "TEXTO", "insert": (10, 5)})
    msp.add_text("ESC 1:50", height=2.0, dxfattribs={"layer": "TEXTO", "insert": (80, 80)})

    path = tmp_path / "test.dxf"
    doc.saveas(str(path))
    return str(path)


def test_parse_extracts_all_entities(simple_dxf):
    result = parse_dxf(simple_dxf)
    assert result.filename == "test.dxf"
    assert len(result.raw_entities) > 0
    assert len(result.texts) >= 2  # V1 and ESC


def test_parse_detects_scale(simple_dxf):
    result = parse_dxf(simple_dxf)
    assert result.detected_scale == pytest.approx(0.02)  # 1:50


def test_parse_extracts_layers(simple_dxf):
    result = parse_dxf(simple_dxf)
    assert "VIGAS" in result.layers
    assert "TEXTO" in result.layers
