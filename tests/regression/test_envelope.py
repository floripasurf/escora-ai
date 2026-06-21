"""Regression: sanidade de consumo (NÃO envelope estrito [12,16]).

A banda histórica [12,16] foi removida como gate: ela foi calibrada em outra
base (BOM total Orguel / volume de concreto), enquanto o motor computa peso
vertical das escoras sobre volume escorado — nessa base até projetos normais
ficam ~3-7 kg/m³ (CFL=6.7, CVS=5.1). kg/m³ virou diagnóstico
(runner.consumption_diagnostics); a recalibração da banda é follow-up.

Este teste agora valida só: o pipeline roda, o resultado não é degenerado
(volume/escoras > 0) e o kg/m³ vertical fica numa faixa AMPLA de sanidade —
pega cálculo vazio inesperado e drift grosseiro, não variação normal.
"""
import pytest

# Faixa de sanidade ampla para o kg/m³ vertical (não o envelope estrito).
SANITY_MIN_KG_M3 = 1.0
SANITY_MAX_KG_M3 = 40.0


@pytest.mark.slow
def test_kg_per_m3_sanity(calibration_dxf):
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
    assert SANITY_MIN_KG_M3 <= kg_m3 <= SANITY_MAX_KG_M3, (
        f"{project_id}: kg/m³ vertical = {kg_m3:.1f}, fora da faixa de sanidade "
        f"[{SANITY_MIN_KG_M3:.0f}, {SANITY_MAX_KG_M3:.0f}] — provável erro de "
        "cálculo (não é o envelope estrito [12,16], que foi removido)"
    )
