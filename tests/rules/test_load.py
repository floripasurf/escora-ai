"""Tests for load rules LOAD-001 through LOAD-004."""

from src.rules.project import LoadParams
from src.rules.verifiers.load import (
    _verify_sobrecarga,
    _verify_static_load,
    _verify_gamma_f,
)
from tests.rules.conftest import make_project, make_slab


class TestLoad001Sobrecarga:
    def test_compliant_sobrecarga(self):
        project = make_project(
            load_params=LoadParams(
                q_sobrecarga=2.0, q_forma=0.5,
                gamma_f=1.4, gamma_concreto=25.0, pe_direito_m=2.80,
            ),
        )
        assert _verify_sobrecarga(project) == []

    def test_noncompliant_sobrecarga(self):
        """The known defect: Q_SOBRECARGA_DEFAULT=1.5 < 2.0"""
        project = make_project(
            load_params=LoadParams(
                q_sobrecarga=1.5, q_forma=0.5,
                gamma_f=1.4, gamma_concreto=25.0, pe_direito_m=2.80,
            ),
        )
        violations = _verify_sobrecarga(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "LOAD-001"
        assert violations[0].severity == "error"

    def test_no_load_params(self):
        project = make_project(load_params=None)
        project.load_params = None
        assert _verify_sobrecarga(project) == []


class TestLoad002StaticLoad:
    def test_thick_slab_passes(self):
        slab = make_slab(thickness_m=0.20)  # 25*0.20=5.0 + 0.5 + 2.0 = 7.5 > 4.0
        project = make_project(slab_panels=[slab])
        assert _verify_static_load(project) == []

    def test_very_thin_slab_fails(self):
        slab = make_slab(thickness_m=0.04)  # 25*0.04=1.0 + 0.5 + 2.0 = 3.5 < 4.0
        project = make_project(slab_panels=[slab])
        violations = _verify_static_load(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "LOAD-002"


class TestLoad004GammaF:
    def test_correct_gamma_f(self):
        project = make_project()
        assert _verify_gamma_f(project) == []

    def test_wrong_gamma_f(self):
        project = make_project(
            load_params=LoadParams(
                q_sobrecarga=2.0, q_forma=0.5,
                gamma_f=1.2, gamma_concreto=25.0, pe_direito_m=2.80,
            ),
        )
        violations = _verify_gamma_f(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "LOAD-004"
