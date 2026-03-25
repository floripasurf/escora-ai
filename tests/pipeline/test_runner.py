import pytest
import ezdxf
from src.pipeline.runner import run_pipeline


@pytest.fixture
def synthetic_dxf(tmp_path):
    """Create a synthetic DXF in real-world meters (model space)."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Beam: two parallel horizontal lines 0.14m apart, 6m long
    msp.add_line((0, 10.0), (6.0, 10.0), dxfattribs={"layer": "11"})
    msp.add_line((0, 10.14), (6.0, 10.14), dxfattribs={"layer": "11"})

    # Pillar SOLID: 0.20m x 0.40m
    msp.add_solid(
        [(0, 9.80), (0.20, 9.80), (0.20, 10.20), (0, 10.20)],
        dxfattribs={"layer": "21"},
    )

    # Text
    msp.add_text("V1 14x40", height=0.1, dxfattribs={"layer": "TEXTO", "insert": (3.0, 10.2)})
    msp.add_text("P1", height=0.1, dxfattribs={"layer": "TEXTO", "insert": (0.1, 10.3)})
    msp.add_text("ESC 1:50", height=0.1, dxfattribs={"layer": "TEXTO", "insert": (5.0, 12.0)})

    path = tmp_path / "synthetic.dxf"
    doc.saveas(str(path))
    return str(path)


def test_pipeline_runs_end_to_end(synthetic_dxf):
    result = run_pipeline(synthetic_dxf)
    assert result.filename == "synthetic.dxf"
    assert result.scale == pytest.approx(1.0)  # real-meter coordinates auto-detected
    assert len(result.levels) >= 1
    all_elements = result.levels[0].elements
    types = [e.element_type.value for e in all_elements]
    assert "beam" in types
    assert "pillar" in types
