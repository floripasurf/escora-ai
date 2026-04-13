"""Shape grammar — geração procedural de plantas baseada em fluxo de circulação.

Princípios extraídos de plantas residenciais reais:

REGRAS FUNDAMENTAIS:
1. Cada quarto tem acesso INDEPENDENTE à área social (nunca por outro quarto)
2. Cada quarto tem acesso fácil a um banheiro (via corredor)
3. Circulação = faixa fina de LARGURA TOTAL entre zona social e íntima
4. Banheiro e serviço ficam na zona íntima (junto aos quartos)
5. Porta de entrada na sala, voltada para a rua
6. Corredor tem o MÍNIMO de área possível (não é área útil)

MODELO DE LAYOUT (rua embaixo):

  +--------+------+--------+------+
  |Quarto 1|Banh. |Quarto 2|Serv. |   ← zona íntima (quartos + wet)
  +--------+------+--------+------+
  |        Corredor (hall)         |   ← faixa fina, LARGURA TOTAL
  +--------------------------------+
  |                                |
  |        Sala/Cozinha            |   ← zona social (frente/rua)
  +--------------------------------+

- O corredor é uma faixa contínua de largura total → TODOS os quartos,
  banheiro e serviço são adjacentes a ele → acesso garantido.
- Banheiro fica ENTRE os quartos na zona íntima → próximo de todos.
- Serviço fica no canto da zona íntima → cluster molhado com banheiro.
- Corredor mínimo: ~0.90m de profundidade real (NBR 15575).
"""

import logging
from typing import Dict, List, Any, Tuple

from src.utils.masonry_constants import (
    MIN_ROOM_AREAS, MIN_ROOM_DIMENSION, MAX_ROOM_AREAS,
    MAX_ASPECT_RATIO, TARGET_AREA_RATIO,
)

logger = logging.getLogger(__name__)


def generate_layout(
    bedrooms: int,
    target_area_m2: float,
    layout_type: str = "open_kitchen",
    has_garage: bool = False,
    bathrooms: int = 1,
) -> Dict[str, Any]:
    """Gera layout com corredor full-width e circulação correta.

    Returns:
        Template-compatible dict para o solver.
    """
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

    # ==================================================================
    # 1. PROPORÇÕES DAS 3 FAIXAS (Y relativo 0→1, rua = 0)
    # ==================================================================
    # Corredor: faixa fina, MÍNIMA. ~0.90-1.20m real.
    # Em edifício de 8-10m: 0.10 relativo ≈ 0.80-1.00m.
    # Toda área poupada no corredor vai para quartos e sala.

    # Corredor: faixa ultra-fina. Profundidade real mín ~0.90m (NBR 15575).
    # Usamos valor fixo ANTES de normalizar, para que não cresça com o edifício.
    # Depois de normalizar, o solver snappa ao módulo (mín 0.90m real).
    corridor_h = 0.08  # será ~0.90m em edifício de 10m, ~0.65m em 8m (snap to 0.75)

    if bedrooms == 1:
        social_h = 0.50
        intimate_h = 0.42
    elif bedrooms == 2:
        social_h = 0.42
        intimate_h = 0.50
    else:
        social_h = 0.38
        intimate_h = 0.54

    if layout_type == "separate_kitchen":
        social_h -= 0.03
        intimate_h += 0.03

    # Normalizar (social + corridor + intimate = 1.0)
    total = social_h + corridor_h + intimate_h
    social_h /= total
    corridor_h /= total
    intimate_h /= total

    # Y bounds
    y_social = (0.0, social_h)
    y_corr = (social_h, social_h + corridor_h)
    y_intim = (social_h + corridor_h, 1.0)

    rooms = []

    # ==================================================================
    # 2. FAIXA SOCIAL (frente/rua)
    # ==================================================================
    if has_garage:
        garage_w = 0.40  # ~3.0m em edifício de 7.5m (mín NBR garage = 3.0m)
        if layout_type == "separate_kitchen":
            rooms.append(_r("Sala", "living", 0.0, y_social[0],
                            1.0 - garage_w, social_h))
        else:
            rooms.append(_r("Sala/Cozinha", "living", 0.0, y_social[0],
                            1.0 - garage_w, social_h))
        rooms.append(_r("Garagem", "garage", 1.0 - garage_w, y_social[0],
                        garage_w, social_h))
    else:
        name = "Sala" if layout_type == "separate_kitchen" else "Sala/Cozinha"
        rooms.append(_r(name, "living", 0.0, y_social[0], 1.0, social_h))

    # ==================================================================
    # 3. FAIXA CORREDOR — largura total, um único cômodo
    # ==================================================================
    rooms.append(_r("Circulação", "circulation",
                    0.0, y_corr[0], 1.0, corridor_h))

    # ==================================================================
    # 4. FAIXA ÍNTIMA — quartos + wet core
    # ==================================================================
    # Layout: [Quarto1] [Quarto2] ... [Wet Core]
    #
    # Quartos ficam lado a lado, cada um com a LARGURA TOTAL da faixa íntima.
    # Áreas molhadas (banheiro, serviço, cozinha) ficam empilhadas
    # verticalmente em uma única coluna ("wet core") à direita.
    #
    # Isso garante que quartos tenham largura suficiente (>2.4m)
    # mesmo quando há muitos cômodos molhados.
    #
    # +--------+--------+------+
    # |        |        |Banh.1|
    # |Quarto 1|Quarto 2|------|  ← wet core (empilhado vertical)
    # |        |        |Serv. |
    # +--------+--------+------+

    # Montar listas separadas
    bedroom_items = []
    wet_items = []

    for i in range(bedrooms):
        label = f"Quarto {i + 1}" if bedrooms > 1 else "Quarto"
        bedroom_items.append({"name": label, "type": "bedroom"})

    for i in range(bathrooms):
        label = f"Banheiro {i + 1}" if bathrooms > 1 else "Banheiro"
        wet_items.append({"name": label, "type": "bathroom",
                          "is_wet": True, "min_area": 2.4})

    wet_items.append({"name": "Serviço", "type": "service",
                      "is_wet": True, "min_area": 2.5})

    if layout_type == "separate_kitchen":
        wet_items.append({"name": "Cozinha", "type": "kitchen",
                          "is_wet": True, "min_area": 4.0})

    # Wet core width: proporcional ao que as áreas molhadas precisam.
    # Em casas reais, o bloco molhado ocupa ~25-35% da largura.
    # Cálculo: soma_áreas_wet / (intimate_h_real * building_depth)
    # Aproximação: cada wet item precisa de ~2.5-4m² → coluna ~1.5-2.0m
    # Em termos relativos: 0.22 para 1-2 wet, 0.28 para 3+, 0.32 para 4+
    n_wet = len(wet_items)
    if n_wet <= 2:
        wet_core_w = 0.22
    elif n_wet <= 3:
        wet_core_w = 0.28
    else:
        wet_core_w = 0.32

    # Quartos dividem o espaço restante igualmente
    bedroom_zone_w = 1.0 - wet_core_w
    n_bed = len(bedroom_items)
    bed_w = bedroom_zone_w / n_bed if n_bed > 0 else bedroom_zone_w

    # Colocar quartos
    x = 0.0
    for i, bed in enumerate(bedroom_items):
        if i == n_bed - 1:
            w = round(bedroom_zone_w - x, 4)
        else:
            w = round(bed_w, 4)
        rooms.append(_r(bed["name"], "bedroom",
                        x, y_intim[0], w, intimate_h))
        x = round(x + w, 4)

    # Colocar wet core — itens empilhados verticalmente na coluna direita
    wet_x = round(1.0 - wet_core_w, 4)
    wet_total_w = wet_core_w

    # Distribuir altura proporcional à área mínima de cada wet item
    total_min = sum(it["min_area"] for it in wet_items)
    wet_y = y_intim[0]
    for i, wit in enumerate(wet_items):
        frac = wit["min_area"] / total_min
        if i == len(wet_items) - 1:
            h = round(y_intim[0] + intimate_h - wet_y, 4)
        else:
            h = round(intimate_h * frac, 4)
        rooms.append(_r(wit["name"], wit["type"],
                        wet_x, wet_y, wet_total_w, h,
                        is_wet=True))
        wet_y = round(wet_y + h, 4)

    # ==================================================================
    # 5. Validações
    # ==================================================================
    _validate(rooms, y_corr, y_intim)

    # ==================================================================
    # 6. Montar template
    # ==================================================================
    garage_tag = "_gar" if has_garage else ""
    kitchen_tag = "sep" if layout_type == "separate_kitchen" else "int"
    tid = f"grammar_{bedrooms}q_{int(target_area_m2)}m2_{kitchen_tag}{garage_tag}"

    template = {
        "id": tid,
        "description": f"{bedrooms} quartos, ~{target_area_m2:.0f}m² (generated)",
        "target_area_m2": target_area_m2,
        "bedrooms": bedrooms,
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
                f"corridor {corridor_h:.0%} depth")
    return template


