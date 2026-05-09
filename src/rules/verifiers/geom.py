"""Geometric verifiers: GEOM-001 through GEOM-007.

All geometric rules that govern shore/barrote placement relative
to structural elements (pillars, slab edges, walls).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from shapely.geometry import Point, Polygon as ShapelyPolygon

from src.rules.schema import REGISTRY, Rule, Source, Violation

if TYPE_CHECKING:
    from src.rules.project import RuleProject


# --- GEOM-001: Column setback >= 0.70m ---

_GEOM_001 = Rule(
    id="GEOM-001",
    category="GEOM",
    source=Source(type="norm", ref="NBR 6118:2023 §19.5"),
    description_pt="Distância mínima de 0.70 m da face de qualquer pilar (zona de punção)",
    severity="error",
)

PILLAR_MIN_DISTANCE_M = 0.70


def _verify_column_setback(project: "RuleProject") -> list[Violation]:
    violations = []
    for shore in project.shore_positions:
        pt = Point(shore.x, shore.y)
        for pillar in project.pillars:
            px, py = pillar.center_xy
            hw = pillar.width_m / 2
            hd = pillar.depth_m / 2
            pillar_poly = ShapelyPolygon([
                (px - hw, py - hd), (px + hw, py - hd),
                (px + hw, py + hd), (px - hw, py + hd),
            ])
            dist = pt.distance(pillar_poly)
            if dist < PILLAR_MIN_DISTANCE_M - 1e-6:
                violations.append(Violation(
                    rule_id="GEOM-001",
                    severity="error",
                    message=(
                        f"Escora a {dist:.2f}m do pilar {pillar.name or '?'}, "
                        f"mínimo é {PILLAR_MIN_DISTANCE_M}m (zona de punção)"
                    ),
                    element_id=pillar.name or None,
                    actual_value=round(dist, 3),
                    limit_value=PILLAR_MIN_DISTANCE_M,
                    location=(shore.x, shore.y),
                ))
    return violations


REGISTRY.register(_GEOM_001, _verify_column_setback)


# --- GEOM-002: Slab edge setback >= 0.15m ---

_GEOM_002 = Rule(
    id="GEOM-002",
    category="GEOM",
    source=Source(
        type="engineer_qa", ref="Orguel practice",
        calibration="Orguel 2026-04-07 (n=12)",
    ),
    description_pt="Distância mínima de 0.15 m da borda da laje",
    severity="error",
)

SLAB_EDGE_MIN_DISTANCE_M = 0.15


def _verify_slab_edge_setback(project: "RuleProject") -> list[Violation]:
    violations = []
    for panel in project.slab_panels:
        poly = panel.polygon
        if not hasattr(poly, 'boundary'):
            continue
        boundary = poly.boundary
        for shore in panel.shores:
            pt = Point(shore.x, shore.y)
            dist = boundary.distance(pt)
            if dist < SLAB_EDGE_MIN_DISTANCE_M - 1e-6:
                violations.append(Violation(
                    rule_id="GEOM-002",
                    severity="error",
                    message=(
                        f"Escora a {dist:.2f}m da borda da laje "
                        f"{panel.label or '?'}, mínimo é "
                        f"{SLAB_EDGE_MIN_DISTANCE_M}m"
                    ),
                    element_id=panel.label or None,
                    actual_value=round(dist, 3),
                    limit_value=SLAB_EDGE_MIN_DISTANCE_M,
                    location=(shore.x, shore.y),
                ))
    return violations


REGISTRY.register(_GEOM_002, _verify_slab_edge_setback)


# --- GEOM-003: Min spacing between shores >= 0.30m ---

_GEOM_003 = Rule(
    id="GEOM-003",
    category="GEOM",
    source=Source(
        type="engineer_qa", ref="Orguel practice",
        calibration="Orguel 2026-04-07 (n=12)",
    ),
    description_pt="Espaçamento mínimo de 0.30 m entre escoras adjacentes",
    severity="error",
)

MIN_SHORE_SPACING_M = 0.30


def _verify_min_spacing(project: "RuleProject") -> list[Violation]:
    violations = []
    shores = project.shore_positions
    seen_pairs: set[tuple[int, int]] = set()
    for i, s1 in enumerate(shores):
        for j, s2 in enumerate(shores):
            if i >= j:
                continue
            pair = (i, j)
            if pair in seen_pairs:
                continue
            dist = ((s1.x - s2.x) ** 2 + (s1.y - s2.y) ** 2) ** 0.5
            if dist < MIN_SHORE_SPACING_M - 1e-6:
                seen_pairs.add(pair)
                violations.append(Violation(
                    rule_id="GEOM-003",
                    severity="error",
                    message=(
                        f"Escoras a {dist:.2f}m de distância, "
                        f"mínimo é {MIN_SHORE_SPACING_M}m"
                    ),
                    actual_value=round(dist, 3),
                    limit_value=MIN_SHORE_SPACING_M,
                    location=(s1.x, s1.y),
                ))
    return violations


REGISTRY.register(_GEOM_003, _verify_min_spacing)


# --- GEOM-004: Shore inside slab polygon ---

_GEOM_004 = Rule(
    id="GEOM-004",
    category="GEOM",
    source=Source(type="manual", ref="Implícito — definição de escora suportando laje"),
    description_pt="Toda escora posicionada deve estar dentro do polígono real da laje",
    severity="error",
)


def _verify_shore_in_polygon(project: "RuleProject") -> list[Violation]:
    violations = []
    for panel in project.slab_panels:
        poly = panel.polygon
        if not hasattr(poly, 'contains'):
            continue
        for shore in panel.shores:
            pt = Point(shore.x, shore.y)
            # Allow points on the boundary (within tolerance)
            if not poly.contains(pt) and not poly.boundary.distance(pt) < 0.01:
                violations.append(Violation(
                    rule_id="GEOM-004",
                    severity="error",
                    message=(
                        f"Escora em ({shore.x:.2f}, {shore.y:.2f}) está fora "
                        f"do polígono da laje {panel.label or '?'}"
                    ),
                    element_id=panel.label or None,
                    actual_value=f"({shore.x:.2f}, {shore.y:.2f})",
                    limit_value="Dentro do polígono",
                    location=(shore.x, shore.y),
                ))
    return violations


REGISTRY.register(_GEOM_004, _verify_shore_in_polygon)


# --- GEOM-005: Cotas from concreted structure (Orguel p.23) ---
# This is a documentation/output rule — verifiable only when dimension
# entities exist in the output DXF. For now, it's a placeholder that
# always passes (no DXF dimension entities in RuleProject).

_GEOM_005 = Rule(
    id="GEOM-005",
    category="GEOM",
    source=Source(type="manual", ref="Orguel p.23"),
    description_pt=(
        "Cotas sempre em relação à estrutura concretada "
        "(pilar ou parede), nunca de referência arbitrária"
    ),
    severity="warning",
)


def _verify_cotas_reference(project: "RuleProject") -> list[Violation]:
    # TODO(engineer-confirmation): This rule requires DXF dimension
    # entity analysis. Currently a no-op — will be implemented when
    # the output DXF writer encodes dimension origins.
    return []


REGISTRY.register(_GEOM_005, _verify_cotas_reference)


# --- GEOM-006: Alvenaria offset <= 5cm (Orguel p.107, regra 12) ---

_GEOM_006 = Rule(
    id="GEOM-006",
    category="GEOM",
    source=Source(type="manual", ref="Orguel p.107 regra 12"),
    description_pt=(
        "Distância dos barrotes para alvenaria estrutural ≤ 5 cm "
        "(guias e barrotes quase encostados na alvenaria)"
    ),
    severity="warning",
)

ALVENARIA_MAX_OFFSET_M = 0.05


def _verify_alvenaria_offset(project: "RuleProject") -> list[Violation]:
    # TODO(engineer-confirmation): Requires wall/masonry geometry in
    # RuleProject. Currently not available from the pipeline.
    # Will be implemented when wall detection is added.
    return []


REGISTRY.register(_GEOM_006, _verify_alvenaria_offset)


# --- GEOM-007: Barrote edge offset (Orguel p.105-106, regra 11 — corrected) ---
# With lateral wall form: 20-40 cm from form edge to first barrote
# Without lateral wall form (laje encostada): 5 cm from concrete edge

_GEOM_007 = Rule(
    id="GEOM-007",
    category="GEOM",
    source=Source(type="manual", ref="Orguel p.105-106 regra 11"),
    description_pt=(
        "Offset de barrotes na borda da laje: com forma lateral 20-40 cm, "
        "sem forma lateral (laje encostada) 5 cm"
    ),
    severity="warning",
)


def _verify_barrote_edge_offset(project: "RuleProject") -> list[Violation]:
    # TODO(engineer-confirmation): Requires barrote position data and
    # wall-form detection. Currently not available from the pipeline.
    # The rule has two distinct cases that need wall adjacency info.
    return []


REGISTRY.register(_GEOM_007, _verify_barrote_edge_offset)
