"""Tests for envelope rules ENV-001."""

from src.rules.verifiers.env import _verify_kg_m3_envelope
from tests.rules.conftest import make_project


class TestEnv001KgM3:
    def test_within_envelope(self):
        project = make_project(
            total_volume_m3=100.0,
            total_shores_weight_kg=1400.0,  # 14 kg/m³
        )
        assert _verify_kg_m3_envelope(project) == []

    def test_below_envelope_no_violation_disabled(self):
        # ENV-001 desabilitado: a banda [12,16] não casa com a base do motor
        # (vertical / volume escorado) — falso-positivava até projeto normal
        # (CFL=6.7, CVS=5.1). Recalibração c/ referência Orguel = follow-up.
        project = make_project(
            total_volume_m3=100.0,
            total_shores_weight_kg=800.0,  # 8 kg/m³ (antes: violava)
        )
        assert _verify_kg_m3_envelope(project) == []

    def test_above_envelope_no_violation_disabled(self):
        project = make_project(
            total_volume_m3=100.0,
            total_shores_weight_kg=2000.0,  # 20 kg/m³ (antes: violava)
        )
        assert _verify_kg_m3_envelope(project) == []

    def test_zero_volume_no_violation(self):
        project = make_project(total_volume_m3=0.0, total_shores_weight_kg=0.0)
        assert _verify_kg_m3_envelope(project) == []

    def test_env001_not_registered(self):
        # #3 codex: a regra está desabilitada → não deve aparecer no registry
        # (recalibração Orguel = follow-up antes de re-registrar).
        from src.rules.schema import REGISTRY
        assert "ENV-001" not in {r.id for r in REGISTRY.all()}
