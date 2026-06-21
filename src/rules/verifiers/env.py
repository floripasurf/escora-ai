"""Envelope verifiers: ENV-001.

Calibration envelope checks from Orguel project analysis.
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
        calibration="Orguel 2026-04-07 (n=12)",
    ),
    description_pt="kg/m³ total no envelope [12, 16]",
    severity="warning",
)

KG_M3_MIN = 12.0
KG_M3_MAX = 16.0


def _verify_kg_m3_envelope(project: "RuleProject") -> list[Violation]:
    """DESABILITADO (não emite violação) — banda [12,16] miscalibrada p/ a base.

    A banda foi calibrada noutra base (BOM total Orguel / volume de concreto),
    mas aqui kg/m³ usa peso vertical das escoras sobre volume escorado. Nessa
    base até projetos normais ficam ~3-7 kg/m³ (CFL=6.7, CVS=5.1), então a regra
    falso-positivava. kg/m³ vira diagnóstico (runner.consumption_diagnostics) e a
    recalibração da banda contra a referência Orguel é follow-up. Sem severidade
    "info" no rule engine (só error/warning), a regra fica como no-op até lá.
    """
    return []


REGISTRY.register(_ENV_001, _verify_kg_m3_envelope)
