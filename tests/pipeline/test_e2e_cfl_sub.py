"""End-to-end regression test using the CFL-SUB DXF.

This DXF has many pillars (83 per manual count) including
both rectangular SOLIDs and circular columns (CIRCLE entities).
"""

import pytest
from pathlib import Path
from shapely.geometry import LineString
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

    def test_detects_square_section_pillars(self):
        result = run_pipeline(str(DXF_PATH))
        all_elements = result.levels[0].elements
        pillars = [e for e in all_elements if e.element_type == ElementType.PILLAR]
        # Some pillars have square sections (width == height)
        # Note: r=0.25 circles on layer 1 are level markers (cota de nível),
        # not circular pillars — they have cross patterns and elevation text
        square = [p for p in pillars if p.section_width_m == p.section_height_m]
        assert len(square) >= 3

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

    def test_final_vm_grid_has_no_failed_segments(self):
        result = run_pipeline(str(DXF_PATH), mode="price")
        assert result.calculation is not None

        failed = []
        for slab_idx, sr in enumerate(result.calculation.slab_results, 1):
            grid = getattr(sr, "vm_grid", None)
            if not grid:
                continue
            for seg in grid.segments:
                if not seg.passes_moment or not seg.passes_deflection:
                    failed.append((slab_idx, seg))

        assert failed == []

    def test_final_vm_grid_segments_stay_inside_slab_polygons(self):
        result = run_pipeline(str(DXF_PATH), mode="price")
        assert result.calculation is not None

        outside = []
        for slab_idx, sr in enumerate(result.calculation.slab_results, 1):
            grid = getattr(sr, "vm_grid", None)
            if not grid:
                continue
            slab_area = sr.polygon.buffer(1e-5)
            for seg in grid.segments:
                if not slab_area.covers(LineString([seg.start, seg.end])):
                    outside.append((slab_idx, seg))

        assert outside == []

    def test_real_slab_panels_have_vm_grid(self):
        result = run_pipeline(str(DXF_PATH), mode="price")
        assert result.calculation is not None

        missing = []
        for slab_idx, sr in enumerate(result.calculation.slab_results, 1):
            if sr.area_m2 < 1.0:
                continue
            grid = getattr(sr, "vm_grid", None)
            if not grid or not getattr(grid, "segments", []):
                missing.append((slab_idx, round(sr.area_m2, 2), len(sr.shores)))

        assert missing == []

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