# ==================================================================
# HELPERS
# ==================================================================

def _r(name, rtype, x, y, w, h, is_wet=False):
    return {"name": name, "type": rtype,
            "rel_x": round(x, 4), "rel_y": round(y, 4),
            "rel_w": round(w, 4), "rel_h": round(h, 4),
            "is_wet": is_wet}


def _validate(rooms, y_corr, y_intim):
    """Valida topologia de circulação."""
    corr_top = round(y_corr[1], 3)
    corr_bot = round(y_corr[0], 3)

    bedrooms = [r for r in rooms if r["type"] == "bedroom"]
    baths = [r for r in rooms if r["type"] == "bathroom"]

    # Todos os quartos devem estar na faixa íntima (acima do corredor)
    for b in bedrooms:
        b_bot = round(b["rel_y"], 3)
        if abs(b_bot - corr_top) > 0.02:
            logger.warning(f"{b['name']} não adjacente ao corredor "
                           f"(y={b_bot}, corredor top={corr_top})")

    # Banheiros devem estar na faixa íntima (acima do corredor)
    for b in baths:
        b_bot = round(b["rel_y"], 3)
        if abs(b_bot - corr_top) > 0.02:
            logger.warning(f"{b['name']} não adjacente ao corredor")

    # Corredor deve ser full-width
    corr = [r for r in rooms if r["type"] == "circulation"]
    for c in corr:
        if c["rel_w"] < 0.95:
            logger.warning(f"Corredor width {c['rel_w']:.2f} < full width")

    # Checar bounds
    for r in rooms:
        end_x = r["rel_x"] + r["rel_w"]
        end_y = r["rel_y"] + r["rel_h"]
        if end_x > 1.01 or end_y > 1.01:
            logger.warning(f"{r['name']} fora dos limites: "
                           f"x={r['rel_x']:.2f}+{r['rel_w']:.2f}={end_x:.2f}, "
                           f"y={r['rel_y']:.2f}+{r['rel_h']:.2f}={end_y:.2f}")
