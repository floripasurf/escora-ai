"""Shape grammar — geração procedural de plantas baseada em fluxo de circulação.

REGRAS FUNDAMENTAIS:
1. Cada quarto tem acesso INDEPENDENTE à área social (nunca por outro quarto)
2. Cada quarto tem acesso fácil a um banheiro (via corredor)
3. Circulação = faixa fina de LARGURA TOTAL entre zona social e íntima
4. Banheiro e serviço ficam na zona íntima (junto aos quartos)
5. Porta de entrada na sala, voltada para a rua
6. Corredor tem o MÍNIMO de área possível (não é área útil)

MODELO DE LAYOUT (rua embaixo):

  +--------+--------+------+
  |        |        |Banh. |
  |Quarto 1|Quarto 2|------|  ← zona íntima
  |        |        |Serv. |
  +--------+--------+------+
  |     Corredor (hall)    |  ← faixa fina, LARGURA TOTAL
  +------------------------+
  |                        |
  |     Sala/Cozinha       |  ← zona social (frente/rua)
  +------------------------+

Com cozinha separada:
  +------+------+-----+------+
  |      |      |     |Banh. |
  | Q1   | Q2   | Coz |------|
  |      |      |     |Serv. |
  +------+------+-----+------+
  |      Corredor (hall)      |
  +---------------------------+
  |        Sala               |
  +---------------------------+

Wet core: banheiro(s) + serviço empilhados verticalmente.
Cozinha separada: coluna própria (não empilhada no wet core).
"""

import logging
from typing import Dict, Any


logger = logging.getLogger(__name__)

# NBR 15575 — minimum absolute dimensions (meters)
_MIN_DIM = {
    "bedroom": 2.40, "living": 2.40, "kitchen": 1.80,
    "bathroom": 1.50, "service": 1.50, "circulation": 0.90,
    "garage": 3.00,
}
_MIN_AREA = {
    "bedroom": 8.0, "living": 12.0, "kitchen": 4.0,
    "bathroom": 2.4, "service": 2.5, "circulation": 1.5,
    "garage": 12.0,
}
_CORRIDOR_M = 0.90


def generate_layout(
    bedrooms: int,
    target_area_m2: float,
    layout_type: str = "open_kitchen",
    has_garage: bool = False,
    bathrooms: int = 1,
) -> Dict[str, Any]:
    """Gera layout com corredor full-width e circulação correta."""
    try:
        return _generate(bedrooms, target_area_m2, layout_type, has_garage, bathrooms)
    except Exception as e:
        logger.warning(f"Shape grammar failed: {e}. Falling back to templates.")
        from src.layout.templates import find_best_template
        return find_best_template(bedrooms, target_area_m2, layout_type, has_garage)


