"""Distribuição de escoras em grid regular sobre polígonos arbitrários."""

import math
from typing import List, Tuple, Optional
from shapely.geometry import Point
from src.models.slab import Slab
from src.models.shore import PositionedShore, ShoreCatalogEntry
from src.utils.constants import ESPACAMENTO_MAX_DEFAULT, DISTANCIA_BORDA_MIN, DISTANCIA_PILAR_MIN, ESPACAMENTO_MIN
from src.engine.shore_capacity import compute_adaptive_spacing


def _is_narrow_corridor(slab: 'Slab', max_spacing: float) -> bool:
    """Check if a slab is a narrow corridor (width < 2× max_spacing)."""
    bb = slab.bounding_box
    min_dim = min(bb.width, bb.height)
    return min_dim < 2 * max_spacing


def _distribute_linear(
    slab: 'Slab',
    shore: 'ShoreCatalogEntry',
    total_load_kn: float,
    max_spacing: float,
    exclusions: Optional[List['PillarExclusion']] = None,
) -> Tuple[List[PositionedShore], int, int, float, float]:
    """Linear distribution for narrow corridors.

    Instead of a 2D grid (which produces irregular patterns in narrow slabs),
    places shores along the central axis of the corridor at regular intervals.

    Uses minimum_rotated_rectangle to find the principal axis, then generates
    points along the centerline.
    """
    polygon = slab.polygon
    mrr = polygon.minimum_rotated_rectangle
    coords = list(mrr.exterior.coords)

    # Identify long axis from minimum rotated rectangle
    edge1_len = math.hypot(coords[1][0] - coords[0][0], coords[1][1] - coords[0][1])
    edge2_len = math.hypot(coords[2][0] - coords[1][0], coords[2][1] - coords[1][1])

    if edge1_len >= edge2_len:
        start = ((coords[0][0] + coords[3][0]) / 2, (coords[0][1] + coords[3][1]) / 2)
        end = ((coords[1][0] + coords[2][0]) / 2, (coords[1][1] + coords[2][1]) / 2)
    else:
        start = ((coords[0][0] + coords[1][0]) / 2, (coords[0][1] + coords[1][1]) / 2)
        end = ((coords[3][0] + coords[2][0]) / 2, (coords[3][1] + coords[2][1]) / 2)

    length = math.hypot(end[0] - start[0], end[1] - start[1])
    if length < 0.01:
        # Degenerate — fallback to centroid
        centroid = polygon.centroid
        s = PositionedShore(
            x=round(centroid.x, 4), y=round(centroid.y, 4),
            shore=shore, load_applied_kn=total_load_kn, utilization_ratio=0.0,
        )
        return [s], 1, 1, 0.0, 0.0

    # Recede start/end by DISTANCIA_BORDA_MIN along the axis
    dx, dy = (end[0] - start[0]) / length, (end[1] - start[1]) / length
    effective_start = (start[0] + dx * DISTANCIA_BORDA_MIN, start[1] + dy * DISTANCIA_BORDA_MIN)
    effective_end = (end[0] - dx * DISTANCIA_BORDA_MIN, end[1] - dy * DISTANCIA_BORDA_MIN)
    effective_length = length - 2 * DISTANCIA_BORDA_MIN

    if effective_length <= 0:
        n_points = 1
    else:
        n_points = max(2, math.ceil(effective_length / max_spacing) + 1)

    shores: List[PositionedShore] = []
    for i in range(n_points):
        if n_points == 1:
            t = 0.5
            x = (start[0] + end[0]) / 2
            y = (start[1] + end[1]) / 2
        else:
            t = i / (n_points - 1)
            x = effective_start[0] + t * (effective_end[0] - effective_start[0])
            y = effective_start[1] + t * (effective_end[1] - effective_start[1])

        point = Point(x, y)
        if not polygon.contains(point):
            continue

        if exclusions and any(exc.contains(x, y) for exc in exclusions):
            continue

        # Check minimum spacing
        too_close = False
        for existing in shores:
            if math.hypot(x - existing.x, y - existing.y) < ESPACAMENTO_MIN:
                too_close = True
                break
        if too_close:
            continue

        shores.append(PositionedShore(
            x=round(x, 4), y=round(y, 4),
            shore=shore, load_applied_kn=0.0, utilization_ratio=0.0,
        ))

    # Fallback: at least 1 shore at centroid
    if not shores:
        centroid = polygon.centroid
        shores.append(PositionedShore(
            x=round(centroid.x, 4), y=round(centroid.y, 4),
            shore=shore, load_applied_kn=0.0, utilization_ratio=0.0,
        ))

    # Recalculate loads
    if shores:
        load_per_shore = total_load_kn / len(shores)
        utilization = load_per_shore / shore.load_capacity_kn
        for s in shores:
            s.load_applied_kn = round(load_per_shore, 2)
            s.utilization_ratio = round(utilization, 4)

    spacing = effective_length / (n_points - 1) if n_points > 1 else 0.0
    return shores, n_points, 1, spacing, 0.0


