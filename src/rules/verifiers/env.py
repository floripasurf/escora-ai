"""Envelope verifiers: ENV-001.

Calibration envelope checks from Supplier project analysis.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.rules.schema import REGISTRY, Rule, Source, Violation

if TYPE_CHECKING:
    from src.rules.project import RuleProject


# --- ENV-001: kg/m³ in [12, 16] ---

_ENV_001 = Rule(
    id="ENV-001",
    category="ENV",
    source=Source(
        type="engineer_qa",
        ref="Engineer Q&A #8",
        calibration="Supplier 2026-04-07 (n=12)",
    ),
    description_pt="kg/m³ total no envelope [12, 16]",
    severity="warning",
)

KG_M3_MIN = 12.0
KG_M3_MAX = 16.0


def _verify_kg_m3_envelope(project: "RuleProject") -> list[Violation]:
    if project.total_volume_m3 <= 0:
        return []
    kg_m3 = project.total_shores_weight_kg / project.total_volume_m3
    if kg_m3 < KG_M3_MIN - 0.1:
        return [Violation(
            rule_id="ENV-001",
            severity="warning",
            message=(
                f"kg/m³ = {kg_m3:.1f}, abaixo do envelope mínimo "
                f"de {KG_M3_MIN} (possível subdimensionamento)"
            ),
            actual_value=round(kg_m3, 1),
            limit_value=f"[{KG_M3_MIN}, {KG_M3_MAX}]",
        )]
    elif kg_m3 > KG_M3_MAX + 0.1:
        return [Violation(
            rule_id="ENV-001",
            severity="warning",
            message=(
                f"kg/m³ = {kg_m3:.1f}, acima do envelope máximo "
                f"de {KG_M3_MAX} (possível superdimensionamento)"
            ),
            actual_value=round(kg_m3, 1),
            limit_value=f"[{KG_M3_MIN}, {KG_M3_MAX}]",
        )]
    return []


REGISTRY.register(_ENV_001, _verify_kg_m3_envelope)
