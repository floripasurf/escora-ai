"""Tower vs telescopic shore decision engine and tower selection.

Decision criteria (NBR 15696 + practical engineering):
- Height > 4.5m → tower required (telescopic shore limit)
- Load > 20 kN/point → tower recommended (heavy loads)
- Height > 12m OR span > 15m → cimbramento (tower + distribution beam)
- Ribbed slab with h > 30cm → tower with distribution beam

When towers are selected, also selects appropriate distribution beams
to transfer load from the slab/beam to the tower heads.
"""

import json
import math
import logging
from pathlib import Path
from typing import List, Optional, Tuple
from src.models.shore import (
    ShoreCatalogEntry, TowerCatalogEntry, DistributionBeamEntry,
    SupportType,
)

logger = logging.getLogger(__name__)

# Decision thresholds
MAX_TELESCOPIC_HEIGHT_M = 4.5       # Above this → tower
MAX_TELESCOPIC_LOAD_KN = 20.0       # Above this → tower recommended
CIMBRAMENTO_HEIGHT_M = 12.0         # Above this → heavy cimbramento
CIMBRAMENTO_SPAN_M = 15.0           # Above this → heavy cimbramento
HEAVY_SLAB_THICKNESS_M = 0.30       # Above this → tower with dist. beam


def load_tower_catalog(catalog_path: Optional[str] = None) -> Tuple[
    List[TowerCatalogEntry], List[DistributionBeamEntry],
]:
    """Load tower and distribution beam catalog from JSON."""
    if catalog_path is None:
        catalog_path = str(
            Path(__file__).parent.parent.parent / "data" / "catalogs" / "shoring_towers.json"
        )

    with open(catalog_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    towers = [TowerCatalogEntry(**t) for t in data.get("towers", [])]
    beams = [DistributionBeamEntry(**b) for b in data.get("distribution_beams", [])]
    return towers, beams


def decide_support_type(
    required_height_m: float,
    load_per_point_kn: float,
    slab_thickness_m: float = 0.12,
    span_m: float = 0.0,
    slab_type: str = "solid",
) -> Tuple[SupportType, List[str]]:
    """Decide between telescopic shore and tower.

    Returns (support_type, reasons) where reasons explain the decision.
    """
    reasons = []

    # Rule 1: Height exceeds telescopic limit
    if required_height_m > MAX_TELESCOPIC_HEIGHT_M:
        reasons.append(
            f"Altura {required_height_m:.1f}m > {MAX_TELESCOPIC_HEIGHT_M}m "
            f"(limite escora telescópica)"
        )
        return SupportType.TOWER, reasons

    # Rule 2: Heavy load per point
    if load_per_point_kn > MAX_TELESCOPIC_LOAD_KN:
        reasons.append(
            f"Carga {load_per_point_kn:.1f} kN > {MAX_TELESCOPIC_LOAD_KN} kN "
            f"(limite escora telescópica padrão)"
        )
        return SupportType.TOWER, reasons

    # Rule 3: Large span (cimbramento)
    if span_m > CIMBRAMENTO_SPAN_M:
        reasons.append(
            f"Vão {span_m:.1f}m > {CIMBRAMENTO_SPAN_M}m "
            f"(requer cimbramento com torres)"
        )
        return SupportType.TOWER, reasons

    # Rule 4: Heavy slab
    if slab_thickness_m > HEAVY_SLAB_THICKNESS_M:
        reasons.append(
            f"Laje espessa {slab_thickness_m*100:.0f}cm > {HEAVY_SLAB_THICKNESS_M*100:.0f}cm "
            f"(recomendado torre com viga de distribuição)"
        )
        return SupportType.TOWER, reasons

    # Rule 5: Ribbed slab (weight of formwork)
    if slab_type == "ribbed" and slab_thickness_m > 0.25:
        reasons.append(
            f"Laje nervurada h={slab_thickness_m*100:.0f}cm "
            f"(peso de forma requer torre)"
        )
        return SupportType.TOWER, reasons

    # Default: telescopic is fine
    reasons.append(
        f"Escora telescópica adequada "
        f"(h={required_height_m:.1f}m, carga={load_per_point_kn:.1f}kN)"
    )
    return SupportType.TELESCOPIC, reasons


def select_tower(
    towers: List[TowerCatalogEntry],
    required_height_m: float,
    required_capacity_kn: float,
) -> Optional[TowerCatalogEntry]:
    """Select the most economical tower that meets height and load requirements.

    Criteria:
    1. Max height sufficient
    2. Load capacity sufficient
    3. Minimum cost (modules × price)
    """
    compatible = [
        t for t in towers
        if t.max_height_m >= required_height_m
        and t.load_capacity_kn >= required_capacity_kn
    ]

    if not compatible:
        # Fallback: ignore height, select by capacity only
        compatible = [
            t for t in towers
            if t.load_capacity_kn >= required_capacity_kn
        ]

    if not compatible:
        return None

    # Select cheapest option for required height
    return min(compatible, key=lambda t: t.total_price_brl(required_height_m))


def select_distribution_beam(
    beams: List[DistributionBeamEntry],
    span_m: float,
    load_kn_m: float,
) -> Optional[DistributionBeamEntry]:
    """Select distribution beam that can span between towers/shores.

    Criteria:
    1. Max span ≥ required span
    2. Moment capacity ≥ M_max = q*L²/8
    3. Minimum cost per meter
    """
    m_required = load_kn_m * span_m ** 2 / 8.0  # Simply supported beam

    compatible = [
        b for b in beams
        if b.max_span_m >= span_m
        and b.moment_capacity_knm >= m_required
    ]

    if not compatible:
        # Fallback: select by moment capacity only
        compatible = [
            b for b in beams
            if b.moment_capacity_knm >= m_required
        ]

    if not compatible:
        return None

    return min(compatible, key=lambda b: b.price_per_m_brl)


def calculate_tower_grid(
    area_width_m: float,
    area_height_m: float,
    tower: TowerCatalogEntry,
    total_load_kn: float,
    max_spacing_m: float = 3.0,
) -> Tuple[int, int, float, float]:
    """Calculate tower grid dimensions for a given area.

    Spacing is limited by:
    - Tower capacity (load per tower ≤ tower capacity)
    - Distribution beam span (can't exceed beam max_span)
    - Maximum practical spacing (typically 2-3m for towers)

    Returns: (nx, ny, spacing_x, spacing_y)
    """
    # Calculate minimum towers needed by capacity
    min_towers = math.ceil(total_load_kn / tower.load_capacity_kn)
    min_towers = max(min_towers, 4)  # Minimum 2x2 grid

    # Start with max spacing and reduce if needed
    nx = max(2, math.ceil(area_width_m / max_spacing_m) + 1)
    ny = max(2, math.ceil(area_height_m / max_spacing_m) + 1)

    # Ensure enough towers for load
    while nx * ny < min_towers:
        if area_width_m / nx > area_height_m / ny:
            nx += 1
        else:
            ny += 1

    spacing_x = area_width_m / max(nx - 1, 1)
    spacing_y = area_height_m / max(ny - 1, 1)

    # Verify load per tower
    load_per_tower = total_load_kn / (nx * ny)
    if load_per_tower > tower.load_capacity_kn:
        # Need more towers
        factor = math.sqrt(load_per_tower / tower.load_capacity_kn)
        nx = math.ceil(nx * factor)
        ny = math.ceil(ny * factor)
        spacing_x = area_width_m / max(nx - 1, 1)
        spacing_y = area_height_m / max(ny - 1, 1)

    return nx, ny, spacing_x, spacing_y
