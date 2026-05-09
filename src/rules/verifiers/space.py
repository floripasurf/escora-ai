"""Spacing verifiers: SPACE-001 through SPACE-003.

Spacing rules for shores under slabs and beams.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.rules.schema import REGISTRY, Rule, Source, Violation
from src.utils.constants import ESPACAMENTO_POR_ALTURA

if TYPE_CHECKING:
    from src.rules.project import RuleProject


# --- SPACE-001: Slab thickness -> max spacing table ---

_SPACE_001 = Rule(
    id="SPACE-001",
    category="SPACE",
    source=Source(type="norm", ref="AGENTS.md spacing table + Orguel p.89"),
    description_pt=(
        "Espaçamento máximo de escoras em laje conforme tabela por espessura"
    ),
    severity="error",
)


def _get_max_spacing(thickness_m: float) -> float:
    """Get max spacing from ESPACAMENTO_POR_ALTURA table."""
    thickness_cm = round(thickness_m * 100)
    for (min_cm, max_cm), spacing in ESPACAMENTO_POR_ALTURA.items():
        if min_cm <= thickness_cm <= max_cm:
            return spacing
    return 1.10  # fallback for thicknesses outside all ranges


def _verify_slab_spacing(project: "RuleProject") -> list[Violation]:
    violations = []
    for panel in project.slab_panels:
        max_spacing = _get_max_spacing(panel.thickness_m)
        shores = panel.shores
        if len(shores) < 2:
            continue
        # Check nearest-neighbor distance for each shore.
        # If a shore's nearest neighbor is beyond max_spacing, it's a gap.
        for i, s1 in enumerate(shores):
            min_dist = float("inf")
            for j, s2 in enumerate(shores):
                if i == j:
                    continue
                dist = ((s1.x - s2.x) ** 2 + (s1.y - s2.y) ** 2) ** 0.5
                min_dist = min(min_dist, dist)
            if min_dist > max_spacing + 0.05:  # 5cm tolerance
                violations.append(Violation(
                    rule_id="SPACE-001",
                    severity="error",
                    message=(
                        f"Espaçamento {min_dist:.2f}m entre escoras na laje "
                        f"{panel.label or '?'} (espessura {panel.thickness_m*100:.0f}cm), "
                        f"máximo é {max_spacing}m"
                    ),
                    element_id=panel.label or None,
                    actual_value=round(min_dist, 2),
                    limit_value=max_spacing,
                    location=(s1.x, s1.y),
                ))
    return violations


REGISTRY.register(_SPACE_001, _verify_slab_spacing)


# --- SPACE-002: Cruzeta spacing 0.80m under beams ---

_SPACE_002 = Rule(
    id="SPACE-002",
    category="SPACE",
    source=Source(type="engineer_qa", ref="Engineer Q&A #5"),
    description_pt="Cruzetas sob vigas a cada 0.80 m",
    severity="error",
)

CRUZETA_SPACING_M = 0.80


def _verify_cruzeta_spacing(project: "RuleProject") -> list[Violation]:
    violations = []
    for beam in project.beams:
        shores = sorted(beam.shores, key=lambda s: (s.x, s.y))
        for i in range(len(shores) - 1):
            s1, s2 = shores[i], shores[i + 1]
            dist = ((s1.x - s2.x) ** 2 + (s1.y - s2.y) ** 2) ** 0.5
            if dist > CRUZETA_SPACING_M + 0.05:  # 5cm tolerance
                violations.append(Violation(
                    rule_id="SPACE-002",
                    severity="error",
                    message=(
                        f"Espaçamento {dist:.2f}m entre escoras sob viga "
                        f"{beam.label or '?'}, cruzetas devem estar a cada "
                        f"{CRUZETA_SPACING_M}m"
                    ),
                    element_id=beam.label or None,
                    actual_value=round(dist, 2),
                    limit_value=CRUZETA_SPACING_M,
                    location=(s1.x, s1.y),
                ))
    return violations


REGISTRY.register(_SPACE_002, _verify_cruzeta_spacing)


# --- SPACE-003: Plywood seam alignment (Orguel p.114-115, regra 17) ---

_SPACE_003 = Rule(
    id="SPACE-003",
    category="SPACE",
    source=Source(type="manual", ref="Orguel p.114-115 regra 17"),
    description_pt=(
        "Espaçamento dos barrotes deve ser múltiplo do comprimento da chapa "
        "de compensado (220 mm ou 244 mm). Emenda deve cair no eixo do barrote."
    ),
    severity="warning",
)

PLYWOOD_MULTIPLES_MM = [220, 244]


def _verify_plywood_seam_alignment(project: "RuleProject") -> list[Violation]:
    # TODO: Requires barrote spacing data which is not yet directly
    # available in RuleProject. The spacing decision is currently made
    # inside grid_distributor and not exposed as discrete barrote positions.
    # Will be implemented when barrote layout data is added to the adapter.
    return []


REGISTRY.register(_SPACE_003, _verify_plywood_seam_alignment)
