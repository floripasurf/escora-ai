"""Rule, Source, Violation schema for Escora.AI.

Every engineering rule in the system is represented here. The
registry is module-level and singleton-imported as REGISTRY.

Design principles:
- Source citation is mandatory on every Rule (AGENTS.md v3 schema).
- Verifiers are pure functions: RuleProject -> list[Violation].
- Severity is a closed enum: error or warning.
- Rule IDs follow the pattern <CATEGORY>-<NUMBER>.
"""
from __future__ import annotations

import re
from typing import Any, Literal, Optional, Protocol, TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator, model_validator

if TYPE_CHECKING:
    from src.rules.project import RuleProject


_RULE_ID_PATTERN = re.compile(
    r"^(GEOM|SPACE|STRUCT|LOAD|EQUIP|ENV|DECIDE|OUTPUT|OP)-\d{3,4}$"
)

SourceType = Literal["norm", "manual", "dxf_pattern", "engineer_qa"]
Severity = Literal["error", "warning"]
Category = Literal[
    "GEOM", "SPACE", "STRUCT", "LOAD", "EQUIP", "ENV", "DECIDE", "OUTPUT", "OP"
]


class Source(BaseModel):
    """Citation for any rule or numeric value — AGENTS.md v3 schema verbatim."""
    type: SourceType
    ref: str = Field(
        ...,
        description=(
            "Citation: 'NBR 15696:2009 §4.2' or 'Orguel p.86' or "
            "'Engineer Q&A #5'"
        ),
    )
    calibration: Optional[str] = Field(
        None,
        description="When applicable: 'Orguel 2026-04-07 (n=12)'",
    )

    model_config = {"frozen": True}


class Violation(BaseModel):
    """A specific rule violation found in a project."""
    rule_id: str
    severity: Severity
    message: str = Field(..., description="Portuguese explanation")
    element_id: Optional[str] = None
    actual_value: Any = None
    limit_value: Any = None
    location: Optional[tuple[float, float]] = Field(
        None, description="DXF model-space XY"
    )

    @field_validator("rule_id")
    @classmethod
    def _validate_rule_id(cls, v: str) -> str:
        if not _RULE_ID_PATTERN.match(v):
            raise ValueError(
                f"Rule ID '{v}' does not match pattern <CATEGORY>-<NUMBER>"
            )
        return v


class Rule(BaseModel):
    """An engineering rule, citation-traceable."""
    id: str
    category: Category
    source: Source
    description_pt: str
    severity: Severity = "error"

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        if not _RULE_ID_PATTERN.match(v):
            raise ValueError(
                f"Rule ID '{v}' does not match pattern <CATEGORY>-<NUMBER>"
            )
        return v

    @model_validator(mode="after")
    def _category_matches_id(self) -> "Rule":
        prefix = self.id.split("-")[0]
        if prefix != self.category:
            raise ValueError(
                f"Rule id prefix '{prefix}' does not match "
                f"category '{self.category}'"
            )
        return self


class Verifier(Protocol):
    def __call__(self, project: "RuleProject") -> list[Violation]: ...


class RuleRegistry:
    """Module-level singleton holding all registered rules and verifiers."""

    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}
        self._verifiers: dict[str, Verifier] = {}

    def register(self, rule: Rule, verifier: Verifier) -> None:
        if rule.id in self._rules:
            raise ValueError(f"Rule {rule.id} already registered")
        self._rules[rule.id] = rule
        self._verifiers[rule.id] = verifier

    def get(self, rule_id: str) -> Rule:
        return self._rules[rule_id]

    def all(self) -> list[Rule]:
        return list(self._rules.values())

    def by_category(self, category: Category) -> list[Rule]:
        return [r for r in self._rules.values() if r.category == category]

    def check_all(self, project: "RuleProject") -> list[Violation]:
        violations: list[Violation] = []
        for rule_id, verifier in self._verifiers.items():
            try:
                violations.extend(verifier(project))
            except Exception as e:
                violations.append(Violation(
                    rule_id=rule_id,
                    severity="error",
                    message=(
                        f"Verificador da regra {rule_id} falhou "
                        f"durante execução: {type(e).__name__}: {e}"
                    ),
                    actual_value=str(e),
                    limit_value="Verificador executa sem erro",
                ))
        # Errors before warnings, then by rule_id
        violations.sort(key=lambda v: (v.severity != "error", v.rule_id))
        return violations


REGISTRY = RuleRegistry()
