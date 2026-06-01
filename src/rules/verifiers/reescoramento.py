"""Reescoramento / desforma rules — DECIDE-001, DECIDE-002 (manual §26).

Implementa items 9 e 10 da secao 26 do manual:

- DECIDE-001: Fator alfa Doka so deve ser calculado quando houver dados
  reais de fcj/Ec, carga final e carga de construcao, com aprovacao do
  calculista. Caso contrario, gera pendencia em vez de assumir valores.

- DECIDE-002: Ciclo de remocao/remanejamento de escoramento usa 14 dias
  como piso normativo padrao (NBR 14931 + NBR 15696). Reducao abaixo
  disso so com analise do sistema, comprovacao de fcj/Ec e aprovacao
  do responsavel tecnico.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.rules.schema import REGISTRY, Rule, Source, Violation

if TYPE_CHECKING:
    from src.rules.project import RuleProject


# Piso normativo padrao (NBR 14931, NBR 15696, manual §26 item 10).
DESFORMA_MIN_DIAS = 14


# ---------------------------------------------------------------------------
# DECIDE-001: Fator alfa Doka como pendencia se faltar dados
# ---------------------------------------------------------------------------

_DECIDE_001 = Rule(
    id="DECIDE-001",
    category="DECIDE",
    source=Source(
        type="manual",
        ref="Manual §26 item 9 / Doka Cimbra D1 2014",
        calibration=None,
    ),
    description_pt=(
        "Fator alfa Doka so e calculado quando ha dados completos: fcj/Ec "
        "atual, carga final de projeto, carga do estado de construcao e "
        "aprovacao do calculista. Sem esses dados, gerar pendencia."
    ),
    severity="warning",
)


def _verify_decide_001(project: "RuleProject") -> list[Violation]:
    """Emite pendencia para cenarios de reescoramento sem dados completos."""
    multi_level = getattr(project, "multi_level", False)
    data = getattr(project, "reescoramento_data", None)

    # Bloco completo: nao emite violacao
    if data is not None and data.is_complete():
        return []

    if multi_level:
        # Multi-nivel sem dados completos -> pendencia explicita
        return [Violation(
            rule_id="DECIDE-001",
            severity="warning",
            message=(
                "Projeto multi-nivel sem dados completos de reescoramento "
                "(fcj_aos_dias_mpa, eci_mpa, carga_final_kn_m2 ou "
                "calculista_aprovacao). Fator alfa Doka NAO calculado - "
                "listar como pendencia para o calculista (manual §26 item 9)."
            ),
            actual_value="dados ausentes ou incompletos",
            limit_value="fcj/Ec/carga final + aprovacao",
        )]

    # Projeto unico-nivel ou sem flag multi-nivel: nota informativa de processo
    return [Violation(
        rule_id="DECIDE-001",
        severity="warning",
        message=_DECIDE_001.description_pt,
        actual_value="nota de processo",
        limit_value="dados completos quando aplicavel",
    )]


REGISTRY.register(_DECIDE_001, _verify_decide_001)


# ---------------------------------------------------------------------------
# DECIDE-002: 14 dias como piso normativo flexivel
# ---------------------------------------------------------------------------

_DECIDE_002 = Rule(
    id="DECIDE-002",
    category="DECIDE",
    source=Source(
        type="norm",
        ref="NBR 14931 + NBR 15696 / Manual §26 item 10",
        calibration=None,
    ),
    description_pt=(
        f"Ciclo de remocao/remanejamento de escoramento: minimo {DESFORMA_MIN_DIAS} "
        f"dias por padrao normativo. Reducao abaixo desse piso so com analise "
        f"do sistema, comprovacao de fcj/Ec e aprovacao do responsavel tecnico."
    ),
    severity="warning",
)


def _verify_decide_002(project: "RuleProject") -> list[Violation]:
    """Verifica desforma_dias do projeto contra o piso normativo de 14 dias."""
    desforma_dias = getattr(project, "desforma_dias", None)
    justificativa = getattr(project, "desforma_justificativa", "")

    if desforma_dias is None:
        # Sem informacao - apenas registra o piso como nota
        return [Violation(
            rule_id="DECIDE-002",
            severity="warning",
            message=(
                f"Prazo de desforma nao informado. Piso normativo: "
                f"{DESFORMA_MIN_DIAS} dias (NBR 14931). Reducao requer "
                f"analise tecnica (manual §26 item 10)."
            ),
            actual_value="nao informado",
            limit_value=f">= {DESFORMA_MIN_DIAS} dias (default)",
        )]

    if desforma_dias >= DESFORMA_MIN_DIAS:
        return []  # OK, dentro do piso

    # Abaixo do piso: precisa justificativa explicita
    if not justificativa:
        return [Violation(
            rule_id="DECIDE-002",
            severity="error",
            message=(
                f"Prazo de desforma {desforma_dias} dias abaixo do piso "
                f"normativo de {DESFORMA_MIN_DIAS} dias SEM justificativa "
                f"tecnica registrada. Manual §26 item 10 exige analise "
                f"de fcj/Ec e aprovacao do responsavel tecnico."
            ),
            actual_value=f"{desforma_dias} dias",
            limit_value=f">= {DESFORMA_MIN_DIAS} dias (ou justificativa)",
        )]
    return [Violation(
        rule_id="DECIDE-002",
        severity="warning",
        message=(
            f"Prazo de desforma {desforma_dias} dias abaixo do piso de "
            f"{DESFORMA_MIN_DIAS} dias COM justificativa: '{justificativa}'. "
            f"Verificar que aprovacao do responsavel tecnico esta anexada."
        ),
        actual_value=f"{desforma_dias} dias + justif.",
        limit_value=f">= {DESFORMA_MIN_DIAS} dias (default)",
    )]


REGISTRY.register(_DECIDE_002, _verify_decide_002)
