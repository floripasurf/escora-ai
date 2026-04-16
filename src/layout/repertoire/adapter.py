"""Adapta template ao input do usuário — escala zonas e rooms.

Pipeline:
1. Area scaling — escala zonas proporcionalmente ao target
2. Lot fitting — ajusta ao lote real (recuos, largura disponível)
3. Room scaling — recalcula rooms dentro das zonas adaptadas
"""

import logging
import copy
from typing import Dict, Any, Optional

from ._base import TemplateV2, Zone

logger = logging.getLogger(__name__)


def adapt_template(
    template: TemplateV2,
    target_area_m2: float,
    lot_width_m: Optional[float] = None,
    lot_depth_m: Optional[float] = None,
) -> TemplateV2:
    """Adapta um template ao target de área e dimensões do lote.

    Retorna uma cópia do template com zonas redimensionadas.
    Não modifica o template original.
    """
    t = copy.deepcopy(template)

    # 1. Escala para target area
    t = _scale_to_area(t, target_area_m2)

    # 2. Ajusta ao lote (se informado)
    if lot_width_m is not None and lot_depth_m is not None:
        t = _fit_to_lot(t, lot_width_m, lot_depth_m)

    return t


def _scale_to_area(t: TemplateV2, target_area: float) -> TemplateV2:
    """Escala zonas indoor proporcionalmente para atingir target area."""
    current_area = t.built_area_m2
    if current_area <= 0:
        return t

    ratio = target_area / current_area
    if abs(ratio - 1.0) < 0.02:
        return t  # close enough

    # Scale factor per axis: sqrt for uniform scaling
    scale = ratio ** 0.5

    # Clamp scaling to avoid extreme distortion
    scale = max(0.75, min(scale, 1.35))

    for zone in t.zones:
        if zone.scalable_axis == "fixed":
            continue

        if zone.scalable_axis in ("width", "both"):
            zone.anchor_x *= scale
            zone.width_m *= scale
        if zone.scalable_axis in ("depth", "both"):
            zone.anchor_y *= scale
            zone.depth_m *= scale

    # Scale outdoor zones to match new building width
    indoor_zones = [z for z in t.zones if not z.is_outdoor]
    if indoor_zones:
        new_width = max(z.anchor_x + z.width_m for z in indoor_zones) - min(z.anchor_x for z in indoor_zones)
        for zone in t.zones:
            if zone.is_outdoor and zone.scalable_axis != "fixed":
                zone.width_m = min(zone.width_m * scale, new_width)

    return t


def _fit_to_lot(
    t: TemplateV2,
    lot_width: float,
    lot_depth: float,
) -> TemplateV2:
    """Ajusta template para caber no lote com recuos."""
    lp = t.lot_placement
    avail_width = lot_width - 2 * lp.setback_side_m
    avail_depth = lot_depth - lp.setback_front_m - lp.setback_back_m

    if avail_width <= 0 or avail_depth <= 0:
        logger.warning(f"Lot too small for setbacks: {lot_width}x{lot_depth}m")
        return t

    # Max built area from coverage
    max_built = lot_width * lot_depth * lp.building_coverage_max

    bb = t.bounding_box
    bb_w = bb[2] - bb[0]
    bb_h = bb[3] - bb[1]

    # Calculate scale factors to fit
    scale_w = min(avail_width / bb_w, 1.0) if bb_w > avail_width else 1.0
    scale_d = min(avail_depth / bb_h, 1.0) if bb_h > avail_depth else 1.0

    # Also check coverage
    if t.built_area_m2 > max_built:
        coverage_scale = (max_built / t.built_area_m2) ** 0.5
        scale_w = min(scale_w, coverage_scale)
        scale_d = min(scale_d, coverage_scale)

    if scale_w >= 0.99 and scale_d >= 0.99:
        return t  # fits already

    logger.info(
        f"Fitting to lot: scale_w={scale_w:.2f}, scale_d={scale_d:.2f}"
    )

    for zone in t.zones:
        if zone.scalable_axis == "fixed":
            continue

        if zone.scalable_axis in ("width", "both"):
            zone.anchor_x *= scale_w
            zone.width_m *= scale_w
        if zone.scalable_axis in ("depth", "both"):
            zone.anchor_y *= scale_d
            zone.depth_m *= scale_d

    return t
