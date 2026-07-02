"""Tests for spacing rules SPACE-001 and SPACE-002."""

from src.rules.verifiers.space import _verify_slab_spacing, _verify_cruzeta_spacing
from tests.rules.conftest import make_beam, make_project, make_shore, make_slab, rect


class TestSpace001SlabSpacing:
    def test_adequately_spaced_shores(self):
        slab = make_slab(
            polygon=rect(0, 0, 5, 5),
            thickness_m=0.12,
            shores=[make_shore(1, 1), make_shore(2, 1), make_shore(3, 1)],
        )
        project = make_project(slab_panels=[slab])
        assert _verify_slab_spacing(project) == []

    def test_excessively_spaced_shores(self):
        # thickness 0.12m -> max spacing 1.30m. Shores 2.0m apart.
        slab = make_slab(
            polygon=rect(0, 0, 5, 5),
            thickness_m=0.12,
            shores=[make_shore(0.5, 0.5), make_shore(2.5, 0.5)],
        )
        project = make_project(slab_panels=[slab])
        violations = _verify_slab_spacing(project)
        assert len(violations) >= 1
        assert violations[0].rule_id == "SPACE-001"


class TestSpace002CruzetaSpacing:
    def test_beam_shores_properly_spaced(self):
        beam = make_beam(
            shores=[make_shore(0, 0), make_shore(0.7, 0)],
        )
        project = make_project(beams=[beam])
        assert _verify_cruzeta_spacing(project) == []

    def test_beam_shores_too_far(self):
        beam = make_beam(
            shores=[make_shore(0, 0), make_shore(1.5, 0)],
        )
        project = make_project(beams=[beam])
        violations = _verify_cruzeta_spacing(project)
        assert len(violations) >= 1
        assert violations[0].rule_id == "SPACE-002"
