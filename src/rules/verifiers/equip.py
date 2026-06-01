"""Equipment verifiers: EQUIP-001 through EQUIP-005.

Rules governing equipment selection per height, capacity, and beam type.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.rules.schema import REGISTRY, Rule, Source, Violation

if TYPE_CHECKING:
    from src.rules.project import RuleProject


# --- EQUIP-001: Height > 4.50m -> no telescópicas ---

_EQUIP_001 = Rule(
    id="EQUIP-001",
    category="EQUIP",
    source=Source(type="manual", ref="Decision chain Q1 + Orguel p.12"),
    description_pt="Altura > 4.50 m: nenhuma escora telescópica (limite físico ESC450)",
    severity="error",
)

MAX_TELESCOPIC_HEIGHT_M = 4.50


def _verify_no_telescopics_above_limit(project: "RuleProject") -> list[Violation]:
    violations = []
    if project.pe_direito_m <= MAX_TELESCOPIC_HEIGHT_M:
        return []
    for shore in project.shore_positions:
        if shore.shore_type == "telescopic":
            violations.append(Violation(
                rule_id="EQUIP-001",
                severity="error",
                message=(
                    f"Escora telescópica em ({shore.x:.2f}, {shore.y:.2f}) "
                    f"com pé-direito {project.pe_direito_m:.2f}m > "
                    f"{MAX_TELESCOPIC_HEIGHT_M}m — usar torre"
                ),
                actual_value=project.pe_direito_m,
                limit_value=MAX_TELESCOPIC_HEIGHT_M,
                location=(shore.x, shore.y),
            ))
    return violations


REGISTRY.register(_EQUIP_001, _verify_no_telescopics_above_limit)


# --- EQUIP-002: Telescópica capacity check (Orguel p.11 curves) ---

_EQUIP_002 = Rule(
    id="EQUIP-002",
    category="EQUIP",
    source=Source(type="manual", ref="Orguel p.11"),
    description_pt=(
        "Carga aplicada não deve exceder capacidade derateada da "
        "telescópica na abertura real (curvas p.11)"
    ),
    severity="error",
)


def _verify_telescopica_capacity(project: "RuleProject") -> list[Violation]:
    violations = []
    for shore in project.shore_positions:
        if shore.shore_type != "telescopic":
            continue
        if shore.utilization > 1.0 + 1e-6:
            violations.append(Violation(
                rule_id="EQUIP-002",
                severity="error",
                message=(
                    f"Escora telescópica {shore.model or '?'} em "
                    f"({shore.x:.2f}, {shore.y:.2f}) com utilização "
                    f"{shore.utilization:.0%} > 100%"
                ),
                actual_value=round(shore.utilization, 3),
                limit_value=1.0,
                location=(shore.x, shore.y),
            ))
    return violations


REGISTRY.register(_EQUIP_002, _verify_telescopica_capacity)


# --- EQUIP-003: Tower utilization 55-85% ---

_EQUIP_003 = Rule(
    id="EQUIP-003",
    category="EQUIP",
    source=Source(
        type="engineer_qa", ref="Engineer Q&A #10",
        calibration="Orguel 2026-04-07 (n=12)",
    ),
    description_pt="Utilização de torres entre 55% e 85% da capacidade",
    severity="warning",
)

TOWER_UTIL_MIN = 0.55
TOWER_UTIL_MAX = 0.85


def _verify_tower_utilization(project: "RuleProject") -> list[Violation]:
    violations = []
    for shore in project.shore_positions:
        if shore.shore_type != "tower":
            continue
        if shore.utilization < TOWER_UTIL_MIN - 1e-6:
            violations.append(Violation(
                rule_id="EQUIP-003",
                severity="warning",
                message=(
                    f"Torre em ({shore.x:.2f}, {shore.y:.2f}) com utilização "
                    f"{shore.utilization:.0%} < {TOWER_UTIL_MIN:.0%} "
                    f"(subdimensionada)"
                ),
                actual_value=round(shore.utilization, 3),
                limit_value=f"[{TOWER_UTIL_MIN}, {TOWER_UTIL_MAX}]",
                location=(shore.x, shore.y),
            ))
        elif shore.utilization > TOWER_UTIL_MAX + 1e-6:
            violations.append(Violation(
                rule_id="EQUIP-003",
                severity="warning",
                message=(
                    f"Torre em ({shore.x:.2f}, {shore.y:.2f}) com utilização "
                    f"{shore.utilization:.0%} > {TOWER_UTIL_MAX:.0%} "
                    f"(margem insuficiente)"
                ),
                actual_value=round(shore.utilization, 3),
                limit_value=f"[{TOWER_UTIL_MIN}, {TOWER_UTIL_MAX}]",
                location=(shore.x, shore.y),
            ))
    return violations


REGISTRY.register(_EQUIP_003, _verify_tower_utilization)


# --- EQUIP-004: External beam constraints (Orguel p.111, regra 16 parte A) ---

_EQUIP_004 = Rule(
    id="EQUIP-004",
    category="EQUIP",
    source=Source(type="manual", ref="Orguel p.111 regra 16 parte A"),
    description_pt=(
        "Viga externa com escoras telescópicas + cruzetas: "
        "largura ≤ 30cm, altura ≤ 60cm, comprimento ≤ 3.00m. "
        "Além desses limites: torres ou estaiamento"
    ),
    severity="error",
)

EXT_BEAM_MAX_WIDTH_M = 0.30
EXT_BEAM_MAX_HEIGHT_M = 0.60
EXT_BEAM_MAX_LENGTH_M = 3.00


def _verify_external_beam_constraints(project: "RuleProject") -> list[Violation]:
    violations = []
    for beam in project.beams:
        if not beam.is_perimeter:
            continue
        # Check if beam exceeds limits for telescopic-only
        has_only_telescopics = all(
            s.shore_type == "telescopic" for s in beam.shores
        )
        if not has_only_telescopics:
            continue  # Already has towers, OK

        if (beam.width_m > EXT_BEAM_MAX_WIDTH_M or
                beam.height_m > EXT_BEAM_MAX_HEIGHT_M or
                beam.length_m > EXT_BEAM_MAX_LENGTH_M):
            violations.append(Violation(
                rule_id="EQUIP-004",
                severity="error",
                message=(
                    f"Viga externa {beam.label or '?'} "
                    f"({beam.width_m*100:.0f}×{beam.height_m*100:.0f}cm, "
                    f"L={beam.length_m:.1f}m) excede limites para escoras "
                    f"telescópicas apenas — requer torres ou estaiamento"
                ),
                element_id=beam.label or None,
                actual_value=(
                    f"b={beam.width_m:.2f}, h={beam.height_m:.2f}, "
                    f"L={beam.length_m:.1f}"
                ),
                limit_value=(
                    f"b≤{EXT_BEAM_MAX_WIDTH_M}, h≤{EXT_BEAM_MAX_HEIGHT_M}, "
                    f"L≤{EXT_BEAM_MAX_LENGTH_M}"
                ),
            ))
    return violations


REGISTRY.register(_EQUIP_004, _verify_external_beam_constraints)


# --- EQUIP-005: Internal beam constraints (Orguel p.112-113, regra 16 parte B) ---

_EQUIP_005 = Rule(
    id="EQUIP-005",
    category="EQUIP",
    source=Source(type="manual", ref="Orguel p.112-113 regra 16 parte B"),
    description_pt=(
        "Viga interna: L>10m ou b>40cm ou h>70cm → 100% torres; "
        "6-10m → misto (escoras + torre central); "
        "L≤6m, b≤40cm, h≤70cm → escoras + cruzetas"
    ),
    severity="error",
)

INT_BEAM_TOWER_ONLY_LENGTH_M = 10.0
INT_BEAM_TOWER_ONLY_WIDTH_M = 0.40
INT_BEAM_TOWER_ONLY_HEIGHT_M = 0.70
INT_BEAM_MIXED_MIN_LENGTH_M = 6.0


def _verify_internal_beam_constraints(project: "RuleProject") -> list[Violation]:
    violations = []
    for beam in project.beams:
        if beam.is_perimeter:
            continue  # EQUIP-004 handles external beams

        has_only_telescopics = all(
            s.shore_type == "telescopic" for s in beam.shores
        )

        # Check tower-only condition
        needs_towers = (
            beam.length_m > INT_BEAM_TOWER_ONLY_LENGTH_M or
            beam.width_m > INT_BEAM_TOWER_ONLY_WIDTH_M or
            beam.height_m > INT_BEAM_TOWER_ONLY_HEIGHT_M
        )
        if needs_towers and has_only_telescopics and beam.shores:
            violations.append(Violation(
                rule_id="EQUIP-005",
                severity="error",
                message=(
                    f"Viga interna {beam.label or '?'} "
                    f"({beam.width_m*100:.0f}×{beam.height_m*100:.0f}cm, "
                    f"L={beam.length_m:.1f}m) requer 100% torres "
                    f"mas tem apenas escoras telescópicas"
                ),
                element_id=beam.label or None,
                actual_value="100% telescópicas",
                limit_value="100% torres",
            ))
            continue

        # Check mixed condition (6-10m)
        needs_mixed = (
            INT_BEAM_MIXED_MIN_LENGTH_M < beam.length_m <= INT_BEAM_TOWER_ONLY_LENGTH_M
            and beam.width_m <= INT_BEAM_TOWER_ONLY_WIDTH_M
            and beam.height_m <= INT_BEAM_TOWER_ONLY_HEIGHT_M
        )
        if needs_mixed and has_only_telescopics and beam.shores:
            violations.append(Violation(
                rule_id="EQUIP-005",
                severity="error",
                message=(
                    f"Viga interna {beam.label or '?'} "
                    f"(L={beam.length_m:.1f}m, entre 6-10m) requer modo "
                    f"misto (escoras + torre central) mas tem apenas "
                    f"escoras telescópicas"
                ),
                element_id=beam.label or None,
                actual_value="100% telescópicas",
                limit_value="Misto (escoras + torre central)",
            ))
    return violations


REGISTRY.register(_EQUIP_005, _verify_internal_beam_constraints)
