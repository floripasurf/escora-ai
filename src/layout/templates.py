"""Templates de plantas parametrizadas para MCMV.

Cada template define uma planta pré-validada como dicionário com:
- rooms: lista de cômodos com proporções relativas
- adjacency: grafo de adjacência (quais cômodos compartilham parede)
- wet_cluster: posição preferencial das áreas molhadas
- entrance: posição da porta de entrada

As proporções são normalizadas (0-1) e serão escaladas para o lote real
pelo LayoutSolver.

Referência: Portaria 660/2018 do Ministério das Cidades — Especificações MCMV
"""

from typing import Dict, List, Any


def _room(name: str, type: str, x: float, y: float, w: float, h: float,
           is_wet: bool = False) -> dict:
    """Helper para definir um cômodo com proporções relativas (0-1)."""
    return {
        "name": name,
        "type": type,
        "rel_x": x,
        "rel_y": y,
        "rel_w": w,
        "rel_h": h,
        "is_wet": is_wet,
    }


# ============================================================================
# MCMV 1 QUARTO — ~40m²
# ============================================================================

MCMV_1Q_40M2: Dict[str, Any] = {
    "id": "mcmv_1q_40m2",
    "description": "1 quarto, sala/cozinha integrada, ~40m²",
    "target_area_m2": 40.0,
    "bedrooms": 1,
    # Layout: sala frontal, quarto+banheiro no fundo
    # Corredor conecta sala ao quarto, banheiro adjacente ao quarto
    #
    #   Y=1.0 +------------+------+---------+
    #         |   Quarto   |Banh. | Serviço |
    #   Y=0.55+------------+------+---------+
    #         |            |  Circulação    |
    #   Y=0.45+            +----------------+
    #         |                             |
    #         |       Sala/Cozinha          |
    #   Y=0.0 +-----------------------------+
    #        X=0         X=0.55  X=0.75   X=1.0
    "rooms": [
        _room("Sala/Cozinha", "living", 0.0, 0.0, 1.0, 0.45),
        _room("Circulação", "circulation", 0.55, 0.45, 0.45, 0.10),
        _room("Quarto", "bedroom", 0.0, 0.45, 0.55, 0.55),
        _room("Banheiro", "bathroom", 0.55, 0.55, 0.20, 0.45, is_wet=True),
        _room("Serviço", "service", 0.75, 0.55, 0.25, 0.45, is_wet=True),
    ],
    "entrance": {"wall": "south", "position": 0.40},
    "wet_cluster": "northeast",
    "preferred_entrance_side": "south",
    "bedroom_zone": "north",
}


# ============================================================================
# MCMV 2 QUARTOS — ~50m² (cozinha integrada)
# ============================================================================

MCMV_2Q_50M2: Dict[str, Any] = {
    "id": "mcmv_2q_50m2",
    "description": "2 quartos, sala/cozinha integrada, ~50m²",
    "target_area_m2": 50.0,
    "bedrooms": 2,
    # Grid X: 0 | 0.55 | 1.0       (2 colunas)
    # Grid Y: 0 | 0.40 | 0.70 | 1.0 (3 faixas)
    #
    #   Y=1.0 +---------------+----------+
    #         |   Quarto 2    | Serviço  |
    #   Y=0.70+---------------+----------+
    #         |   Quarto 1    |Banh|Circ.|
    #   Y=0.40+---------------+----+-----+
    #         |                          |
    #         |      Sala/Cozinha        |
    #   Y=0.0 +--------------------------+
    #        X=0           X=0.55 X=0.75 X=1.0
    "rooms": [
        _room("Sala/Cozinha", "living", 0.0, 0.0, 1.0, 0.40),
        _room("Quarto 1", "bedroom", 0.0, 0.40, 0.55, 0.30),
        _room("Banheiro", "bathroom", 0.55, 0.40, 0.20, 0.30, is_wet=True),
        _room("Circulação", "circulation", 0.75, 0.40, 0.25, 0.30),
        _room("Quarto 2", "bedroom", 0.0, 0.70, 0.55, 0.30),
        _room("Serviço", "service", 0.55, 0.70, 0.45, 0.30, is_wet=True),
    ],
    "entrance": {"wall": "south", "position": 0.40},
    "wet_cluster": "east",
    "preferred_entrance_side": "south",
    "bedroom_zone": "north",
}


