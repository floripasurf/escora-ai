"""GEOM-008: escala de coordenadas determinada por fallback exige revisão."""
from src.rules.verifiers.geom import _verify_scale_method

from tests.rules.conftest import make_project


def _project_with_method(method: str):
    project = make_project()
    project.scale_method = method
    return project


def test_reliable_methods_pass():
    for method in ("insunits", "dimension", "range", "override", ""):
        assert _verify_scale_method(_project_with_method(method)) == []


def test_default_scale_flags_error():
    violations = _verify_scale_method(_project_with_method("default"))
    assert len(violations) == 1
    assert violations[0].rule_id == "GEOM-008"
    assert violations[0].severity == "error"


def test_text_scale_flags_error():
    violations = _verify_scale_method(_project_with_method("text"))
    assert len(violations) == 1
    assert "anotação" in violations[0].message
