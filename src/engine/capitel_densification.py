"""Capitel densification for flat slabs (Orguel Q6).

Regra da locadora (Q6): "Em laje lisa, concentrar torres/escoras em pontos
de capitel, mantendo grid regular no restante do painel." Traduzimos isso
como uma densificação local ao redor de cada pilar:

- **Anel interno**: 0.70 m (DISTANCIA_PILAR_MIN — zona de punção NBR 6118)
- **Anel externo**: 1.50 m (CAPITEL_OUTER_RADIUS_M)
- **Espaçamento**: 30% menor que o grid padrão (CAPITEL_SPACING_FACTOR=0.70)

O helper aqui devolve apenas as escoras **extras** a serem adicionadas;
o grid regular é calculado à parte por `distribute_shores`. Escoras já
existentes são respeitadas (não duplicamos).
"""

import math
from typing import List, Tuple

from shapely.geometry import Point, Polygon

from src.models.shore import PositionedShore, ShoreCatalogEntry
from src.utils.constants import DISTANCIA_PILAR_MIN


# Raio externo do anel de capitel (m). Dentro deste raio, o grid é densificado.
CAPITEL_OUTER_RADIUS_M = 1.50
# Fator de espaçamento dentro do capitel (0.70 = 30% menor).
CAPITEL_SPACING_FACTOR = 0.70
# Folga mínima para deduplicar contra escoras pré-existentes (m).
_CAPITEL_DEDUP_MIN_DIST_M = 0.40


def _is_clear(
    x: float,
    y: float,
    polygon: Polygon,
    existing_shores: List[PositionedShore],
    candidates: List[PositionedShore],
) -> bool:
    if not polygon.contains(Point(x, y)):
        return False
    for s in existing_shores:
        if math.hypot(s.x - x, s.y - y) < _CAPITEL_DEDUP_MIN_DIST_M:
            return False
    for s in candidates:
        if math.hypot(s.x - x, s.y - y) < _CAPITEL_DEDUP_MIN_DIST_M:
            return False
    return True


def capitel_densification_shores(
    polygon: Polygon,
    shore_entry: ShoreCatalogEntry,
    pillar_positions: List[Tuple[float, float]],
    existing_shores: List[PositionedShore],
    max_spacing: float,
) -> List[PositionedShore]:
    """Gera escoras extras em zonas de capitel ao redor de cada pilar.

    Para cada pilar cujo entorno intercepta o polígono, distribui escoras
    em pelo menos um anel (até 2) entre `DISTANCIA_PILAR_MIN` e
    `CAPITEL_OUTER_RADIUS_M`, com espaçamento angular calibrado para
    `max_spacing × CAPITEL_SPACING_FACTOR` na circunferência externa.

    Args:
        polygon: polígono da laje (Shapely Polygon).
        shore_entry: modelo de escora telescópica a usar.
        pillar_positions: lista (x, y) de centros de pilares.
        existing_shores: escoras já colocadas pelo grid regular.
        max_spacing: espaçamento máximo do grid regular (m).
    """
    if not pillar_positions:
        return []

    densified_spacing = max(0.50, max_spacing * CAPITEL_SPACING_FACTOR)
    # Raios dos anéis — pelo menos o externo; se couber outro, usa 2.
    rings = [CAPITEL_OUTER_RADIUS_M]
    mid = (DISTANCIA_PILAR_MIN + CAPITEL_OUTER_RADIUS_M) / 2.0
    if mid - DISTANCIA_PILAR_MIN >= densified_spacing / 2:
        rings.insert(0, mid)

    extra: List[PositionedShore] = []
    for cx, cy in pillar_positions:
        # Skip pillars whose whole capitel ring is outside the polygon (fast prune)
        probe = Point(cx, cy).buffer(CAPITEL_OUTER_RADIUS_M)
        if not polygon.intersects(probe):
            continue

        for radius in rings:
            # 8 azimuths — suficiente para cobrir o anel em grids 1-1.3m
            circumference = 2 * math.pi * radius
            n_pts = max(4, int(math.ceil(circumference / densified_spacing)))
            for k in range(n_pts):
                theta = 2 * math.pi * k / n_pts
                x = cx + radius * math.cos(theta)
                y = cy + radius * math.sin(theta)
                if not _is_clear(x, y, polygon, existing_shores, extra):
                    continue
                extra.append(PositionedShore(
                    x=round(x, 4),
                    y=round(y, 4),
                    shore=shore_entry,
                    load_applied_kn=0.0,
                    utilization_ratio=0.0,
                ))

    return extra