# ============================================================================
# MCMV 2 QUARTOS — ~55m² (cozinha separada)
# ============================================================================

MCMV_2Q_55M2: Dict[str, Any] = {
    "id": "mcmv_2q_55m2",
    "description": "2 quartos, cozinha separada, ~55m²",
    "target_area_m2": 55.0,
    "bedrooms": 2,
    # Layout: sala frontal, cozinha+servico no nucleo, quartos no fundo
    # Corredor central conecta sala → cozinha → quartos
    # Banheiro adjacente aos quartos (zona intima)
    #
    #   Y=1.0 +-----------+------+-----------+
    #         |  Quarto 2 |Serv. | Quarto 1  |
    #   Y=0.60+-----------+------+-----------+
    #         |  Cozinha   |Circ |  Banheiro |
    #   Y=0.40+-----------+-----+-----------+
    #         |                              |
    #         |           Sala               |
    #   Y=0.0 +------------------------------+
    #        X=0        X=0.45 X=0.60      X=1.0
    "rooms": [
        _room("Sala", "living", 0.0, 0.0, 1.0, 0.40),
        _room("Cozinha", "kitchen", 0.0, 0.40, 0.45, 0.20, is_wet=True),
        _room("Circulação", "circulation", 0.45, 0.40, 0.15, 0.20),
        _room("Banheiro", "bathroom", 0.60, 0.40, 0.40, 0.20, is_wet=True),
        _room("Quarto 2", "bedroom", 0.0, 0.60, 0.45, 0.40),
        _room("Serviço", "service", 0.45, 0.60, 0.15, 0.40, is_wet=True),
        _room("Quarto 1", "bedroom", 0.60, 0.60, 0.40, 0.40),
    ],
    "entrance": {"wall": "south", "position": 0.40},
    "wet_cluster": "center",
    "preferred_entrance_side": "south",
    "bedroom_zone": "north",
}


# ============================================================================
# MCMV 3 QUARTOS — ~65m²
# ============================================================================

MCMV_3Q_65M2: Dict[str, Any] = {
    "id": "mcmv_3q_65m2",
    "description": "3 quartos, sala/cozinha integrada, ~65m²",
    "target_area_m2": 65.0,
    "bedrooms": 3,
    # Layout grid (aligned edges):
    #   Y=1.0 +--------+----------+---------+
    #         |Serviço |Circulaç. | Quarto 3|
    #   Y=0.75+--------+----------+---------+
    #         |        |          |         |
    #         |Cozinha | Banheiro | Quarto 2|
    #   Y=0.50+--------+----------+---------+
    #         |                   |         |
    #         |   Sala/Cozinha    |Quarto 1 |
    #   Y=0.0 +-------------------+---------+
    #        X=0     X=0.30    X=0.50     X=1.0
    "rooms": [
        _room("Sala/Cozinha", "living", 0.0, 0.0, 0.50, 0.50),
        _room("Quarto 1", "bedroom", 0.50, 0.0, 0.50, 0.50),
        _room("Cozinha", "kitchen", 0.0, 0.50, 0.30, 0.25, is_wet=True),
        _room("Banheiro", "bathroom", 0.30, 0.50, 0.20, 0.25, is_wet=True),
        _room("Quarto 2", "bedroom", 0.50, 0.50, 0.50, 0.25),
        _room("Serviço", "service", 0.0, 0.75, 0.30, 0.25, is_wet=True),
        _room("Circulação", "circulation", 0.30, 0.75, 0.20, 0.25),
        _room("Quarto 3", "bedroom", 0.50, 0.75, 0.50, 0.25),
    ],
    "entrance": {"wall": "south", "position": 0.20},
    "wet_cluster": "center",
    "preferred_entrance_side": "south",
    "bedroom_zone": "east",
}


