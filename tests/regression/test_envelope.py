"""Regression: kg/m³ envelope check [12, 16]."""
import pytest


@pytest.mark.slow
def test_kg_per_m3_envelope(calibration_dxf):
    """BOM mass / concrete volume should be in [12, 16] kg/m³."""
    project_id, dxf_path = calibration_dxf
    from src.pipeline.runner import run_pipeline
    result = run_pipeline(str(dxf_path))

    if result.calculation is None:
        pytest.skip(f"{project_id}: calculation stage did not run")

    calc = result.calculation
    if calc.total_volume_m3 <= 0:
        pytest.skip(f"{project_id}: zero volume (no slab panels?)")

    total_weight = sum(
        getattr(sr, 'shores_weight_kg', 0.0) for sr in calc.slab_results
    ) + sum(
        getattr(br, 'shores_weight_kg', 0.0) for br in calc.beam_results
    )
    if total_weight <= 0:
        pytest.skip(f"{project_id}: zero weight (BOM not populated)")

    kg_m3 = total_weight / calc.total_volume_m3
    assert 12 <= kg_m3 <= 16, (
        f"{project_id}: kg/m³ = {kg_m3:.1f}, outside [12, 16] envelope"
    )
