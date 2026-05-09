"""Regression: every calibration DXF runs to completion."""
import pytest


@pytest.mark.slow
def test_pipeline_runs_to_completion(calibration_dxf):
    """Each DXF should run the full pipeline without crashing."""
    project_id, dxf_path = calibration_dxf
    from src.pipeline.runner import run_pipeline
    result = run_pipeline(str(dxf_path))
    assert result is not None, f"{project_id} returned None"
    assert result.filename, f"{project_id} has empty filename"
