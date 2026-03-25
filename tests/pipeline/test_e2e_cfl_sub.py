"""End-to-end regression test using the CFL-SUB DXF.

This DXF has many pillars (83 per manual count) including
both rectangular SOLIDs and circular columns (CIRCLE entities).
"""

import pytest
from pathlib import Path
from src.pipeline.runner import run_pipeline
from src.models.pipeline_models import ElementType

DXF_PATH = Path(__file__).parent.parent / "fixtures" / "CFL-SUB-FOR-0casa-SFGL.DXF"


@pytest.mark.skipif(not DXF_PATH.exists(), reason="CFL-SUB DXF not in fixtures")
class TestCFLSUBRegression:
    def test_pipeline_completes(self):
        result = run_pipeline(str(DXF_PATH))
        assert len(result.levels) >= 1
        assert len(result.errors) == 0

    def test_detects_beams(self):
        result = run_pipeline(str(DXF_PATH))
        all_elements = result.levels[0].elements
        beams = [e for e in all_elements if e.element_type == ElementType.BEAM]
        # CFL-SUB has many beams — expect at least 30 detected
        assert len(beams) >= 30

    def test_detects_pillars(self):
        result = run_pipeline(str(DXF_PATH))
        all_elements = result.levels[0].elements
        pillars = [e for e in all_elements if e.element_type == ElementType.PILLAR]
        # CFL-SUB has 83 pillars (manual count) — expect at least 60 detected
        assert len(pillars) >= 60

    def test_detects_circular_pillars(self):
        result = run_pipeline(str(DXF_PATH))
        all_elements = result.levels[0].elements
        pillars = [e for e in all_elements if e.element_type == ElementType.PILLAR]
        # Some pillars are circular (diameter == width == height)
        circular = [p for p in pillars if p.section_width_m == p.section_height_m]
        assert len(circular) >= 10

    def test_detects_scale(self):
        result = run_pipeline(str(DXF_PATH))
        assert result.scale == pytest.approx(1.0)
