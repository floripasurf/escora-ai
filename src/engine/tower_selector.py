"""Tower vs telescopic shore decision engine and tower selection.

Decision criteria (NBR 15696 + real Orguel/Mecanor practice):
- Height > 4.5m → tower required (ESC450 max limit)
- Load > 20 kN/point → tower recommended
- Ribbed/thick slab ≥ 30cm → tower with distribution beam
- Height > 12m OR span > 15m → heavy cimbramento

Real locadora insight (Orguel, calibrated on 12 real projects):
- Beams → ALWAYS tower with VM distribution (TORRE_VIGA + VM130/VM80)
  measured: TORRE_VIGA dominates in 8/8 analyzed Orguel beam plans
- Slabs → tower grid when area ≥ 40m² or thick ≥ 20cm, else shores
  (Orguel uses TORRE_LAJE for open continuous slab areas)
- Small cover slabs (<50m² total) → shores only (no towers)

Shore models: ESC310 (2.00-3.10m), ESC450 (3.00-4.50m)
VM130 lengths: 155, 205, 255, 310, 360, 410cm
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
MAX_TELESCOPIC_HEIGHT_M = 4.5       # ESC450 max height
CIMBRAMENTO_HEIGHT_M = 12.0         # Above this → heavy cimbramento
CIMBRAMENTO_SPAN_M = 15.0           # Above this → heavy cimbramento
HEAVY_SLAB_THICKNESS_M = 0.30       # Above this → tower with dist. beam

# Orguel-calibrated slab tower triggers (from 12-project analysis 2026-04-07)
SLAB_TOWER_AREA_M2 = 40.0           # ≥40m² panel → tower grid
SLAB_TOWER_THICKNESS_M = 0.20       # ≥20cm slab → tower grid

# NBR 15696 safety factor for shore load combinations
SHORE_SAFETY_FACTOR = 1.4


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
    element_type: str = "slab",
    slab_area_m2: float = 0.0,
    shore_catalog: Optional[List[ShoreCatalogEntry]] = None,
) -> Tuple[SupportType, List[str]]:
    """Decide between telescopic shore and tower.

    Physics-based escalation (NBR 15696 + Euler derating of telescopic shores):
    - Height > 4.5m → tower (ESC450 physical limit)
    - If a shore_catalog is provided and NO shore's derated capacity at
      required_height_m × SAFETY_FACTOR covers load_per_point_kn → tower
    - Slab area ≥ 40m² or thickness ≥ 20cm → tower grid (Orguel practice)
    - Otherwise → telescopic shore

    Returns (support_type, reasons) where reasons explain the decision.
    """
    reasons = []

    # Rule 1: Height exceeds telescopic limit (ESC450 max = 4.50m)
    if required_height_m > MAX_TELESCOPIC_HEIGHT_M:
        reasons.append(
            f"Altura {required_height_m:.1f}m > {MAX_TELESCOPIC_HEIGHT_M}m "
            f"(limite ESC450)"
        )
        return SupportType.TOWER, reasons

    # Rule 1b: Load-based derating check. When a catalog is provided, compare
    # the load per point against every shore's Euler-derated capacity at the
    # required extension height. If no telescopic shore can take the load with
    # the NBR 15696 safety factor, escalate to a tower.
    if shore_catalog and load_per_point_kn > 0:
        best_cap_kn = 0.0
        for shore in shore_catalog:
            eff = shore.effective_capacity(required_height_m)
            if eff > best_cap_kn:
                best_cap_kn = eff
        required_with_sf = load_per_point_kn * SHORE_SAFETY_FACTOR
        if best_cap_kn > 0 and best_cap_kn < required_with_sf:
            reasons.append(
                f"carga {load_per_point_kn:.1f} kN "
                f"(× SF {SHORE_SAFETY_FACTOR} = {required_with_sf:.1f} kN) > "
                f"capacidade derateada máxima {best_cap_kn:.1f} kN "
                f"para altura {required_height_m:.2f} m"
            )
            return SupportType.TOWER, reasons

    # Rule 2: Large span (cimbramento)
    if span_m > CIMBRAMENTO_SPAN_M:
        reasons.append(
            f"Vão {span_m:.1f}m > {CIMBRAMENTO_SPAN_M}m "
            f"(requer cimbramento com torres)"
        )
        return SupportType.TOWER, reasons

    # Rule 3: Heavy/thick slab (≥20cm) — Orguel uses TORRE_LAJE
    if slab_thickness_m >= SLAB_TOWER_THICKNESS_M:
        reasons.append(
            f"Laje {slab_thickness_m*100:.0f}cm ≥ {SLAB_TOWER_THICKNESS_M*100:.0f}cm "
            f"(TORRE_LAJE com viga de distribuição — padrão Orguel)"
        )
        return SupportType.TOWER, reasons

    # Rule 3b: Large slab panel — Orguel uses TORRE_LAJE for open areas
    if slab_area_m2 >= SLAB_TOWER_AREA_M2:
        reasons.append(
            f"Painel de laje {slab_area_m2:.0f}m² ≥ {SLAB_TOWER_AREA_M2:.0f}m² "
            f"(TORRE_LAJE em grid — padrão Orguel para áreas contínuas)"
        )
        return SupportType.TOWER, reasons

    # Rule 4: Ribbed slab ≥ 25cm
    if slab_type == "ribbed" and slab_thickness_m > 0.25:
        reasons.append(
            f"Laje nervurada h={slab_thickness_m*100:.0f}cm "
            f"(peso de forma requer torre)"
        )
        return SupportType.TOWER, reasons

    # Default: telescopic shore (ESC310 or ESC450 by height)
    reasons.append(
        f"Escora telescópica adequada "
        f"(h={required_height_m:.1f}m, laje {slab_thickness_m*100:.0f}cm)"
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
