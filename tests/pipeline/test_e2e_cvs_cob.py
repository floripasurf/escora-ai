"""End-to-end regression test using the real CVS-COB DXF.

This test verifies that the generic pipeline can interpret
the same DXF that was previously handled by hardcoded scripts.
"""

import pytest
from pathlib import Path
from src.pipeline.runner import run_pipeline
from src.models.pipeline_models import ElementType

DXF_PATH = Path(__file__).parent.parent / "fixtures" / "CVS-COB-FOR-006-R00.DXF"


@pytest.mark.skipif(not DXF_PATH.exists(), reason="CVS-COB DXF not in fixtures")
class TestCVSCOBRegression:
    def test_pipeline_completes(self):
        result = run_pipeline(str(DXF_PATH))
        assert len(result.levels) >= 1
        assert len(result.errors) == 0

    def test_detects_beams(self):
        result = run_pipeline(str(DXF_PATH))
        all_elements = result.levels[0].elements
        beams = [e for e in all_elements if e.element_type == ElementType.BEAM]
        # CVS-COB has ~22 beams -- we expect at least 15 detected generically
        assert len(beams) >= 15

    def test_detects_pillars(self):
        result = run_pipeline(str(DXF_PATH))
        all_elements = result.levels[0].elements
        pillars = [e for e in all_elements if e.element_type == ElementType.PILLAR]
        # CVS-COB has 25 pillars -- we expect at least 20 detected
        assert len(pillars) >= 20

    def test_detects_scale(self):
        result = run_pipeline(str(DXF_PATH))
        # DXF is in real-world meters (model space), auto-detected as scale=1.0
        assert result.scale == pytest.approx(1.0)

    def test_calculation_produces_results(self):
        result = run_pipeline(str(DXF_PATH))
        assert result.calculation is not None
        assert result.calculation.total_shores > 0

    def test_beam_geometry_populated(self):
        result = run_pipeline(str(DXF_PATH))
        all_elements = result.levels[0].elements
        beams = [e for e in all_elements if e.element_type == ElementType.BEAM]
        for beam in beams:
            assert len(beam.geometry) == 2

    def test_pillar_geometry_populated(self):
        result = run_pipeline(str(DXF_PATH))
        all_elements = result.levels[0].elements
        pillars = [e for e in all_elements if e.element_type == ElementType.PILLAR]
        for pillar in pillars:
            assert len(pillar.geometry) == 1