def _generate(
    bedrooms: int, target_area_m2: float, layout_type: str,
    has_garage: bool, bathrooms: int,
) -> Dict[str, Any]:

    # Build room lists for intimate zone
    # "columns": full-height rooms (bedrooms, kitchen if separate)
    # "wet_stack": stacked vertically in one column (bathrooms, service)
    columns = []  # list of {"name", "type", "min_w"}
    wet_stack = []

    for i in range(bedrooms):
        label = f"Quarto {i + 1}" if bedrooms > 1 else "Quarto"
        columns.append({"name": label, "type": "bedroom",
                        "min_w": _MIN_DIM["bedroom"]})

    if layout_type == "separate_kitchen":
        columns.append({"name": "Cozinha", "type": "kitchen",
                        "min_w": _MIN_DIM["kitchen"], "is_wet": True})

    for i in range(bathrooms):
        label = f"Banheiro {i + 1}" if bathrooms > 1 else "Banheiro"
        wet_stack.append({"name": label, "type": "bathroom",
                          "is_wet": True, "min_area": _MIN_AREA["bathroom"]})
    wet_stack.append({"name": "Serviço", "type": "service",
                      "is_wet": True, "min_area": _MIN_AREA["service"]})

    # ==================================================================
    # 1. SOLVE DIMENSIONS
    # ==================================================================
    # Princípio: PREFER NARROW (maximize depth → more social area).
    # Edifício estreito = quartos e sala mais profundos = melhores proporções.
    # Só alarga além do min_width quando necessário para caber a garagem.

    wet_w_base = max(_MIN_DIM.get(w["type"], 1.5) for w in wet_stack)

    # For 1Q without separate kitchen: widen wet core so bedroom isn't oversized
    # (1 bedroom takes all remaining width → needs counterbalance)
    if bedrooms == 1 and len(columns) == 1:
        wet_w = max(wet_w_base, 2.0)
    else:
        wet_w = wet_w_base

    wet_heights = [max(_MIN_DIM.get(w["type"], 1.5), w["min_area"] / wet_w)
                   for w in wet_stack]
    total_wet_h = sum(wet_heights)

    # Minimum width: columns at min dimension + wet core
    total_col_min_w = sum(c["min_w"] for c in columns)
    min_width = total_col_min_w + wet_w

    # Garage constraint on min width
    if has_garage:
        min_width = max(min_width, _MIN_DIM["garage"] + _MIN_DIM["living"])
        min_width = max(min_width, _MIN_AREA["garage"] / 4.0 + _MIN_DIM["living"])

    # Target social depth: proportional to area, NOT bare minimum.
    # In real houses, social area (sala/cozinha) is the largest room.
    # Target: ~35% of total area for social zone.
    social_target = max(3.0, min(4.5, target_area_m2 * 0.065))
    social_min = _MIN_DIM["living"]  # absolute minimum 2.4m

    if has_garage:
        # Garage needs min area → constrains social depth
        garage_frac = 0.40
        rest_h = _CORRIDOR_M + total_wet_h
        width_from_garage = (target_area_m2 - _MIN_AREA["garage"] / garage_frac) / rest_h
        width = max(min_width, width_from_garage)

        # Ensure garage is at least 3.0m wide
        if width * garage_frac < _MIN_DIM["garage"]:
            width = target_area_m2 / ((_MIN_AREA["garage"] / _MIN_DIM["garage"]) + rest_h)
            width = max(min_width, width)
            garage_frac = max(0.40, _MIN_DIM["garage"] / width)

        garage_frac = min(garage_frac, 0.48)
        depth = target_area_m2 / width
        garage_w = width * garage_frac
        garage_min_d = _MIN_AREA["garage"] / garage_w
        social_min = max(social_min, garage_min_d)
        social_target = max(social_target, social_min)
    else:
        # No garage: START NARROW → maximize depth → better proportions
        # Use social_target instead of social_min for initial depth calc
        ideal_depth = social_target + _CORRIDOR_M + total_wet_h
        width = max(min_width, target_area_m2 / ideal_depth)
        depth = target_area_m2 / width

    # Check bedroom area constraint
    non_bed_col_w = sum(c["min_w"] for c in columns if c["type"] != "bedroom")
    bed_w = (width - wet_w - non_bed_col_w) / bedrooms
    min_intimate_for_beds = _MIN_AREA["bedroom"] / bed_w if bed_w > 0 else 999.0

    intimate_d = max(total_wet_h, min_intimate_for_beds)
    social_d = depth - _CORRIDOR_M - intimate_d

    # Clamp social to minimum
    if social_d < social_min:
        social_d = social_min
        intimate_d = depth - _CORRIDOR_M - social_d
        if intimate_d < total_wet_h * 0.70:
            logger.warning(f"Tight fit for {bedrooms}Q {target_area_m2}m². "
                           f"Consider larger area.")

    # Redistribute excess intimate area to social for balanced proportions.
    # Rule: social depth should be >= bedroom depth (sala is the main room).
    # If intimate is deeper than needed, transfer excess to social.
    min_intimate = max(total_wet_h, min_intimate_for_beds)
    if intimate_d > min_intimate + 0.2:
        excess = intimate_d - min_intimate
        # Transfer 70% of excess to social (keep 30% for bedroom comfort)
        transfer = excess * 0.70
        social_d += transfer
        intimate_d -= transfer

    # Widen wet core if there's surplus width beyond bedroom minimums
    actual_bed_w = (width - wet_w - non_bed_col_w) / bedrooms
    if actual_bed_w > _MIN_DIM["bedroom"] + 1.0 and wet_w < 2.0:
        # Bedroom has >1m surplus → give some to wet core
        extra = min((actual_bed_w - _MIN_DIM["bedroom"] - 0.5) * bedrooms * 0.3, 0.5)
        if extra > 0:
            wet_w += extra

    # ==================================================================
    # 2. CONVERT TO RELATIVE (0→1) and place rooms
    # ==================================================================
    social_h = social_d / depth
    corridor_h = _CORRIDOR_M / depth
    intimate_h = intimate_d / depth

    rooms = []

    # --- Social zone ---
    if has_garage:
        garage_w_rel = round(min(max(0.40, _MIN_DIM["garage"] / width), 0.48), 4)
        living_name = "Sala" if layout_type == "separate_kitchen" else "Sala/Cozinha"
        rooms.append(_r(living_name, "living", 0.0, 0.0,
                        round(1.0 - garage_w_rel, 4), round(social_h, 4)))
        rooms.append(_r("Garagem", "garage",
                        round(1.0 - garage_w_rel, 4), 0.0,
                        garage_w_rel, round(social_h, 4)))
    else:
        name = "Sala" if layout_type == "separate_kitchen" else "Sala/Cozinha"
        rooms.append(_r(name, "living", 0.0, 0.0, 1.0, round(social_h, 4)))

    # --- Corridor ---
    corr_y = round(social_h, 4)
    rooms.append(_r("Circulação", "circulation",
                    0.0, corr_y, 1.0, round(corridor_h, 4)))

    # --- Intimate zone: columns + wet core ---
    intim_y = round(social_h + corridor_h, 4)
    intim_h_rel = round(intimate_h, 4)
    wet_w_rel = round(wet_w / width, 4)

    # Distribute column widths proportionally to min_w
    col_zone_w = 1.0 - wet_w_rel
    col_total_min = sum(c["min_w"] for c in columns)

    x = 0.0
    for i, col in enumerate(columns):
        frac = col["min_w"] / col_total_min
        if i == len(columns) - 1:
            w = round(col_zone_w - x, 4)
        else:
            w = round(col_zone_w * frac, 4)
        rooms.append(_r(col["name"], col["type"],
                        x, intim_y, w, intim_h_rel,
                        is_wet=col.get("is_wet", False)))
        x = round(x + w, 4)

    # Wet core stacked vertically
    wet_x = round(1.0 - wet_w_rel, 4)
    total_wh = sum(wet_heights)
    wy = intim_y
    for i, wit in enumerate(wet_stack):
        frac = wet_heights[i] / total_wh
        if i == len(wet_stack) - 1:
            h = round(1.0 - wy, 4)
        else:
            h = round(intim_h_rel * frac, 4)
        rooms.append(_r(wit["name"], wit["type"],
                        wet_x, round(wy, 4), wet_w_rel, h, is_wet=True))
        wy += h

    # ==================================================================
    # 3. Validate + template
    # ==================================================================
    _validate(rooms, (corr_y, round(corr_y + corridor_h, 4)))

    garage_tag = "_gar" if has_garage else ""
    kitchen_tag = "sep" if layout_type == "separate_kitchen" else "int"
    tid = f"grammar_{bedrooms}q_{int(target_area_m2)}m2_{kitchen_tag}{garage_tag}"

    template = {
        "id": tid,
        "description": f"{bedrooms} quartos, ~{target_area_m2:.0f}m² (generated)",
        "target_area_m2": target_area_m2,
        "bedrooms": bedrooms,
        "min_width_m": round(min_width, 2),
        "preferred_width_m": round(width, 2),
        "preferred_depth_m": round(depth, 2),
        "rooms": [
            {"name": r["name"], "type": r["type"],
             "rel_x": r["rel_x"], "rel_y": r["rel_y"],
             "rel_w": r["rel_w"], "rel_h": r["rel_h"],
             "is_wet": r.get("is_wet", False)}
            for r in rooms
        ],
        "entrance": {"wall": "south", "position": 0.40},
        "wet_cluster": "east",
        "preferred_entrance_side": "south",
        "bedroom_zone": "north",
    }

    if has_garage:
        template["garage_access"] = {
            "position": "right", "door_faces": "street",
            "needs_driveway": True, "min_maneuver_depth_m": 5.0,
        }

    logger.info(f"Shape grammar: {tid} — {len(rooms)} rooms, "
                f"building {width:.1f}x{depth:.1f}m")
    return template


