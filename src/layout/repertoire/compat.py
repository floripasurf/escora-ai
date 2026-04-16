"""Compatibilidade: converte TemplateV2 (zonas) → template dict legado.

O solver.py espera um dict com rooms em coordenadas relativas (0-1)
dentro de um bounding box retangular. Esta camada converte as coordenadas
zone-relative para bounding-box-relative.
"""

import logging
from typing import Dict, Any

from ._base import TemplateV2

logger = logging.getLogger(__name__)


def to_legacy_template(template: TemplateV2) -> Dict[str, Any]:
    """Converte TemplateV2 → dict compatível com solver._scale_rooms().

    Flattening:
    1. Calcula bounding box de todas as zonas (incluindo outdoor)
    2. Cada room: zone-relative → bounding-box-relative
    3. Retorna dict no formato legado
    """
    bb = template.bounding_box  # (x0, y0, x1, y1)
    bb_w = bb[2] - bb[0]
    bb_h = bb[3] - bb[1]

    if bb_w <= 0 or bb_h <= 0:
        raise ValueError(f"Template {template.id} has invalid bounding box: {bb}")

    rooms = []
    for room in template.rooms:
        zone = template.get_zone(room.zone_id)
        if zone is None:
            logger.warning(f"Room {room.name} references unknown zone {room.zone_id}")
            continue

        # Room absolute position = zone anchor + (room rel * zone size)
        abs_x = zone.anchor_x + room.rel_x * zone.width_m
        abs_y = zone.anchor_y + room.rel_y * zone.depth_m
        abs_w = room.rel_w * zone.width_m
        abs_h = room.rel_h * zone.depth_m

        # Convert to bounding-box-relative (0-1)
        rel_x = (abs_x - bb[0]) / bb_w
        rel_y = (abs_y - bb[1]) / bb_h
        rel_w = abs_w / bb_w
        rel_h = abs_h / bb_h

        rooms.append({
            "name": room.name,
            "type": room.type,
            "rel_x": round(rel_x, 4),
            "rel_y": round(rel_y, 4),
            "rel_w": round(rel_w, 4),
            "rel_h": round(rel_h, 4),
            "is_wet": room.is_wet,
        })

    # Metadata
    area_range = template.target_area_range
    mid_area = (area_range[0] + area_range[1]) / 2

    # Lot placement as dict
    lp = template.lot_placement
    lot_placement = {
        "street_facing_zone": lp.street_facing_zone,
        "setback_front_m": lp.setback_front_m,
        "setback_back_m": lp.setback_back_m,
        "setback_side_m": lp.setback_side_m,
        "building_coverage_max": lp.building_coverage_max,
        "garden_side": lp.garden_side,
        "driveway_side": lp.driveway_side,
    }

    return {
        "id": template.id,
        "description": template.name,
        "target_area_m2": mid_area,
        "bedrooms": template.bedrooms,
        "min_width_m": round(bb_w, 2),
        "preferred_width_m": round(bb_w, 2),
        "preferred_depth_m": round(bb_h, 2),
        "rooms": rooms,
        "entrance": {"wall": "south", "position": 0.40},
        "wet_cluster": "east",
        "preferred_entrance_side": "south",
        "bedroom_zone": "north",
        "typology": template.typology,
        "lot_placement": lot_placement,
        "tags": template.tags,
        # Zone metadata for rendering
        "zones": [
            {
                "id": z.id,
                "anchor_x": z.anchor_x,
                "anchor_y": z.anchor_y,
                "width_m": z.width_m,
                "depth_m": z.depth_m,
                "is_outdoor": z.is_outdoor,
            }
            for z in template.zones
        ],
    }
