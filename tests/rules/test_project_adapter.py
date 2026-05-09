"""Tests for src/rules/project.py — RuleProject adapter."""
import pytest

from src.rules.project import IncompleteDataError, RuleProject


class TestRuleProjectFromPipelineResult:
    def test_raises_on_none_calculation(self):
        """from_pipeline_result must raise IncompleteDataError, not default."""

        class FakeResult:
            calculation = None
            levels = []

        with pytest.raises(IncompleteDataError, match="calculation is None"):
            RuleProject.from_pipeline_result(FakeResult())
