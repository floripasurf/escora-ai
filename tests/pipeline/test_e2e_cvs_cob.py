"""End-to-end regression test using the real CVS-COB DXF.

This test verifies that the generic pipeline can interpret
the same DXF that was previously handled by hardcoded scripts.
"""

import pytest
from pathlib import Path
from shapely.geometry import LineString

from src.models.plywood import default_plywood_spec
from src.pipeline.runner import run_pipeline
from src.pipeline.stage_calculate import (
    _axis_aligned_perimeter_ratio,
    _secondary_vm_spacing_m,
)
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

    def test_secondary_vm_spacing_uses_manual_plywood_step(self):
        spacing = _secondary_vm_spacing_m(0.18, default_plywood_spec())
        assert spacing == pytest.approx(0.488)

    def test_filters_noisy_nonorthogonal_slab_contours(self):
        result = run_pipeline(str(DXF_PATH), mode="price")
        assert result.calculation is not None

        noisy = []
        for slab_idx, sr in enumerate(result.calculation.slab_results, 1):
            coords = list(sr.polygon.exterior.coords)
            axis_ratio, _ = _axis_aligned_perimeter_ratio(sr.polygon)
            minx, miny, maxx, maxy = sr.polygon.bounds
            bbox_area = (maxx - minx) * (maxy - miny)
            rectangularity = sr.polygon.area / bbox_area if bbox_area else 1.0
            if (
                sr.area_m2 < 25
                and len(coords) >= 24
                and axis_ratio < 0.50
                and rectangularity < 0.75
            ):
                noisy.append((slab_idx, sr.area_m2, len(coords), axis_ratio))

        assert noisy == []

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


@pytest.mark.skipif(not DXF_PATH.exists(), reason="CVS-COB DXF not in fixtures")
class TestMethodologyTraceability:
    """Rastreabilidade da metodologia anexada ao PipelineResult (§28.9)."""

    def test_default_origin_is_locadora_profile(self):
        result = run_pipeline(str(DXF_PATH))
        assert result.methodology is not None
        assert result.methodology["origem"] == "perfil_locadora"
        assert "laje_layout" in result.methodology
        assert "efetivo" in result.methodology

    def test_injected_profile_marks_override(self):
        from src.models.methodology import PROFILE_ORGUEL_LINE_FIRST
        result = run_pipeline(
            str(DXF_PATH), methodology=PROFILE_ORGUEL_LINE_FIRST,
        )
        # Fix do review: methodology injetado (sem slab_layout_mode) e override.
        assert result.methodology["origem"] == "override"
        assert result.methodology["laje_layout"] == "line_first"

    def test_explicit_slab_layout_marks_override(self):
        result = run_pipeline(str(DXF_PATH), slab_layout_mode="line_first")
        assert result.methodology["origem"] == "override"
