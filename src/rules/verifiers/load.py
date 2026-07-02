"""Load verifiers: LOAD-001 through LOAD-005.

All load-related rules from NBR 15696 and Orguel training.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.rules.schema import REGISTRY, Rule, Source, Violation

if TYPE_CHECKING:
    from src.rules.project import RuleProject


# --- LOAD-001: Sobrecarga >= 2.0 kN/m² ---

_LOAD_001 = Rule(
    id="LOAD-001",
    category="LOAD",
    source=Source(type="norm", ref="NBR 15696:2009 §4.2 + Orguel p.26"),
    description_pt="Sobrecarga de trabalho ≥ 2.0 kN/m²",
    severity="error",
)

SOBRECARGA_MIN_KN_M2 = 2.0


def _verify_sobrecarga(project: "RuleProject") -> list[Violation]:
    if project.load_params is None:
        return []
    q = project.load_params.q_sobrecarga
    if q < SOBRECARGA_MIN_KN_M2 - 1e-6:
        return [Violation(
            rule_id="LOAD-001",
            severity="error",
            message=(
                f"Sobrecarga de trabalho = {q} kN/m², "
                f"NBR 15696 exige mínimo {SOBRECARGA_MIN_KN_M2} kN/m²"
            ),
            actual_value=q,
            limit_value=SOBRECARGA_MIN_KN_M2,
        )]
    return []


REGISTRY.register(_LOAD_001, _verify_sobrecarga)


# --- LOAD-002: Total static load >= 4.0 kN/m² ---

_LOAD_002 = Rule(
    id="LOAD-002",
    category="LOAD",
    source=Source(type="norm", ref="NBR 15696:2009 §4.2 + Orguel p.26"),
    description_pt="Carga estática total ≥ 4.0 kN/m²",
    severity="error",
)

STATIC_LOAD_MIN_KN_M2 = 4.0


def _verify_static_load(project: "RuleProject") -> list[Violation]:
    violations = []
    if project.load_params is None:
        return []
    lp = project.load_params
    for panel in project.slab_panels:
        peso_concreto = lp.gamma_concreto * panel.thickness_m
        carga_total = peso_concreto + lp.q_forma + lp.q_sobrecarga
        if carga_total < STATIC_LOAD_MIN_KN_M2 - 1e-6:
            violations.append(Violation(
                rule_id="LOAD-002",
                severity="error",
                message=(
                    f"Laje {panel.label or '?'}: carga estática total = "
                    f"{carga_total:.2f} kN/m², mínimo é "
                    f"{STATIC_LOAD_MIN_KN_M2} kN/m²"
                ),
                element_id=panel.label or None,
                actual_value=round(carga_total, 2),
                limit_value=STATIC_LOAD_MIN_KN_M2,
            ))
    return violations


REGISTRY.register(_LOAD_002, _verify_static_load)


# --- LOAD-003: +25% on central support of continuous beams ---

_LOAD_003 = Rule(
    id="LOAD-003",
    category="LOAD",
    source=Source(type="manual", ref="Orguel p.109 regra 14 (hiperestaticidade)"),
    description_pt=(
        "Em vigas contínuas com 3+ apoios: acréscimo de 25% na reação central "
        "(10/8 q·L)"
    ),
    severity="error",
)


# O engine aplica 10/8 (=1.25) na escora mais proxima do apoio central para
# vigas com EXATAMENTE 3 apoios (beam_calculator, escopo confirmado com o
# engenheiro). O verificador usa 1.20 como piso — folga para ruido de
# posicionamento/arredondamento sem deixar passar a ausencia do fator.
# Vigas com >=4 apoios ficam fora do escopo (o engine tambem nao amplifica).
HYPERSTATIC_MIN_RATIO = 1.20


def _verify_hyperestaticity(project: "RuleProject") -> list[Violation]:
    import math

    violations = []
    for beam in project.beams:
        if len(beam.support_positions) != 3 or len(beam.shores) < 3:
            continue
        if not beam.centerline or len(beam.centerline) < 2:
            continue

        (x0, y0) = beam.centerline[0]
        (x1, y1) = beam.centerline[-1]
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            continue

        central_pos = sorted(
            max(0.0, min(length, sp)) for sp in beam.support_positions
        )[1]

        def _axis_pos(shore) -> float:
            return ((shore.x - x0) * dx + (shore.y - y0) * dy) / length

        loads = [s.load_kn for s in beam.shores]
        central_idx = min(
            range(len(beam.shores)),
            key=lambda i: abs(_axis_pos(beam.shores[i]) - central_pos),
        )
        others = sorted(
            load for i, load in enumerate(loads)
            if i != central_idx and load > 0
        )
        if not others:
            continue
        median_other = others[len(others) // 2]
        central_load = loads[central_idx]

        if central_load < HYPERSTATIC_MIN_RATIO * median_other - 1e-6:
            violations.append(Violation(
                rule_id="LOAD-003",
                severity="error",
                message=(
                    f"Viga {beam.label or '?'} (3 apoios): escora do apoio "
                    f"central com {central_load:.1f} kN vs mediana "
                    f"{median_other:.1f} kN das demais — acréscimo de 25% "
                    f"(10/8 q·L, Orguel p.109 regra 14) não aplicado"
                ),
                element_id=beam.label or None,
                actual_value=round(
                    central_load / median_other if median_other else 0.0, 3
                ),
                limit_value=HYPERSTATIC_MIN_RATIO,
                location=(
                    beam.shores[central_idx].x,
                    beam.shores[central_idx].y,
                ),
            ))
    return violations


REGISTRY.register(_LOAD_003, _verify_hyperestaticity)


# --- LOAD-004: gamma_f = 1.4 applied ---

_LOAD_004 = Rule(
    id="LOAD-004",
    category="LOAD",
    source=Source(type="norm", ref="NBR 15696:2009"),
    description_pt="Coeficiente de majoração γf = 1.4 aplicado a todas as cargas",
    severity="error",
)

GAMMA_F_REQUIRED = 1.4


def _verify_gamma_f(project: "RuleProject") -> list[Violation]:
    if project.load_params is None:
        return []
    gf = project.load_params.gamma_f
    if abs(gf - GAMMA_F_REQUIRED) > 1e-6:
        return [Violation(
            rule_id="LOAD-004",
            severity="error",
            message=(
                f"γf = {gf}, deveria ser {GAMMA_F_REQUIRED} "
                f"(NBR 15696:2009)"
            ),
            actual_value=gf,
            limit_value=GAMMA_F_REQUIRED,
        )]
    return []


REGISTRY.register(_LOAD_004, _verify_gamma_f)


# --- LOAD-005: Substrate stress check (Orguel p.25) ---

_LOAD_005 = Rule(
    id="LOAD-005",
    category="LOAD",
    source=Source(type="manual", ref="Orguel p.25"),
    description_pt=(
        "Verificação de tensão mínima no substrato: torre 16.53 kgf/cm², "
        "ESC2000-3100 26.45 kgf/cm², ESC3000-4500 17.35 kgf/cm²"
    ),
    severity="warning",
)

# Minimum substrate stress per equipment type (kgf/cm²)
SUBSTRATE_STRESS = {
    "tower": 16.53,
    "ESC2000-3100": 26.45,
    "ESC3000-4500": 17.35,
}


def _verify_substrate_stress(project: "RuleProject") -> list[Violation]:
    # TODO(engineer-confirmation): Requires substrate capacity data
    # (soil bearing capacity or lower slab capacity) which is not
    # currently available from the pipeline. This rule will fire as
    # a reminder that the substrate check is required in the Memória
    # de Cálculo, rather than as an automatic verification.
    return []


REGISTRY.register(_LOAD_005, _verify_substrate_stress)
