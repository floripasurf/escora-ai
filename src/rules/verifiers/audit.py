"""Verificadores de AUDITORIA visual automatica — OP-101/002.

Decisao do revisor (2026-06-12): os defeitos que ele vinha marcando a mao
nas inspecoes (viga sem escoramento; escoras coladas) devem ser checks do
proprio script, emitidos como Violations com localizacao — para aparecerem
no relatorio e na camada de falhas do DXF.

OP-101: viga calculada sem escoras, ou com VAO entre escoras
consecutivas (projetadas no eixo) acima do teto pratico.
OP-102: par de escoras (qualquer tipo, incluindo viga x viga em
cruzamentos) a menos da distancia minima global.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from src.rules.schema import REGISTRY, Rule, Source, Violation

if TYPE_CHECKING:
    from src.rules.project import RuleProject

# Teto de vao sem escora ao longo de viga calculada (folga sobre o teto
# pratico de 1.00 m do manual §10.3; acima disso e buraco de escoramento).
AUDIT_BEAM_GAP_MAX_M = 1.80
# Distancia minima global entre escoras (manual §11.1/ESPACAMENTO_MIN +
# decisao do revisor v10; vira campo do perfil §28.9).
AUDIT_MIN_SHORE_DIST_M = 0.30


_OP_101 = Rule(
    id="OP-101",
    category="OP",
    source=Source(type="manual", ref="Inspecao do revisor 2026-06-12 / manual §10.3"),
    description_pt=(
        "Toda viga calculada deve ter escoras ao longo do eixo, sem vao "
        "maior que o teto pratico"
    ),
    severity="error",
)


def _verify_beam_shoring_coverage(project: "RuleProject") -> list[Violation]:
    violations: list[Violation] = []
    for beam in project.beams:
        if beam.length_m < 1.0 or len(beam.centerline) < 2:
            continue
        (x1, y1), (x2, y2) = beam.centerline[0], beam.centerline[-1]
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1.0:
            continue
        if not beam.shores:
            violations.append(Violation(
                rule_id="OP-101",
                severity="error",
                message=(
                    f"Viga {beam.label or 'sem nome'} ({L:.1f} m) SEM "
                    f"nenhuma escora — verificar classificacao/filtros"
                ),
                element_id=beam.label or None,
                actual_value=0,
                location=((x1 + x2) / 2, (y1 + y2) / 2),
            ))
            continue
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        ts = sorted(
            (s.x - x1) * ux + (s.y - y1) * uy for s in beam.shores
        )
        # Incluir extremos da viga como bordas do vao
        gaps = []
        prev = 0.0
        for t in ts + [L]:
            gaps.append((t - prev, prev, t))
            prev = t
        for gap, t_lo, t_hi in gaps:
            if gap > AUDIT_BEAM_GAP_MAX_M:
                mx = x1 + ux * (t_lo + t_hi) / 2
                my = y1 + uy * (t_lo + t_hi) / 2
                violations.append(Violation(
                    rule_id="OP-101",
                    severity="error",
                    message=(
                        f"Viga {beam.label or 'sem nome'}: vao de "
                        f"{gap:.2f} m sem escora (teto "
                        f"{AUDIT_BEAM_GAP_MAX_M:.2f} m) — trecho sem "
                        f"escoramento"
                    ),
                    element_id=beam.label or None,
                    actual_value=round(gap, 2),
                    limit_value=AUDIT_BEAM_GAP_MAX_M,
                    location=(round(mx, 2), round(my, 2)),
                ))
    return violations


REGISTRY.register(_OP_101, _verify_beam_shoring_coverage)


_OP_102 = Rule(
    id="OP-102",
    category="OP",
    source=Source(type="manual", ref="Inspecao do revisor 2026-06-12 / v10"),
    description_pt=(
        "Nenhum par de escoras (incluindo viga x viga em cruzamentos) a "
        "menos da distancia minima global"
    ),
    severity="warning",
)


def _verify_global_shore_distance(project: "RuleProject") -> list[Violation]:
    # shore_positions ja agrega escoras de VIGA e de LAJE (RuleProject
    # .from_pipeline_result) — nao somar beam.shores de novo, senao cada
    # escora de viga vira um falso par a 0.00 m consigo mesma.
    pts = [(s.x, s.y) for s in project.shore_positions]
    cell = AUDIT_MIN_SHORE_DIST_M
    occupied: dict = {}
    violations: list[Violation] = []
    seen: set = set()
    for x, y in pts:
        k = (int(math.floor(x / cell)), int(math.floor(y / cell)))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for ox, oy in occupied.get((k[0] + dx, k[1] + dy), ()):
                    d = math.hypot(x - ox, y - oy)
                    if d < AUDIT_MIN_SHORE_DIST_M:
                        key = (round((x + ox) / 2, 1), round((y + oy) / 2, 1))
                        if key in seen:
                            continue
                        seen.add(key)
                        violations.append(Violation(
                            rule_id="OP-102",
                            severity="warning",
                            message=(
                                f"Escoras a {d:.2f} m uma da outra "
                                f"(< {AUDIT_MIN_SHORE_DIST_M:.2f} m) em "
                                f"({key[0]}, {key[1]}) — tipico em "
                                f"cruzamento de vigas; remover/snap"
                            ),
                            actual_value=round(d, 3),
                            limit_value=AUDIT_MIN_SHORE_DIST_M,
                            location=key,
                        ))
        occupied.setdefault(k, []).append((x, y))
    return violations


REGISTRY.register(_OP_102, _verify_global_shore_distance)
