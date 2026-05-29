"""Operational rules verifier — OP-001 to OP-017 (manual §17).

Each OP-XXX corresponds to a row in the operational rules table of the
manual. Most are advisory notes (severity="warning") that must appear in
the project report; a subset (e.g. OP-012, OP-014, OP-015, OP-016) maps
to geometric/structural envelope checks that ARE verifiable from the
pipeline output.

This module registers all 17 OP rules and provides verifier functions
that return Violations when:
- A note must be emitted to the report (always-fire informational rules).
- A geometric envelope is violated (verifiable rules).

The "always-fire" rules emit one Violation per project so the report
includes the operational note. The "verifiable" rules emit Violations
only when actual data shows the rule is broken.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.rules.schema import REGISTRY, Rule, Source, Violation

if TYPE_CHECKING:
    from src.rules.project import RuleProject


# ---------------------------------------------------------------------------
# Helper para criar OP rules com source comum
# ---------------------------------------------------------------------------

def _op_source(page: int | str = "p.97-115") -> Source:
    return Source(
        type="manual",
        ref=f"Manual §17 / Orguel {page}",
        calibration=None,
    )


def _info_violation(rule_id: str, message: str) -> Violation:
    """Cria uma 'violation' informativa (severity=warning) para anotacao."""
    return Violation(
        rule_id=rule_id,
        severity="warning",
        message=message,
        actual_value="nota operacional",
        limit_value="aparecer no relatorio",
    )


# ---------------------------------------------------------------------------
# OP-001 a OP-009: Regras operacionais informativas (sempre disparam)
# ---------------------------------------------------------------------------

_OP_INFO_RULES = [
    (
        "OP-001",
        "p.97",
        "Apoiar em base firme; preparo da base e responsabilidade do cliente",
    ),
    (
        "OP-002",
        "p.98",
        "Escoras e torres devem estar aprumadas",
    ),
    (
        "OP-003",
        "p.99",
        "Topo e base devem ser ajustados sem folgas",
    ),
    (
        "OP-004",
        "p.100",
        "Guias devem ser apoiadas e cunhadas corretamente",
    ),
    (
        "OP-005",
        "p.101",
        "Madeiramento do fundo da forma deve seguir projeto",
    ),
    (
        "OP-006",
        "p.102",
        "Tempo de cura e responsabilidade do cliente/calculista",
    ),
    (
        "OP-007",
        "p.103",
        "Equipamentos devem ser inspecionados antes do uso",
    ),
    (
        "OP-008",
        "p.104",
        "Nao alterar projeto sem comunicacao tecnica",
    ),
    (
        "OP-009",
        "p.104",
        "Travamento e amarracao das formas sao responsabilidade do cliente",
    ),
]


def _make_info_verifier(rule_id: str, message: str):
    def _verifier(project: "RuleProject") -> list[Violation]:
        return [_info_violation(rule_id, message)]
    _verifier.__name__ = f"_verify_{rule_id.replace('-', '_').lower()}"
    return _verifier


for _rid, _page, _msg in _OP_INFO_RULES:
    _rule = Rule(
        id=_rid,
        category="OP",
        source=_op_source(_page),
        description_pt=_msg,
        severity="warning",
    )
    REGISTRY.register(_rule, _make_info_verifier(_rid, _msg))


# ---------------------------------------------------------------------------
# OP-010: Forcados nao podem ser locados em balanco
# ---------------------------------------------------------------------------

_OP_010 = Rule(
    id="OP-010",
    category="OP",
    source=_op_source("p.109"),
    description_pt=(
        "Forcados nao podem ser locados em balanco; suporte do forcado em "
        "viga deve estar sempre apoiado"
    ),
    severity="warning",
)


def _verify_op_010(project: "RuleProject") -> list[Violation]:
    violations: list[Violation] = []
    for beam in project.beams:
        for shore in beam.shores:
            # Heuristica: shore em posicao alem do ultimo apoio (cantilever)
            # e sem flag is_cantilever explicito - alerta para revisao manual.
            sp = beam.support_positions or []
            if not sp:
                continue
            shore_x = getattr(shore, "x", 0.0)
            # Distancia ao apoio mais proximo
            min_d = min(abs(shore_x - p) for p in sp) if sp else 0.0
            # Se shore esta antes do primeiro apoio (balanco no inicio) e nao
            # ha is_cantilever_start, ou apos o ultimo apoio sem
            # is_cantilever_end -> alerta.
            before_first = shore_x < min(sp) - 0.05
            after_last = shore_x > max(sp) + 0.05
            if (before_first and not beam.is_cantilever_start) or (
                after_last and not beam.is_cantilever_end
            ):
                violations.append(Violation(
                    rule_id="OP-010",
                    severity="warning",
                    message=(
                        f"Viga '{beam.label or '?'}': escora em x={shore_x:.2f}m "
                        f"esta em provavel balanco sem flag is_cantilever — "
                        f"verificar suporte do forcado"
                    ),
                    actual_value=round(shore_x, 2),
                    limit_value="apoiado sobre estrutura",
                ))
                break  # 1 alerta por viga e suficiente
    return violations or [_info_violation(
        "OP-010",
        _OP_010.description_pt,
    )]


REGISTRY.register(_OP_010, _verify_op_010)


# ---------------------------------------------------------------------------
# OP-011: Viga continua 3 apoios — apoio central +25% (10/8 qL)
# ---------------------------------------------------------------------------

_OP_011 = Rule(
    id="OP-011",
    category="OP",
    source=_op_source("p.109"),
    description_pt=(
        "Vigas continuas com 3 apoios sobrecarregam apoio central em 25% "
        "(10/8 qL); extremos = 3/8 qL"
    ),
    severity="warning",
)


def _verify_op_011(project: "RuleProject") -> list[Violation]:
    violations: list[Violation] = []
    for beam in project.beams:
        # Vigas com 3 apoios precisam ter a regra aplicada no calculo.
        # Beam_calculator ja faz o ajuste; esta nota confirma o requisito.
        if beam.support_positions and len(beam.support_positions) == 3:
            violations.append(_info_violation(
                "OP-011",
                f"Viga '{beam.label or '?'}' com 3 apoios: apoio central "
                f"deve receber +25% de carga (10/8 qL aplicado)",
            ))
    if not violations:
        violations.append(_info_violation("OP-011", _OP_011.description_pt))
    return violations


REGISTRY.register(_OP_011, _verify_op_011)


# ---------------------------------------------------------------------------
# OP-012: Vigas externas <=30 cm, <=60 cm, <=3 m podem usar escora+cruzeta
# ---------------------------------------------------------------------------

_OP_012 = Rule(
    id="OP-012",
    category="OP",
    source=_op_source("p.111"),
    description_pt=(
        "Vigas externas: largura <=30 cm, altura <=60 cm, comprimento "
        "<=3 m podem usar escora+cruzeta; acima disso, torres"
    ),
    severity="warning",
)

OP012_MAX_WIDTH_M = 0.30
OP012_MAX_HEIGHT_M = 0.60
OP012_MAX_LENGTH_M = 3.00


def _verify_op_012(project: "RuleProject") -> list[Violation]:
    violations: list[Violation] = []
    for beam in project.beams:
        if not beam.is_perimeter:
            continue
        # Verifica se ultrapassou envelope e ainda esta usando escora simples
        # (decision_rule != rule-16c-viga-grande).
        excede_envelope = (
            beam.width_m > OP012_MAX_WIDTH_M
            or beam.height_m > OP012_MAX_HEIGHT_M
            or beam.length_m > OP012_MAX_LENGTH_M
        )
        if not excede_envelope:
            continue
        # Verifica se o calculo escalou para torre/estaiamento
        rule = beam.decision_rule or ""
        if rule.startswith("rule-1") or "viga-grande" in rule:
            continue
        violations.append(Violation(
            rule_id="OP-012",
            severity="error",
            message=(
                f"Viga externa '{beam.label or '?'}' "
                f"(b={beam.width_m*100:.0f}cm, h={beam.height_m*100:.0f}cm, "
                f"L={beam.length_m:.2f}m) ultrapassa envelope "
                f"30x60x300cm mas nao foi escalada para torre/estaiamento"
            ),
            actual_value={
                "width_cm": beam.width_m * 100,
                "height_cm": beam.height_m * 100,
                "length_m": beam.length_m,
                "decision_rule": rule,
            },
            limit_value=f"<=30x60cm e <=3.00m (ou torre/estaiamento)",
        ))
    return violations


REGISTRY.register(_OP_012, _verify_op_012)


# ---------------------------------------------------------------------------
# OP-013: Vigas externas com console (altura >=70 cm)
# ---------------------------------------------------------------------------

_OP_013 = Rule(
    id="OP-013",
    category="OP",
    source=_op_source("p.111"),
    description_pt=(
        "Vigas externas com console: altura >=70 cm exige console (mao francesa)"
    ),
    severity="warning",
)

OP013_CONSOLE_REQUIRED_HEIGHT_M = 0.70


def _verify_op_013(project: "RuleProject") -> list[Violation]:
    violations: list[Violation] = []
    for beam in project.beams:
        if not beam.is_perimeter:
            continue
        if beam.height_m >= OP013_CONSOLE_REQUIRED_HEIGHT_M:
            violations.append(_info_violation(
                "OP-013",
                f"Viga externa '{beam.label or '?'}' h={beam.height_m*100:.0f}cm "
                f">=70cm: console (mao francesa) requerido",
            ))
    return violations


REGISTRY.register(_OP_013, _verify_op_013)


# ---------------------------------------------------------------------------
# OP-014: Vigas internas <=6m, ate 40x70 cm -> escoras com cruzetas
# ---------------------------------------------------------------------------

_OP_014 = Rule(
    id="OP-014",
    category="OP",
    source=_op_source("p.112"),
    description_pt=(
        "Vigas internas <=6 m, ate 40 x 70 cm: escoras com cruzetas"
    ),
    severity="warning",
)


def _verify_op_014(project: "RuleProject") -> list[Violation]:
    # Esta regra confirma que vigas dentro do envelope NAO precisam de
    # torre. Se decision_rule mostrar torre para esse caso, alerta.
    violations: list[Violation] = []
    for beam in project.beams:
        if beam.is_perimeter:
            continue
        if (
            beam.length_m <= 6.0
            and beam.width_m <= 0.40
            and beam.height_m <= 0.70
        ):
            rule = beam.decision_rule or ""
            if rule.startswith("rule-1") and "rule-1b" not in rule:
                # 'rule-1-altura' (altura excessiva) - aceitavel.
                # Outras 'rule-1*' nao deveriam disparar; reportar.
                violations.append(Violation(
                    rule_id="OP-014",
                    severity="warning",
                    message=(
                        f"Viga interna '{beam.label or '?'}' "
                        f"(L={beam.length_m:.2f}m, b={beam.width_m*100:.0f}cm, "
                        f"h={beam.height_m*100:.0f}cm) dentro do envelope "
                        f"(<=6m e <=40x70cm) recebeu torre por '{rule}'; "
                        f"verificar se escora+cruzeta nao seria suficiente"
                    ),
                    actual_value=rule,
                    limit_value="escora+cruzeta",
                ))
    return violations or [_info_violation("OP-014", _OP_014.description_pt)]


REGISTRY.register(_OP_014, _verify_op_014)


# ---------------------------------------------------------------------------
# OP-015: Vigas internas 6-10 m, ate 40x70 cm -> escoras + torre central
# ---------------------------------------------------------------------------

_OP_015 = Rule(
    id="OP-015",
    category="OP",
    source=_op_source("p.112"),
    description_pt=(
        "Vigas internas 6-10 m, ate 40 x 70 cm: escoras + torre central"
    ),
    severity="warning",
)


def _verify_op_015(project: "RuleProject") -> list[Violation]:
    violations: list[Violation] = []
    for beam in project.beams:
        if beam.is_perimeter:
            continue
        if (
            6.0 < beam.length_m <= 10.0
            and beam.width_m <= 0.40
            and beam.height_m <= 0.70
        ):
            # Conta torres e escoras na viga
            n_tower = sum(
                1 for s in beam.shores
                if getattr(s, "shore_type", "") == "tower"
                or "tower" in getattr(s, "shore_type", "")
            )
            n_total = len(beam.shores)
            if n_total > 0 and n_tower == 0:
                violations.append(Violation(
                    rule_id="OP-015",
                    severity="warning",
                    message=(
                        f"Viga interna '{beam.label or '?'}' (L={beam.length_m:.2f}m, "
                        f"6-10m): manual recomenda 1 torre central + escoras "
                        f"nas extremidades; encontradas 0 torres em {n_total} apoios"
                    ),
                    actual_value=f"{n_tower}/{n_total} torres",
                    limit_value=">=1 torre central",
                ))
    return violations or [_info_violation("OP-015", _OP_015.description_pt)]


REGISTRY.register(_OP_015, _verify_op_015)


# ---------------------------------------------------------------------------
# OP-016: Vigas internas >10 m -> torres + escoras (pode mesclar)
# ---------------------------------------------------------------------------

_OP_016 = Rule(
    id="OP-016",
    category="OP",
    source=_op_source("p.113"),
    description_pt=(
        "Vigas internas >10 m: torres + escoras (pode mesclar)"
    ),
    severity="error",
)


def _verify_op_016(project: "RuleProject") -> list[Violation]:
    violations: list[Violation] = []
    for beam in project.beams:
        if beam.is_perimeter:
            continue
        if beam.length_m > 10.0:
            n_tower = sum(
                1 for s in beam.shores
                if "tower" in getattr(s, "shore_type", "")
            )
            if n_tower == 0:
                violations.append(Violation(
                    rule_id="OP-016",
                    severity="error",
                    message=(
                        f"Viga interna '{beam.label or '?'}' L={beam.length_m:.2f}m "
                        f">10m: manual exige torres; encontradas 0 torres"
                    ),
                    actual_value=f"0 torres em L={beam.length_m:.2f}m",
                    limit_value=">=1 torre",
                ))
    return violations or [_info_violation("OP-016", _OP_016.description_pt)]


REGISTRY.register(_OP_016, _verify_op_016)


# ---------------------------------------------------------------------------
# OP-017: Vigas externas perifericas precisam ser estaiadas
# ---------------------------------------------------------------------------

_OP_017 = Rule(
    id="OP-017",
    category="OP",
    source=_op_source("p.111"),
    description_pt=(
        "Vigas externas perifericas precisam ser estaiadas para evitar tombamento"
    ),
    severity="warning",
)


def _verify_op_017(project: "RuleProject") -> list[Violation]:
    violations: list[Violation] = []
    perimeter_count = sum(1 for b in project.beams if b.is_perimeter)
    if perimeter_count > 0:
        violations.append(_info_violation(
            "OP-017",
            f"{perimeter_count} viga(s) externa(s) detectada(s): garantir "
            f"estaiamento durante montagem para evitar tombamento",
        ))
    return violations


REGISTRY.register(_OP_017, _verify_op_017)
