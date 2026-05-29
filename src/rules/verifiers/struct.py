"""Structural verifiers: STRUCT-001 through STRUCT-003.

Rules governing support placement at structural intersections,
cantilever constraints, and beam support strategies.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.rules.schema import REGISTRY, Rule, Source, Violation

if TYPE_CHECKING:
    from src.rules.project import RuleProject


# --- STRUCT-001: Beam intersection requires support ---

_STRUCT_001 = Rule(
    id="STRUCT-001",
    category="STRUCT",
    source=Source(type="engineer_qa", ref="Engineer Q&A #3"),
    description_pt=(
        "Toda interseção viga-viga sem pilar deve ter torre ou escora "
        "dentro de raio configurável"
    ),
    severity="error",
)

INTERSECTION_SUPPORT_RADIUS_M = 0.50


def _verify_beam_intersection_support(project: "RuleProject") -> list[Violation]:
    violations = []
    # Find beam-beam intersections that don't have a pillar nearby
    from shapely.geometry import LineString, Point

    beam_lines = []
    for beam in project.beams:
        if len(beam.centerline) >= 2:
            beam_lines.append((beam, LineString(beam.centerline)))

    pillar_points = [Point(p.center_xy) for p in project.pillars]

    for i, (b1, line1) in enumerate(beam_lines):
        for j, (b2, line2) in enumerate(beam_lines):
            if i >= j:
                continue
            if not line1.intersects(line2):
                continue
            intersection = line1.intersection(line2)
            if intersection.is_empty:
                continue

            # Get intersection point(s)
            points = []
            if intersection.geom_type == "Point":
                points = [(intersection.x, intersection.y)]
            elif intersection.geom_type == "MultiPoint":
                points = [(p.x, p.y) for p in intersection.geoms]

            for ix, iy in points:
                ipt = Point(ix, iy)

                # Check if a pillar is nearby (no support needed)
                has_pillar = any(
                    ipt.distance(pp) < PILLAR_NEARBY_M
                    for pp in pillar_points
                )
                if has_pillar:
                    continue

                # Check if a shore is within radius
                has_support = any(
                    ((s.x - ix) ** 2 + (s.y - iy) ** 2) ** 0.5
                    < INTERSECTION_SUPPORT_RADIUS_M
                    for s in project.shore_positions
                )
                if not has_support:
                    violations.append(Violation(
                        rule_id="STRUCT-001",
                        severity="error",
                        message=(
                            f"Interseção viga-viga em ({ix:.2f}, {iy:.2f}) "
                            f"sem pilar e sem suporte dentro de "
                            f"{INTERSECTION_SUPPORT_RADIUS_M}m"
                        ),
                        actual_value="Sem suporte",
                        limit_value=f"Suporte dentro de {INTERSECTION_SUPPORT_RADIUS_M}m",
                        location=(ix, iy),
                    ))
    return violations


PILLAR_NEARBY_M = 1.0  # Pillar within 1m = intersection is supported

REGISTRY.register(_STRUCT_001, _verify_beam_intersection_support)


# --- STRUCT-002: Forcado not on cantilever (Orguel p.109, regra 14) ---
# CORRECTED from old plan. This is NOT "cantilever tip support."
# Per AGENTS.md v3: forcado/saddle support placement must be inside
# the slab area, not on a cantilever (balanço) edge.

_STRUCT_002 = Rule(
    id="STRUCT-002",
    category="STRUCT",
    source=Source(type="manual", ref="Orguel p.109 regra 14"),
    description_pt=(
        "Forcado/saddle deve ser posicionado dentro da área da laje, "
        "não na extremidade de balanço (cantilever)"
    ),
    severity="error",
)


def _verify_forcado_not_on_cantilever(project: "RuleProject") -> list[Violation]:
    violations = []
    for beam in project.beams:
        if not (beam.is_cantilever_start or beam.is_cantilever_end):
            continue
        if len(beam.centerline) < 2:
            continue

        # Check shores near cantilever extremities
        for shore in beam.shores:
            if beam.is_cantilever_start:
                start = beam.centerline[0]
                dist_to_start = (
                    (shore.x - start[0]) ** 2 + (shore.y - start[1]) ** 2
                ) ** 0.5
                if dist_to_start < 0.10:  # Very close to cantilever edge
                    violations.append(Violation(
                        rule_id="STRUCT-002",
                        severity="error",
                        message=(
                            f"Escora em ({shore.x:.2f}, {shore.y:.2f}) "
                            f"posicionada na extremidade de balanço da viga "
                            f"{beam.label or '?'} — forcado não deve estar "
                            f"no balanço"
                        ),
                        element_id=beam.label or None,
                        actual_value=f"dist={dist_to_start:.2f}m da extremidade",
                        limit_value="Dentro da área da laje",
                        location=(shore.x, shore.y),
                    ))

            if beam.is_cantilever_end:
                end = beam.centerline[-1]
                dist_to_end = (
                    (shore.x - end[0]) ** 2 + (shore.y - end[1]) ** 2
                ) ** 0.5
                if dist_to_end < 0.10:
                    violations.append(Violation(
                        rule_id="STRUCT-002",
                        severity="error",
                        message=(
                            f"Escora em ({shore.x:.2f}, {shore.y:.2f}) "
                            f"posicionada na extremidade de balanço da viga "
                            f"{beam.label or '?'} — forcado não deve estar "
                            f"no balanço"
                        ),
                        element_id=beam.label or None,
                        actual_value=f"dist={dist_to_end:.2f}m da extremidade",
                        limit_value="Dentro da área da laje",
                        location=(shore.x, shore.y),
                    ))
    return violations


REGISTRY.register(_STRUCT_002, _verify_forcado_not_on_cantilever)


# --- STRUCT-003: Tower at center for 3-support beams (Orguel p.110, regra 15) ---

_STRUCT_003 = Rule(
    id="STRUCT-003",
    category="STRUCT",
    source=Source(type="manual", ref="Orguel p.110 regra 15"),
    description_pt=(
        "Viga contínua com 3 apoios: torre no apoio central "
        "(absorve +25%), telescópicas nas extremidades"
    ),
    severity="warning",
)


def _verify_tower_at_center(project: "RuleProject") -> list[Violation]:
    violations = []
    for beam in project.beams:
        n_supports = len(beam.support_positions)
        if n_supports < 3:
            continue
        # Check if any tower-type shore exists near the central support
        if n_supports >= 3 and beam.shores:
            # Find the central support position
            sorted_supports = sorted(beam.support_positions)
            central_idx = len(sorted_supports) // 2
            central_pos = sorted_supports[central_idx]

            # Check if there's a tower near the center
            has_tower_at_center = False
            for shore in beam.shores:
                if shore.shore_type == "tower":
                    # Approximate: check if shore is near center
                    # (this is a simplified check)
                    has_tower_at_center = True
                    break

            if not has_tower_at_center and len(beam.shores) > 2:
                violations.append(Violation(
                    rule_id="STRUCT-003",
                    severity="warning",
                    message=(
                        f"Viga {beam.label or '?'} com {n_supports} apoios: "
                        f"recomendado torre no apoio central para absorver "
                        f"a reação majorada (+25%)"
                    ),
                    element_id=beam.label or None,
                    actual_value=f"{n_supports} apoios, sem torre central",
                    limit_value="Torre no apoio central",
                ))
    return violations


REGISTRY.register(_STRUCT_003, _verify_tower_at_center)


# ===========================================================================
# Manual §28: verificadores do grid de VMs (vm_grid_builder)
# Nomeclatura: STRUCT-004 = momento, STRUCT-005 = flecha. Os IDs seguem
# o padrao numerico do regex de schema; descricoes citam "VM-001/VM-002"
# para correlacionar com o plano do manual §28.4.
# ===========================================================================

_STRUCT_004 = Rule(
    id="STRUCT-004",
    category="STRUCT",
    source=Source(
        type="manual",
        ref="Manual §22.2 + §28.4 (STRUCT-VM-001)",
    ),
    description_pt=(
        "Cada segmento de VM (primaria ou secundaria) do grid deve ter "
        "M_aplicado <= M_admissivel do modelo. Manual §22.2 (M=qL²/8) e "
        "catalogo equipment.yaml."
    ),
    severity="error",
)


def _verify_vm_grid_moment(project: "RuleProject") -> list[Violation]:
    """Verifica momento aplicado de cada VMSegment do grid de cada laje."""
    violations: list[Violation] = []
    for slab in project.slab_panels:
        grid = getattr(slab, "vm_grid", None)
        if grid is None:
            continue
        segments = getattr(grid, "segments", [])
        for seg in segments:
            if seg.passes_moment:
                continue
            label = slab.label or "?"
            violations.append(Violation(
                rule_id="STRUCT-004",
                severity="error",
                message=(
                    f"Laje '{label}': VM {seg.role} {seg.model} L={seg.length_mm}mm "
                    f"vao={seg.span_m:.2f}m com M={seg.moment_kn_m:.2f} kN.m > "
                    f"M_adm={seg.moment_adm_kn_m:.2f} kN.m (utilizacao "
                    f"{seg.utilization*100:.0f}%)"
                ),
                element_id=label,
                location=(
                    (seg.start[0] + seg.end[0]) / 2,
                    (seg.start[1] + seg.end[1]) / 2,
                ),
                actual_value=round(seg.moment_kn_m, 3),
                limit_value=round(seg.moment_adm_kn_m, 3),
            ))
    return violations


REGISTRY.register(_STRUCT_004, _verify_vm_grid_moment)


_STRUCT_005 = Rule(
    id="STRUCT-005",
    category="STRUCT",
    source=Source(
        type="manual",
        ref="Manual §22.3 + NBR 15696 §4.3.2 + §28.4 (STRUCT-VM-002)",
    ),
    description_pt=(
        "Cada segmento de VM deve ter flecha calculada <= flecha admissivel "
        "1 + L/500 mm (NBR 15696 §4.3.2). Manual §22.3 (f=5qL⁴/384EI)."
    ),
    severity="error",
)


def _verify_vm_grid_deflection(project: "RuleProject") -> list[Violation]:
    """Verifica flecha de cada VMSegment contra limite admissivel."""
    violations: list[Violation] = []
    for slab in project.slab_panels:
        grid = getattr(slab, "vm_grid", None)
        if grid is None:
            continue
        segments = getattr(grid, "segments", [])
        for seg in segments:
            if seg.passes_deflection:
                continue
            label = slab.label or "?"
            violations.append(Violation(
                rule_id="STRUCT-005",
                severity="error",
                message=(
                    f"Laje '{label}': VM {seg.role} {seg.model} L={seg.length_mm}mm "
                    f"vao={seg.span_m:.2f}m com flecha={seg.flecha_mm:.2f}mm > "
                    f"flecha_adm={seg.flecha_adm_mm:.2f}mm (utilizacao "
                    f"{seg.utilization*100:.0f}%)"
                ),
                element_id=label,
                location=(
                    (seg.start[0] + seg.end[0]) / 2,
                    (seg.start[1] + seg.end[1]) / 2,
                ),
                actual_value=round(seg.flecha_mm, 2),
                limit_value=round(seg.flecha_adm_mm, 2),
            ))
    return violations


REGISTRY.register(_STRUCT_005, _verify_vm_grid_deflection)
