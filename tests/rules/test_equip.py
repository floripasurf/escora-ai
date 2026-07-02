"""Tests for equipment rules EQUIP-001 through EQUIP-005."""

from src.rules.verifiers.equip import (
    _verify_no_telescopics_above_limit,
    _verify_telescopica_capacity,
    _verify_tower_utilization,
    _verify_external_beam_constraints,
    _verify_internal_beam_constraints,
)
from tests.rules.conftest import make_beam, make_project, make_shore


class TestEquip001NoTelescopicsAboveLimit:
    def test_low_height_no_violation(self):
        project = make_project(
            pe_direito_m=3.0,
            shore_positions=[make_shore(1, 1, shore_type="telescopic")],
        )
        assert _verify_no_telescopics_above_limit(project) == []

    def test_high_pe_direito_with_telescopic_fires(self):
        project = make_project(
            pe_direito_m=5.0,
            shore_positions=[make_shore(1, 1, shore_type="telescopic")],
        )
        violations = _verify_no_telescopics_above_limit(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "EQUIP-001"

    def test_high_pe_direito_with_tower_ok(self):
        project = make_project(
            pe_direito_m=5.0,
            shore_positions=[make_shore(1, 1, shore_type="tower")],
        )
        assert _verify_no_telescopics_above_limit(project) == []


class TestEquip002TelescopicaCapacity:
    def test_within_capacity_no_violation(self):
        project = make_project(
            shore_positions=[make_shore(1, 1, utilization=0.8)],
        )
        assert _verify_telescopica_capacity(project) == []

    def test_overloaded_fires(self):
        project = make_project(
            shore_positions=[make_shore(1, 1, utilization=1.2)],
        )
        violations = _verify_telescopica_capacity(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "EQUIP-002"


class TestEquip003TowerUtilization:
    def test_optimal_utilization(self):
        project = make_project(
            shore_positions=[make_shore(1, 1, shore_type="tower", utilization=0.70)],
        )
        assert _verify_tower_utilization(project) == []

    def test_underutilized(self):
        project = make_project(
            shore_positions=[make_shore(1, 1, shore_type="tower", utilization=0.30)],
        )
        violations = _verify_tower_utilization(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "EQUIP-003"

    def test_overutilized(self):
        project = make_project(
            shore_positions=[make_shore(1, 1, shore_type="tower", utilization=0.95)],
        )
        violations = _verify_tower_utilization(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "EQUIP-003"


class TestEquip004ExternalBeamConstraints:
    def test_small_external_beam_ok(self):
        beam = make_beam(
            width_m=0.20, height_m=0.50, length_m=2.5,
            is_perimeter=True,
            shores=[make_shore(1, 0)],
        )
        project = make_project(beams=[beam])
        assert _verify_external_beam_constraints(project) == []

    def test_large_external_beam_telescopic_fires(self):
        beam = make_beam(
            width_m=0.40, height_m=0.70, length_m=4.0,
            is_perimeter=True,
            shores=[make_shore(1, 0)],
        )
        project = make_project(beams=[beam])
        violations = _verify_external_beam_constraints(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "EQUIP-004"

    def test_large_external_beam_with_tower_ok(self):
        beam = make_beam(
            width_m=0.40, height_m=0.70, length_m=4.0,
            is_perimeter=True,
            shores=[make_shore(1, 0, shore_type="tower")],
        )
        project = make_project(beams=[beam])
        assert _verify_external_beam_constraints(project) == []


class TestEquip005InternalBeamConstraints:
    def test_short_internal_beam_ok(self):
        beam = make_beam(
            width_m=0.20, height_m=0.50, length_m=4.0,
            shores=[make_shore(1, 0)],
        )
        project = make_project(beams=[beam])
        assert _verify_internal_beam_constraints(project) == []

    def test_long_internal_beam_telescopic_fires(self):
        beam = make_beam(
            width_m=0.50, height_m=0.80, length_m=12.0,
            shores=[make_shore(1, 0)],
        )
        project = make_project(beams=[beam])
        violations = _verify_internal_beam_constraints(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "EQUIP-005"

    def test_medium_internal_beam_needs_mixed(self):
        beam = make_beam(
            width_m=0.20, height_m=0.50, length_m=8.0,
            shores=[make_shore(1, 0)],
        )
        project = make_project(beams=[beam])
        violations = _verify_internal_beam_constraints(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "EQUIP-005"
        assert "misto" in violations[0].message.lower()
