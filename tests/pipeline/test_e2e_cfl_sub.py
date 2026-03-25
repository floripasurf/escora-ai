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

    def test_calculation_produces_results(self):
        result = run_pipeline(str(DXF_PATH))
        assert result.calculation is not None
        assert result.calculation.total_shores > 0
        assert result.calculation.total_load_kn > 0

    def test_calculation_has_beam_results(self):
        result = run_pipeline(str(DXF_PATH))
        assert result.calculation is not None
        assert len(result.calculation.beam_results) > 0

    def test_calculation_is_valid(self):
        result = run_pipeline(str(DXF_PATH))
        assert result.calculation is not None
        assert isinstance(result.calculation.is_valid, bool)

    def test_beam_geometry_populated(self):
        result = run_pipeline(str(DXF_PATH))
        all_elements = result.levels[0].elements
        beams = [e for e in all_elements if e.element_type == ElementType.BEAM]
        for beam in beams:
            assert len(beam.geometry) == 2, f"Beam {beam.name} has empty geometry"

    def test_pillar_geometry_populated(self):
        result = run_pipeline(str(DXF_PATH))
        all_elements = result.levels[0].elements
        pillars = [e for e in all_elements if e.element_type == ElementType.PILLAR]
        for pillar in pillars:
            assert len(pillar.geometry) == 1, f"Pillar {pillar.name} has empty geometry"
