"""Tests for envelope rules ENV-001."""
import pytest

from src.rules.verifiers.env import _verify_kg_m3_envelope
from tests.rules.conftest import make_project


class TestEnv001KgM3:
    def test_within_envelope(self):
        project = make_project(
            total_volume_m3=100.0,
            total_shores_weight_kg=1400.0,  # 14 kg/m³
        )
        assert _verify_kg_m3_envelope(project) == []

    def test_below_envelope(self):
        project = make_project(
            total_volume_m3=100.0,
            total_shores_weight_kg=800.0,  # 8 kg/m³
        )
        violations = _verify_kg_m3_envelope(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "ENV-001"
        assert "abaixo" in violations[0].message

    def test_above_envelope(self):
        project = make_project(
            total_volume_m3=100.0,
            total_shores_weight_kg=2000.0,  # 20 kg/m³
        )
        violations = _verify_kg_m3_envelope(project)
        assert len(violations) == 1
        assert "acima" in violations[0].message

    def test_zero_volume_no_violation(self):
        project = make_project(total_volume_m3=0.0, total_shores_weight_kg=0.0)
        assert _verify_kg_m3_envelope(project) == []
