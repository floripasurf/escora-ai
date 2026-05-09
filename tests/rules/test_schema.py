"""Tests for src/rules/schema.py — Source, Rule, Violation, RuleRegistry."""
import pytest
from pydantic import ValidationError

from src.rules.schema import (
    REGISTRY, Rule, RuleRegistry, Source, Violation,
)


class TestSource:
    def test_requires_type_and_ref(self):
        s = Source(type="norm", ref="NBR 15696:2009 §4.2")
        assert s.type == "norm"
        assert s.ref == "NBR 15696:2009 §4.2"
        assert s.calibration is None

    def test_rejects_missing_type(self):
        with pytest.raises(ValidationError):
            Source(ref="NBR 15696")  # type: ignore

    def test_rejects_missing_ref(self):
        with pytest.raises(ValidationError):
            Source(type="norm")  # type: ignore

    def test_rejects_invalid_type(self):
        with pytest.raises(ValidationError):
            Source(type="invented", ref="foo")  # type: ignore

    def test_with_calibration(self):
        s = Source(
            type="engineer_qa", ref="Q&A #5",
            calibration="Supplier 2026-04-07 (n=12)",
        )
        assert s.calibration == "Supplier 2026-04-07 (n=12)"


class TestViolation:
    def test_valid_rule_id(self):
        v = Violation(
            rule_id="GEOM-001", severity="error",
            message="test", actual_value=0.5, limit_value=0.7,
        )
        assert v.rule_id == "GEOM-001"

    def test_rejects_invalid_rule_id(self):
        with pytest.raises(ValidationError):
            Violation(
                rule_id="BAD-ID", severity="error",
                message="test", actual_value=0, limit_value=0,
            )

    def test_severity_error_and_warning(self):
        v1 = Violation(
            rule_id="LOAD-001", severity="error",
            message="t", actual_value=0, limit_value=0,
        )
        v2 = Violation(
            rule_id="LOAD-002", severity="warning",
            message="t", actual_value=0, limit_value=0,
        )
        assert v1.severity == "error"
        assert v2.severity == "warning"

    def test_rejects_invalid_severity(self):
        with pytest.raises(ValidationError):
            Violation(
                rule_id="GEOM-001", severity="BLOCK",  # type: ignore
                message="t", actual_value=0, limit_value=0,
            )


class TestRule:
    def test_valid_rule(self):
        r = Rule(
            id="GEOM-001", category="GEOM",
            source=Source(type="norm", ref="NBR 6118:2023"),
            description_pt="Teste",
        )
        assert r.id == "GEOM-001"
        assert r.severity == "error"

    def test_rejects_mismatched_category(self):
        with pytest.raises(ValidationError):
            Rule(
                id="LOAD-001", category="GEOM",
                source=Source(type="norm", ref="test"),
                description_pt="Teste",
            )

    def test_rejects_invalid_id_pattern(self):
        with pytest.raises(ValidationError):
            Rule(
                id="INVALID", category="GEOM",
                source=Source(type="norm", ref="test"),
                description_pt="Teste",
            )


class TestRuleRegistry:
    def test_register_and_run_all(self):
        reg = RuleRegistry()
        rule = Rule(
            id="ENV-001", category="ENV",
            source=Source(type="norm", ref="test"),
            description_pt="Teste",
            severity="warning",
        )

        def verifier(project):
            return [Violation(
                rule_id="ENV-001", severity="warning",
                message="test violation",
                actual_value=20, limit_value=16,
            )]

        reg.register(rule, verifier)
        assert len(reg.all()) == 1

        violations = reg.check_all(None)
        assert len(violations) == 1
        assert violations[0].rule_id == "ENV-001"

    def test_duplicate_registration_raises(self):
        reg = RuleRegistry()
        rule = Rule(
            id="ENV-001", category="ENV",
            source=Source(type="norm", ref="test"),
            description_pt="Teste",
        )
        reg.register(rule, lambda p: [])
        with pytest.raises(ValueError, match="already registered"):
            reg.register(rule, lambda p: [])

    def test_by_category(self):
        reg = RuleRegistry()
        r1 = Rule(
            id="GEOM-001", category="GEOM",
            source=Source(type="norm", ref="test"),
            description_pt="Teste",
        )
        r2 = Rule(
            id="LOAD-001", category="LOAD",
            source=Source(type="norm", ref="test"),
            description_pt="Teste",
        )
        reg.register(r1, lambda p: [])
        reg.register(r2, lambda p: [])

        geom_rules = reg.by_category("GEOM")
        assert len(geom_rules) == 1
        assert geom_rules[0].id == "GEOM-001"

    def test_errors_sort_before_warnings(self):
        reg = RuleRegistry()
        r1 = Rule(
            id="LOAD-001", category="LOAD",
            source=Source(type="norm", ref="test"),
            description_pt="Teste", severity="warning",
        )
        r2 = Rule(
            id="GEOM-001", category="GEOM",
            source=Source(type="norm", ref="test"),
            description_pt="Teste", severity="error",
        )
        reg.register(r1, lambda p: [Violation(
            rule_id="LOAD-001", severity="warning",
            message="w", actual_value=0, limit_value=0,
        )])
        reg.register(r2, lambda p: [Violation(
            rule_id="GEOM-001", severity="error",
            message="e", actual_value=0, limit_value=0,
        )])

        violations = reg.check_all(None)
        assert violations[0].severity == "error"
        assert violations[1].severity == "warning"

    def test_verifier_crash_produces_violation(self):
        reg = RuleRegistry()
        rule = Rule(
            id="GEOM-001", category="GEOM",
            source=Source(type="norm", ref="test"),
            description_pt="Teste",
        )

        def crasher(project):
            raise RuntimeError("boom")

        reg.register(rule, crasher)
        violations = reg.check_all(None)
        assert len(violations) == 1
        assert "falhou" in violations[0].message
        assert "boom" in violations[0].message