class PillarExclusion:
    """Zona de exclusão retangular ao redor de um pilar."""

    def __init__(self, cx: float, cy: float, width_m: float, depth_m: float,
                 margin: float = DISTANCIA_PILAR_MIN):
        self.cx = cx
        self.cy = cy
        half_w = width_m / 2 + margin
        half_d = depth_m / 2 + margin
        self.min_x = cx - half_w
        self.max_x = cx + half_w
        self.min_y = cy - half_d
        self.max_y = cy + half_d

    def contains(self, x: float, y: float) -> bool:
        return (self.min_x <= x <= self.max_x and
                self.min_y <= y <= self.max_y)


def calculate_grid_dimensions(
    width: float,
    height: float,
    max_spacing: float = ESPACAMENTO_MAX_DEFAULT,
) -> Tuple[int, int, float, float]:
    """
    Calcula dimensões do grid de escoras sobre o bounding box.

    Retorna: (nx, ny, spacing_x, spacing_y)
    """
    usable_width = width - 2 * DISTANCIA_BORDA_MIN
    usable_height = height - 2 * DISTANCIA_BORDA_MIN

    if usable_width <= 0 or usable_height <= 0:
        return 1, 1, 0.0, 0.0

    nx = math.ceil(usable_width / max_spacing) + 1
    ny = math.ceil(usable_height / max_spacing) + 1

    nx = max(nx, 2)
    ny = max(ny, 2)

    spacing_x = usable_width / (nx - 1)
    spacing_y = usable_height / (ny - 1)

    return nx, ny, spacing_x, spacing_y


