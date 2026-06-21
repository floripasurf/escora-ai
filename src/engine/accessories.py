"""Acessórios e estabilidade de torres — manual §13.7, §14, OP-028/OP-029.

Implementa as pendências 23 e 26 do manual (§21):

1. Tripés (manual §14, JAU pág. 70): obrigatórios em escora de EXTREMIDADE
   de linha de viga e em TRANSPASSE de viga; dispensáveis nas intermediárias.
   Regra de BOM: n_tripes = 2 por linha de viga + 1 por transpasse.

2. Folga de desforma (OP-028, JAU p.07/32): o conjunto sapata + forcado
   deve manter >= 10 cm de curso livre (rosca) em algum fuso para permitir
   a descida na desforma.

3. Estabilidade global de torres (manual §13.7):
   - esbeltez: altura total <= 4 x menor dimensão da base (JAU p.04);
     acima disso, estaiamento/contraventamento obrigatório;
   - gatilhos de altura: > 8 m revisão de engenharia; > 20 m projeto
     especial (fontes externas comparativas — severidade warning/error);
   - interligação: torres adjacentes sob carga concentrada devem ser
     interligadas (cantoneiras 300/500 mm ou DT — JAU p.11).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence, Tuple

# --- Tripés (manual §14 / JAU pág. 70) -------------------------------------

TRIPODS_PER_BEAM_LINE = 2  # 1 em cada extremidade da linha de escoras


def count_tripods(
    beam_lines: Sequence[Sequence[Tuple[float, float]]],
    transpasse_count: int = 0,
) -> int:
    """Quantidade de tripés para escoras sob viga.

    `beam_lines`: cada item é a sequência ordenada de pontos de escora de
    UMA linha de viga. Linhas com 1 escora levam 1 tripé (a própria escora
    é extremidade dupla). Linhas vazias não contam.
    `transpasse_count`: transpasses de viga (emendas de linhas), 1 tripé
    cada (JAU pág. 70: tripé obrigatório em transpasse).
    """
    total = 0
    for line in beam_lines:
        n = len(line)
        if n == 0:
            continue
        total += 1 if n == 1 else TRIPODS_PER_BEAM_LINE
    return total + max(0, transpasse_count)


# --- Folga de desforma (OP-028) ---------------------------------------------

DEFORM_CLEARANCE_MIN_M = 0.10  # JAU p.07/32: >= 10 cm de rosca livre


@dataclass(frozen=True)
class DeformClearance:
    """Resultado da verificação de folga de desforma de um conjunto."""
    ok: bool
    clearance_m: float
    message: str


def check_deform_clearance(
    total_travel_m: float,
    used_travel_m: float,
) -> DeformClearance:
    """Verifica folga de desforma >= 10 cm (OP-028).

    `total_travel_m`: curso total disponível nos fusos do conjunto
    (sapata ajustável + forcado ajustável). `used_travel_m`: curso já
    consumido pelo ajuste de altura (residual da seção 13.6).
    """
    clearance = total_travel_m - used_travel_m
    if clearance >= DEFORM_CLEARANCE_MIN_M:
        return DeformClearance(
            ok=True,
            clearance_m=clearance,
            message=f"Folga de desforma {clearance*100:.0f} cm >= 10 cm (OP-028)",
        )
    return DeformClearance(
        ok=False,
        clearance_m=clearance,
        message=(
            f"Folga de desforma {clearance*100:.0f} cm < 10 cm — ajustar a "
            f"combinação de painéis/abertura para deixar >= 10 cm de rosca "
            f"livre (OP-028, JAU p.07/32)"
        ),
    )


# --- Estabilidade de torres (manual §13.7) ----------------------------------

TOWER_SLENDERNESS_MAX = 4.0       # JAU p.04: H <= 4 x menor dimensão da base
TOWER_BASE_DEFAULT_M = 1.00       # menor painel/quadro de catálogo (§13.4)
TOWER_REVIEW_HEIGHT_M = 8.0       # manual §13.7: > 8 m -> revisão
TOWER_SPECIAL_HEIGHT_M = 20.0     # manual §13.7: > 20 m -> projeto especial
TOWER_TIE_DISTANCE_M = 2.5        # §13.7: torres adjacentes -> interligar


@dataclass(frozen=True)
class TowerStability:
    """Resultado da verificação de estabilidade de uma torre isolada."""
    ok: bool
    slenderness: float
    needs_bracing: bool      # esbeltez > 4:1 -> estaiar/contraventar
    needs_review: bool       # > 8 m
    is_special: bool         # > 20 m
    messages: Tuple[str, ...] = ()


def check_tower_stability(
    height_m: float,
    base_min_dim_m: float = TOWER_BASE_DEFAULT_M,
) -> TowerStability:
    """Esbeltez 4:1 + gatilhos de altura (manual §13.7, JAU p.04)."""
    msgs: List[str] = []
    if base_min_dim_m <= 0:
        base_min_dim_m = TOWER_BASE_DEFAULT_M
        msgs.append(
            "Base da torre desconhecida — usando 1.00 m (menor quadro de "
            "catálogo, §13.4); confirmar modelo."
        )
    slenderness = height_m / base_min_dim_m
    needs_bracing = slenderness > TOWER_SLENDERNESS_MAX
    needs_review = height_m > TOWER_REVIEW_HEIGHT_M
    is_special = height_m > TOWER_SPECIAL_HEIGHT_M
    if needs_bracing:
        msgs.append(
            f"Torre isolada com esbeltez {slenderness:.1f}:1 > 4:1 "
            f"(H={height_m:.2f} m, base {base_min_dim_m:.2f} m) — "
            f"estaiamento ou contraventamento OBRIGATÓRIO (JAU p.04, §13.7)"
        )
    if is_special:
        msgs.append(
            f"Torre com {height_m:.1f} m > 20 m — projeto especial (§13.7)"
        )
    elif needs_review:
        msgs.append(
            f"Torre com {height_m:.1f} m > 8 m — revisão de engenharia (§13.7)"
        )
    return TowerStability(
        ok=not (needs_bracing or is_special),
        slenderness=slenderness,
        needs_bracing=needs_bracing,
        needs_review=needs_review,
        is_special=is_special,
        messages=tuple(msgs),
    )


def tower_tie_groups(
    tower_xy: Sequence[Tuple[float, float]],
    max_distance_m: float = TOWER_TIE_DISTANCE_M,
) -> List[List[int]]:
    """Agrupa torres adjacentes (<= max_distance_m) que devem ser
    interligadas com cantoneiras/DT (manual §13.7, JAU p.11).

    Retorna grupos (índices em `tower_xy`) com 2+ torres. União por
    componentes conexos com distância euclidiana.
    """
    n = len(tower_xy)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        parent[find(i)] = find(j)

    for i in range(n):
        xi, yi = tower_xy[i]
        for j in range(i + 1, n):
            xj, yj = tower_xy[j]
            if math.hypot(xi - xj, yi - yj) <= max_distance_m:
                union(i, j)

    groups: dict = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return [g for g in groups.values() if len(g) >= 2]
