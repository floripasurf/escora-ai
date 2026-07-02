"""Tests for structural rules STRUCT-001 and STRUCT-002."""

from src.rules.verifiers.struct import (
    _verify_beam_intersection_support,
    _verify_forcado_not_on_cantilever,
)
from tests.rules.conftest import make_beam, make_pillar, make_project, make_shore


class TestStruct001BeamIntersection:
    def test_intersection_with_support_nearby(self):
        b1 = make_beam(centerline=[(0, 5), (10, 5)], length_m=10.0)
        b2 = make_beam(centerline=[(5, 0), (5, 10)], length_m=10.0)
        project = make_project(
            beams=[b1, b2],
            shore_positions=[make_shore(5.0, 5.0)],
        )
        assert _verify_beam_intersection_support(project) == []

    def test_intersection_without_support(self):
        b1 = make_beam(centerline=[(0, 5), (10, 5)], length_m=10.0)
        b2 = make_beam(centerline=[(5, 0), (5, 10)], length_m=10.0)
        project = make_project(
            beams=[b1, b2],
            shore_positions=[make_shore(0.0, 0.0)],  # far away
        )
        violations = _verify_beam_intersection_support(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "STRUCT-001"

    def test_intersection_with_pillar_no_violation(self):
        b1 = make_beam(centerline=[(0, 5), (10, 5)], length_m=10.0)
        b2 = make_beam(centerline=[(5, 0), (5, 10)], length_m=10.0)
        project = make_project(
            beams=[b1, b2],
            pillars=[make_pillar(5.0, 5.0)],
            shore_positions=[],
        )
        assert _verify_beam_intersection_support(project) == []


class TestStruct002ForcadoNotOnCantilever:
    def test_no_cantilever_no_violation(self):
        beam = make_beam(
            shores=[make_shore(0, 0)],
            is_cantilever_start=False,
            is_cantilever_end=False,
        )
        project = make_project(beams=[beam])
        assert _verify_forcado_not_on_cantilever(project) == []

    def test_shore_at_cantilever_tip_fires(self):
        beam = make_beam(
            centerline=[(0, 0), (5, 0)],
            shores=[make_shore(0.05, 0)],  # very close to start
            is_cantilever_start=True,
        )
        project = make_project(beams=[beam])
        violations = _verify_forcado_not_on_cantilever(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "STRUCT-002"

    def test_shore_away_from_cantilever_ok(self):
        beam = make_beam(
            centerline=[(0, 0), (5, 0)],
            shores=[make_shore(2.5, 0)],  # middle of beam
            is_cantilever_start=True,
        )
        project = make_project(beams=[beam])
        assert _verify_forcado_not_on_cantilever(project) == []