# ============================================================================
# MCMV 3 QUARTOS — ~70m² + garagem
# ============================================================================

MCMV_3Q_70M2: Dict[str, Any] = {
    "id": "mcmv_3q_70m2",
    "description": "3 quartos, cozinha integrada, garagem, ~70m²",
    "target_area_m2": 70.0,
    "bedrooms": 3,
    # Layout grid (aligned edges):
    #   Y=1.0 +---------+---------+---------+
    #         | Serviço |Circulaç.| Quarto 3|
    #   Y=0.75+---------+---------+---------+
    #         |         |         |         |
    #         | Cozinha |Banheiro | Quarto 2|
    #   Y=0.50+---------+---------+---------+
    #         |         |                   |
    #         |Garagem  |   Sala/Cozinha    |
    #         |         |                   |
    #   Y=0.25+---------+         +---------+
    #         |         |         | Quarto 1|
    #   Y=0.0 +---------+---------+---------+
    #        X=0      X=0.25   X=0.55     X=1.0
    "rooms": [
        _room("Garagem", "garage", 0.0, 0.0, 0.25, 0.50),
        _room("Sala/Cozinha", "living", 0.25, 0.0, 0.30, 0.50),
        _room("Quarto 1", "bedroom", 0.55, 0.0, 0.45, 0.50),
        _room("Cozinha", "kitchen", 0.0, 0.50, 0.25, 0.25, is_wet=True),
        _room("Banheiro", "bathroom", 0.25, 0.50, 0.30, 0.25, is_wet=True),
        _room("Quarto 2", "bedroom", 0.55, 0.50, 0.45, 0.25),
        _room("Serviço", "service", 0.0, 0.75, 0.25, 0.25, is_wet=True),
        _room("Circulação", "circulation", 0.25, 0.75, 0.30, 0.25),
        _room("Quarto 3", "bedroom", 0.55, 0.75, 0.45, 0.25),
    ],
    "entrance": {"wall": "south", "position": 0.40},
    "wet_cluster": "center",
    "preferred_entrance_side": "south",
    "bedroom_zone": "east",
    # Vehicle access: garage opens toward the street side
    # The garage door is on the street-facing wall of the garage room
    "garage_access": {
        "position": "left",           # garage is on the left side of the building
        "door_faces": "street",       # door always faces the street
        "needs_driveway": True,       # driveway from street to garage door
        "min_maneuver_depth_m": 5.0,  # space in front of garage for car turning
    },
}


# ============================================================================
# TEMPLATE REGISTRY
# ============================================================================

ALL_TEMPLATES: List[Dict[str, Any]] = [
    MCMV_1Q_40M2,
    MCMV_2Q_50M2,
    MCMV_2Q_55M2,
    MCMV_3Q_65M2,
    MCMV_3Q_70M2,
]


def find_best_template(bedrooms: int, target_area_m2: float,
                        layout_type: str = "open_kitchen",
                        has_garage: bool = False) -> Dict[str, Any]:
    """Seleciona o template mais adequado para os parâmetros de entrada.

    Prioridade:
    1. Número de quartos (exato)
    2. Área mais próxima do alvo
    3. Garagem se solicitada
    """
    candidates = [t for t in ALL_TEMPLATES if t["bedrooms"] == bedrooms]

    if not candidates:
        # Fallback: template mais próximo em número de quartos
        candidates = sorted(ALL_TEMPLATES, key=lambda t: abs(t["bedrooms"] - bedrooms))
        candidates = [t for t in candidates if t["bedrooms"] == candidates[0]["bedrooms"]]

    # Prefer template with garage if requested
    if has_garage:
        with_garage = [t for t in candidates
                       if any(r["type"] == "garage" for r in t["rooms"])]
        if with_garage:
            candidates = with_garage

    # Sort by area proximity
    candidates.sort(key=lambda t: abs(t["target_area_m2"] - target_area_m2))

    return candidates[0]
