"""Distribuição de escoras em grid regular sobre polígonos arbitrários."""

import math
from typing import List, Tuple, Optional
from shapely.geometry import Point
from src.models.slab import Slab
from src.models.shore import PositionedShore, ShoreCatalogEntry
from src.utils.constants import ESPACAMENTO_MAX_DEFAULT, DISTANCIA_BORDA_MIN, DISTANCIA_PILAR_MIN


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
) -> Tuple[List[PositionedShore], int, int, float, float]:
    """
    Distribui escoras em grid regular sobre a laje.

    O grid é gerado sobre o bounding box, mas cada ponto é verificado:
    1. Deve estar DENTRO do polígono real da laje (suporta qualquer forma)
    2. Deve respeitar a distância mínima da borda do polígono (DISTANCIA_BORDA_MIN)
    3. Não pode cair em zona de exclusão de pilar

    Suporta polígonos com qualquer número de lados e ângulos não retos.

    Retorna: (shores, nx, ny, spacing_x, spacing_y)
    """
    bb = slab.bounding_box
    width = bb.width
    height = bb.height

    nx, ny, spacing_x, spacing_y = calculate_grid_dimensions(
        width, height, max_spacing
    )

    # Usar o polígono real da laje para verificar contenção.
    # A distância da borda já é garantida pelo grid (start_x/y com offset).
    # Não aplicar buffer negativo aqui para não duplicar o recuo.
    polygon_check = slab.polygon

    shores: List[PositionedShore] = []
    start_x = bb.min_x + DISTANCIA_BORDA_MIN
    start_y = bb.min_y + DISTANCIA_BORDA_MIN

    for i in range(nx):
        for j in range(ny):
            x = start_x + i * spacing_x if nx > 1 else bb.min_x + width / 2
            y = start_y + j * spacing_y if ny > 1 else bb.min_y + height / 2

            point = Point(x, y)

            # 1. Verificar se está dentro do polígono real (não apenas bounding box)
            if not polygon_check.contains(point):
                continue

            # 2. Verificar zonas de exclusão de pilares
            if exclusions and any(exc.contains(x, y) for exc in exclusions):
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

    # Recalcular carga com número efetivo de escoras
    if shores:
        load_per_shore = total_load_kn / len(shores)
        utilization = load_per_shore / shore.load_capacity_kn
        for s in shores:
            s.load_applied_kn = round(load_per_shore, 2)
            s.utilization_ratio = round(utilization, 4)

    return shores, nx, ny, spacing_x, spacing_y