# ==================================================================
# HELPERS
# ==================================================================

def _r(name, rtype, x, y, w, h, is_wet=False):
    return {"name": name, "type": rtype,
            "rel_x": round(x, 4), "rel_y": round(y, 4),
            "rel_w": round(w, 4), "rel_h": round(h, 4),
            "is_wet": is_wet}


def _validate(rooms, y_corr):
    """Valida topologia de circulação."""
    corr_top = round(y_corr[1], 3)

    for b in [r for r in rooms if r["type"] == "bedroom"]:
        b_bot = round(b["rel_y"], 3)
        if abs(b_bot - corr_top) > 0.02:
            logger.warning(f"{b['name']} não adjacente ao corredor "
                           f"(y={b_bot}, corredor top={corr_top})")

    for c in [r for r in rooms if r["type"] == "circulation"]:
        if c["rel_w"] < 0.95:
            logger.warning(f"Corredor width {c['rel_w']:.2f} < full width")

    for r in rooms:
        end_x = r["rel_x"] + r["rel_w"]
        end_y = r["rel_y"] + r["rel_h"]
        if end_x > 1.01 or end_y > 1.01:
            logger.warning(f"{r['name']} fora dos limites: "
                           f"x={r['rel_x']:.2f}+{r['rel_w']:.2f}={end_x:.2f}, "
                           f"y={r['rel_y']:.2f}+{r['rel_h']:.2f}={end_y:.2f}")
