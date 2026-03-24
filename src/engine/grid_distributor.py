"""Distribuição de escoras em grid regular."""

import math
from typing import List, Tuple
from src.models.slab import Slab
from src.models.shore import PositionedShore, ShoreCatalogEntry
from src.utils.constants import ESPACAMENTO_MAX_DEFAULT, DISTANCIA_BORDA_MIN


def calculate_grid_dimensions(
    width: float,
    height: float,
    max_spacing: float = ESPACAMENTO_MAX_DEFAULT,
) -> Tuple[int, int, float, float]:
    """
    Calcula dimensões do grid de escoras.

    Retorna: (nx, ny, spacing_x, spacing_y)
    """
    # Área útil (desconta bordas)
    usable_width = width - 2 * DISTANCIA_BORDA_MIN
    usable_height = height - 2 * DISTANCIA_BORDA_MIN

    if usable_width <= 0 or usable_height <= 0:
        return 1, 1, 0.0, 0.0

    nx = math.ceil(usable_width / max_spacing) + 1
    ny = math.ceil(usable_height / max_spacing) + 1

    # Garante mínimo de 2x2
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
) -> Tuple[List[PositionedShore], int, int, float, float]:
    """
    Distribui escoras em grid regular sobre a laje.

    Retorna: (shores, nx, ny, spacing_x, spacing_y)
    """
    bb = slab.bounding_box
    width = bb.width
    height = bb.height

    nx, ny, spacing_x, spacing_y = calculate_grid_dimensions(
        width, height, max_spacing
    )

    total_shores = nx * ny
    load_per_shore = total_load_kn / total_shores
    utilization = load_per_shore / shore.load_capacity_kn

    shores: List[PositionedShore] = []
    start_x = bb.min_x + DISTANCIA_BORDA_MIN
    start_y = bb.min_y + DISTANCIA_BORDA_MIN

    for i in range(nx):
        for j in range(ny):
            x = start_x + i * spacing_x if nx > 1 else start_x + width / 2
            y = start_y + j * spacing_y if ny > 1 else start_y + height / 2

            shores.append(
                PositionedShore(
                    x=round(x, 4),
                    y=round(y, 4),
                    shore=shore,
                    load_applied_kn=round(load_per_shore, 2),
                    utilization_ratio=round(utilization, 4),
                )
            )

    return shores, nx, ny, spacing_x, spacing_y