def distribute_shores(
    slab: Slab,
    shore: ShoreCatalogEntry,
    total_load_kn: float,
    max_spacing: float = ESPACAMENTO_MAX_DEFAULT,
    exclusions: Optional[List[PillarExclusion]] = None,
    floor_height_m: Optional[float] = None,
    global_origin: Optional[Tuple[float, float]] = None,
) -> Tuple[List[PositionedShore], int, int, float, float]:
    """
    Distribui escoras em grid regular sobre a laje.

    O grid é gerado sobre o bounding box, mas cada ponto é verificado:
    1. Deve estar DENTRO do polígono real da laje (suporta qualquer forma)
    2. Deve respeitar a distância mínima da borda do polígono (DISTANCIA_BORDA_MIN)
    3. Não pode cair em zona de exclusão de pilar

    Quando floor_height_m é fornecido, calcula espaçamento adaptativo baseado
    na carga real (espessura da laje + capacidade derateada da escora). O
    max_spacing passado funciona como TETO — o espaçamento adaptativo nunca
    ultrapassa o max_spacing.

    Quando global_origin é fornecido, o grid é alinhado a esse ponto global
    em vez do bounding box individual — garante alinhamento entre lajes
    adjacentes.

    Suporta polígonos com qualquer número de lados e ângulos não retos.

    Retorna: (shores, nx, ny, spacing_x, spacing_y)
    """
    bb = slab.bounding_box
    width = bb.width
    height = bb.height

    # Espaçamento adaptativo: calcula a partir de carga/capacidade quando possível
    effective_spacing = max_spacing

    # Pre-compute adaptive spacing for corridor check
    if floor_height_m is not None and slab.thickness_m > 0:
        derated_cap = shore.effective_capacity(floor_height_m)
        _adaptive = compute_adaptive_spacing(
            slab_thickness_m=slab.thickness_m,
            floor_height_m=floor_height_m,
            shore_capacity_kn=derated_cap,
        )
        effective_spacing = min(_adaptive, max_spacing)

    # Narrow corridor detection: use linear distribution instead of grid
    if _is_narrow_corridor(slab, effective_spacing):
        return _distribute_linear(slab, shore, total_load_kn, effective_spacing, exclusions)

    # Reset effective_spacing for the normal grid path below
    effective_spacing = max_spacing
    if floor_height_m is not None and slab.thickness_m > 0:
        derated_cap = shore.effective_capacity(floor_height_m)
        adaptive = compute_adaptive_spacing(
            slab_thickness_m=slab.thickness_m,
            floor_height_m=floor_height_m,
            shore_capacity_kn=derated_cap,
        )
        effective_spacing = min(adaptive, max_spacing)

    # Usar o polígono real da laje para verificar contenção.
    # A distância da borda já é garantida pelo grid (start_x/y com offset).
    # Small positive buffer (5cm) on the polygon prevents grid points from
    # being rejected at slightly irregular edges — for rectangular buildings
    # this keeps the grid strictly orthogonal without holes.
    polygon_check = slab.polygon.buffer(0.05)

    shores: List[PositionedShore] = []

    # Grid alignment: when global_origin is provided, use a FIXED spacing
    # (effective_spacing) and snap grid lines to global coordinates so
    # adjacent slabs share exactly the same grid lines.
    if global_origin is not None:
        # Manual §28.7 fix (2026-05-31): snap o effective_spacing ao
        # valor padrao mais proximo de um conjunto pequeno. Lajes
        # adjacentes com spacing similar caem no mesmo valor.
        # Conjunto pequeno = mais alinhamento; conjunto grande = mais
        # otimizacao adaptativa. [0.80, 1.00, 1.20] e um compromisso:
        # mantem seguranca para lajes pesadas E maximiza alinhamento.
        STANDARD_SPACINGS = [0.80, 1.00, 1.20]
        candidates = [s for s in STANDARD_SPACINGS if s <= effective_spacing + 0.05]
        if candidates:
            spacing_x = max(candidates)
        else:
            spacing_x = STANDARD_SPACINGS[0]
        spacing_y = spacing_x
        ox, oy = global_origin
        # First grid line >= bb.min_x + DISTANCIA_BORDA_MIN
        first_nx = math.ceil((bb.min_x + DISTANCIA_BORDA_MIN - ox) / spacing_x) if spacing_x > 0 else 0
        first_ny = math.ceil((bb.min_y + DISTANCIA_BORDA_MIN - oy) / spacing_y) if spacing_y > 0 else 0
        # Last grid line <= bb.max_x - DISTANCIA_BORDA_MIN
        last_nx = math.floor((bb.max_x - DISTANCIA_BORDA_MIN - ox) / spacing_x) if spacing_x > 0 else 0
        last_ny = math.floor((bb.max_y - DISTANCIA_BORDA_MIN - oy) / spacing_y) if spacing_y > 0 else 0

        grid_xs = [ox + n * spacing_x for n in range(first_nx, last_nx + 1)]
        grid_ys = [oy + n * spacing_y for n in range(first_ny, last_ny + 1)]

        if not grid_xs:
            grid_xs = [bb.min_x + width / 2]
        if not grid_ys:
            grid_ys = [bb.min_y + height / 2]

        nx = len(grid_xs)
        ny = len(grid_ys)
    else:
        nx, ny, spacing_x, spacing_y = calculate_grid_dimensions(
            width, height, effective_spacing
        )
        start_x = bb.min_x + DISTANCIA_BORDA_MIN
        start_y = bb.min_y + DISTANCIA_BORDA_MIN
        grid_xs = [start_x + i * spacing_x if nx > 1 else bb.min_x + width / 2 for i in range(nx)]
        grid_ys = [start_y + j * spacing_y if ny > 1 else bb.min_y + height / 2 for j in range(ny)]

    for x in grid_xs:
        for y in grid_ys:

            point = Point(x, y)

            # 1. Verificar se está dentro do polígono real (não apenas bounding box)
            if not polygon_check.contains(point):
                continue

            # 2. Verificar zonas de exclusão de pilares
            if exclusions and any(exc.contains(x, y) for exc in exclusions):
                continue

            # 3. Enforce minimum spacing between shores
            too_close = False
            for existing in shores:
                if math.hypot(x - existing.x, y - existing.y) < ESPACAMENTO_MIN:
                    too_close = True
                    break
            if too_close:
                continue

            shores.append(
                PositionedShore(
                    x=round(x, 4),
                    y=round(y, 4),
                    shore=shore,
                    load_applied_kn=0.0,
                    utilization_ratio=0.0,
                )
            )

    # Guarantee at least 1 shore at the polygon centroid if the grid
    # produced no points (very small or irregular slabs).
    if not shores:
        centroid = slab.polygon.centroid
        shores.append(
            PositionedShore(
                x=round(centroid.x, 4),
                y=round(centroid.y, 4),
                shore=shore,
                load_applied_kn=0.0,
                utilization_ratio=0.0,
            )
        )

    # Recalcular carga com número efetivo de escoras
    if shores:
        load_per_shore = total_load_kn / len(shores)
        utilization = load_per_shore / shore.load_capacity_kn
        for s in shores:
            s.load_applied_kn = round(load_per_shore, 2)
            s.utilization_ratio = round(utilization, 4)

    return shores, nx, ny, spacing_x, spacing_y
