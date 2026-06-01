"""Capitel densification for flat slabs (Orguel Q6).

Regra da locadora (Q6): "Em laje lisa, concentrar torres/escoras em pontos
de capitel, mantendo grid regular no restante do painel." Traduzimos isso
como uma densificação local ao redor de cada pilar:

- **Anel interno**: 0.70 m (DISTANCIA_PILAR_MIN — zona de punção NBR 6118)
- **Anel externo**: 1.50 m (CAPITEL_OUTER_RADIUS_M)
- **Espaçamento**: 30% menor que o grid padrão (CAPITEL_SPACING_FACTOR=0.70)

**Alinhamento axial (bug fix 2026-04-16)**: as escoras de capitel são
geradas numa grade **cartesiana alinhada aos eixos X/Y** do plano, não
em anel angular. Isso garante que:

  - As escoras fiquem em colunas/fileiras travaveis com VM50 (travamento
    vertical desenhado por bins de coluna X).
  - O padrão visual case com o grid principal (Q9: "VMs apoiadas de
    torre a torre, vão quebrado pelas escoras").

O helper aqui devolve apenas as escoras **extras** a serem adicionadas;
o grid regular é calculado à parte por `distribute_shores`. Escoras já
existentes são respeitadas (não duplicamos).
"""

import math
from typing import List, Optional, Tuple

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
    pillar_positions: Optional[List[Tuple[float, float]]] = None,
) -> bool:
    if not polygon.contains(Point(x, y)):
        return False
    # Enforce minimum distance from ALL pillar faces (not just the
    # pillar that generated this offset). Prevents shores landing
    # right next to a neighboring pillar.
    if pillar_positions:
        for px, py in pillar_positions:
            if math.hypot(x - px, y - py) < DISTANCIA_PILAR_MIN - 1e-6:
                return False
    for s in existing_shores:
        if math.hypot(s.x - x, s.y - y) < _CAPITEL_DEDUP_MIN_DIST_M:
            return False
    for s in candidates:
        if math.hypot(s.x - x, s.y - y) < _CAPITEL_DEDUP_MIN_DIST_M:
            return False
    return True


def _axis_aligned_offsets(densified_spacing: float) -> List[Tuple[float, float]]:
    """Gera offsets (dx, dy) cartesianos dentro do anel de capitel.

    Itera multiplicadores inteiros i, j ∈ [-k, k] em torno de (0, 0);
    só retém pontos no anel [DISTANCIA_PILAR_MIN, CAPITEL_OUTER_RADIUS_M].
    Produz padrão típico de 8 pontos com spacing=0.91m: 4 cardinais +
    4 diagonais, todos alinhados ao eixo X/Y (±1·d, 0), (0, ±1·d),
    (±1·d, ±1·d).
    """
    max_k = max(1, int(math.ceil(CAPITEL_OUTER_RADIUS_M / densified_spacing)))
    offsets: List[Tuple[float, float]] = []
    for i in range(-max_k, max_k + 1):
        for j in range(-max_k, max_k + 1):
            if i == 0 and j == 0:
                continue
            dx = i * densified_spacing
            dy = j * densified_spacing
            r = math.hypot(dx, dy)
            if r < DISTANCIA_PILAR_MIN - 1e-6:
                continue
            if r > CAPITEL_OUTER_RADIUS_M + 1e-6:
                continue
            offsets.append((dx, dy))
    return offsets


def _snap_to_global_grid(
    x: float,
    y: float,
    global_origin: Tuple[float, float],
    spacing: float,
) -> Tuple[float, float]:
    """Snap (x, y) a uma posicao da grade global mais proxima.

    Manual §28.7 (2026-06-01): escoras de capitel densificadas eram
    posicionadas livremente ao redor de pilares, gerando padrao visual
    desalinhado do grid principal. Snap garante que cada escora cai num
    nó da grade global enquanto continua dentro do anel de capitel.
    """
    ox, oy = global_origin
    kx = round((x - ox) / spacing)
    ky = round((y - oy) / spacing)
    return (ox + kx * spacing, oy + ky * spacing)


def capitel_densification_shores(
    polygon: Polygon,
    shore_entry: ShoreCatalogEntry,
    pillar_positions: List[Tuple[float, float]],
    existing_shores: List[PositionedShore],
    max_spacing: float,
    global_origin: Optional[Tuple[float, float]] = None,
    grid_spacing: Optional[float] = None,
) -> List[PositionedShore]:
    """Gera escoras extras em zonas de capitel ao redor de cada pilar.

    Para cada pilar cujo entorno intercepta o polígono, distribui escoras
    numa grade **cartesiana alinhada aos eixos** dentro do anel de capitel
    [DISTANCIA_PILAR_MIN, CAPITEL_OUTER_RADIUS_M]. Com max_spacing≈1.30m,
    isso gera 4 cardinais em 0.91m + 4 diagonais em 1.29m por pilar —
    alinhadas em colunas/fileiras para permitir travamento VM50 vertical.

    Args:
        polygon: polígono da laje (Shapely Polygon).
        shore_entry: modelo de escora telescópica a usar.
        pillar_positions: lista (x, y) de centros de pilares.
        existing_shores: escoras já colocadas pelo grid regular.
        max_spacing: espaçamento máximo do grid regular (m).
        global_origin: (ox, oy) do grid global da laje. Quando fornecido,
            cada escora densificada e snap-ada ao no mais proximo da grade
            global, mantendo alinhamento visual com o grid regular.
            Manual §28.7 (2026-06-01, fix do bug 'capitel desalinhado').
        grid_spacing: espacamento da grade global. Requerido quando
            global_origin esta presente.
    """
    if not pillar_positions:
        return []

    densified_spacing = max(0.50, max_spacing * CAPITEL_SPACING_FACTOR)
    offsets = _axis_aligned_offsets(densified_spacing)

    use_snap = global_origin is not None and grid_spacing is not None and grid_spacing > 0

    extra: List[PositionedShore] = []
    for cx, cy in pillar_positions:
        # Skip pillars whose whole capitel ring is outside the polygon (fast prune)
        probe = Point(cx, cy).buffer(CAPITEL_OUTER_RADIUS_M)
        if not polygon.intersects(probe):
            continue

        for dx, dy in offsets:
            x = cx + dx
            y = cy + dy
            if use_snap:
                x, y = _snap_to_global_grid(x, y, global_origin, grid_spacing)
                # Apos snap, validar que ainda esta no anel de capitel
                r = math.hypot(x - cx, y - cy)
                if r < DISTANCIA_PILAR_MIN - 1e-6 or r > CAPITEL_OUTER_RADIUS_M + 1e-6:
                    continue
            if not _is_clear(x, y, polygon, existing_shores, extra, pillar_positions):
                continue
            extra.append(PositionedShore(
                x=round(x, 4),
                y=round(y, 4),
                shore=shore_entry,
                load_applied_kn=0.0,
                utilization_ratio=0.0,
            ))

    return extra
