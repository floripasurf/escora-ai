"""Catálogo de 2 quartos — 6 templates arquitetônicos.

Cada template representa uma solução espacial comprovada para habitação
popular brasileira (MCMV, 45-65m²). Circulação validada: todo cômodo
acessível sem passar por quarto.

Convenção de coordenadas:
- Y=0 = frente (rua), Y cresce para os fundos
- X=0 = esquerda olhando de frente

Regra de dimensionamento mínimo:
- bedroom: >= 9.0m², ambos os lados >= 3.0m
- living:  >= 12.0m², lado menor >= 2.4m
- bathroom: >= 2.25m², lado menor >= 1.2m
- service: >= 2.5m², lado menor >= 1.5m
- garage:  >= 12.0m², lado menor >= 3.0m
- circulation: lado menor >= 0.9m

Princípio arquitetônico: Serviço (lavanderia) pertence à zona social,
adjacente à cozinha com acesso ao exterior — NUNCA na zona íntima.
"""

from ._base import TemplateV2, Zone, RoomDef, CirculationGraph, LotPlacement


def _templates() -> list:
    return [
        _2q_rect_compact(),
        _2q_rect_sep(),
        _2q_l_quartos(),
        _2q_varanda_frontal(),
        _2q_gar_lateral(),
        _2q_patio_servico(),
    ]


# =====================================================================
# 1. Retangular compacto — cozinha integrada
# =====================================================================
#
#   +----------+----------+---------+
#   |          |          |         |
#   | Q1       | Q2       | Ban.    |  ← zona íntima (7.8m × 3.6m)
#   | 3.0×3.6  | 3.0×3.6  | 1.8×3.6|
#   |          |          |         |
#   +----------+----------+---------+
#   |       Corredor (7.8m×0.9m)    |
#   +-----------------------------+-+
#   |                             |S|
#   |     Sala/Cozinha            |e|  ← zona social (7.8m × 3.6m)
#   |     6.0×3.6                 |r|     Serviço no canto dos fundos
#   |                             |v|     1.8×1.8
#   +-----------------------------+-+
#            RUA
#
def _2q_rect_compact():
    # intimate width = Q1(3.0) + Q2(3.0) + Ban(1.8) = 7.8m
    # Banheiro agora ocupa altura total na zona íntima (sem Serviço)
    # Serviço movido para canto da zona social
    return TemplateV2(
        id="2q_rect_compact",
        name="2Q Retangular Compacto",
        typology="rectangle",
        target_area_range=(45, 60),
        bedrooms=2,
        bathrooms=1,
        tags=["mcmv", "compacto", "cozinha_integrada"],
        zones=[
            Zone("social", 0, 0, 7.8, 3.6, "both"),
            Zone("corridor", 0, 3.6, 7.8, 0.90, "width", False),
            Zone("intimate", 0, 4.5, 7.8, 3.6, "both"),
        ],
        rooms=[
            # --- zona social ---
            # Sala/Cozinha: 0.77×7.8=6.006 × 3.6 = 21.6m²  ✓ (>= 12m², min side 3.6 >= 2.4)
            RoomDef("Sala/Cozinha", "living", "social",
                    0.0, 0.0, 0.77, 1.0),
            # Serviço: 0.23×7.8=1.794 × 0.50×3.6=1.8 = 3.23m²  ✓ (>= 2.5m², min side 1.794 >= 1.5)
            RoomDef("Serviço", "service", "social",
                    0.77, 0.50, 0.23, 0.50, is_wet=True),
            # --- corredor ---
            # Corredor: 7.8×0.9 = 7.02m²  ✓ (min side 0.9 >= 0.9)
            RoomDef("Circulação", "circulation", "corridor",
                    0.0, 0.0, 1.0, 1.0),
            # --- zona íntima ---
            # intimate 7.8m: Q1=3.0(0.3846), Q2=3.0(0.3846), Ban=1.8(0.2308)
            # Q1: 3.0×3.6 = 10.8m²  ✓ (>= 9m², both sides >= 3.0)
            RoomDef("Quarto 1", "bedroom", "intimate",
                    0.0, 0.0, 0.3846, 1.0),
            # Q2: 3.0×3.6 = 10.8m²  ✓ (>= 9m², both sides >= 3.0)
            RoomDef("Quarto 2", "bedroom", "intimate",
                    0.3846, 0.0, 0.3846, 1.0),
            # Ban: 1.8×3.6 = 6.48m²  ✓ (>= 2.25m², min side 1.8 >= 1.2)
            RoomDef("Banheiro", "bathroom", "intimate",
                    0.7692, 0.0, 0.2308, 1.0, is_wet=True),
        ],
        circulation=CirculationGraph(
            entrance="Sala/Cozinha",
            edges={
                "Sala/Cozinha": ["Circulação", "Serviço"],
                "Circulação": ["Quarto 1", "Quarto 2", "Banheiro"],
                "Quarto 1": [],
                "Quarto 2": [],
                "Banheiro": [],
                "Serviço": [],
            },
        ),
        lot_placement=LotPlacement(
            street_facing_zone="social",
            setback_front_m=3.0,
            setback_back_m=2.0,
            setback_side_m=1.5,
            building_coverage_max=0.60,
        ),
        privacy_gradient=["Sala/Cozinha", "Circulação", "Quarto 1", "Quarto 2"],
    )


# =====================================================================
# 2. Retangular com cozinha separada
# =====================================================================
#
#   +--------+--------+-----------+
#   |        |        |           |
#   | Q1     | Q2     | Ban.      |  ← zona íntima (7.5m × 3.3m)
#   | 3.0×3.3| 3.0×3.3| 1.5×3.3  |
#   |        |        |           |
#   +--------+--------+-----------+
#   |       Corredor (7.5×0.9)    |
#   +-----------------------------+
#   |              |        |Serv.|
#   |   Sala       | Coz.   |1.5× |  ← zona social (7.5m × 3.3m)
#   |   3.8×3.3    | 2.2×3.3|1.65 |    Serviço adjacente à Cozinha
#   |              |        |     |
#   +-----------------------------+
#            RUA
#
def _2q_rect_sep():
    # intimate width = Q1(3.0) + Q2(3.0) + Ban(1.5) = 7.5m
    # social width = Sala(3.8) + Coz(2.2) + Serv(1.5) = 7.5m
    # Serviço removido da zona íntima, adjacente à Cozinha na zona social
    return TemplateV2(
        id="2q_rect_sep",
        name="2Q Cozinha Separada",
        typology="rectangle",
        target_area_range=(50, 65),
        bedrooms=2,
        bathrooms=1,
        tags=["mcmv", "cozinha_separada"],
        zones=[
            Zone("social", 0, 0, 7.5, 3.3, "both"),
            Zone("corridor", 0, 3.3, 7.5, 0.90, "width"),
            Zone("intimate", 0, 4.2, 7.5, 3.3, "both"),
        ],
        rooms=[
            # --- zona social ---
            # Sala: 0.507×7.5=3.8 × 3.3 = 12.54m²  ✓ (>= 12m², min side 3.3 >= 2.4)
            RoomDef("Sala", "living", "social",
                    0.0, 0.0, 0.507, 1.0),
            # Cozinha: 0.293×7.5=2.2 × 3.3 = 7.26m²  ✓
            RoomDef("Cozinha", "kitchen", "social",
                    0.507, 0.0, 0.293, 1.0, is_wet=True),
            # Serviço: 0.20×7.5=1.5 × 0.50×3.3=1.65 = 2.475m²
            # Ajuste: usar rel_h maior → 0.52×3.3=1.716 → 1.5×1.716 = 2.574m²  ✓ (>= 2.5m², min 1.5 >= 1.5)
            RoomDef("Serviço", "service", "social",
                    0.80, 0.48, 0.20, 0.52, is_wet=True),
            # --- corredor ---
            # Corredor: 7.5×0.9 = 6.75m²  ✓ (min side 0.9 >= 0.9)
            RoomDef("Circulação", "circulation", "corridor",
                    0.0, 0.0, 1.0, 1.0),
            # --- zona íntima ---
            # intimate 7.5m: Q1=3.0(0.40), Q2=3.0(0.40), Ban=1.5(0.20)
            # Q1: 3.0×3.3 = 9.9m²  ✓ (>= 9m², both sides >= 3.0)
            RoomDef("Quarto 1", "bedroom", "intimate",
                    0.0, 0.0, 0.40, 1.0),
            # Q2: 3.0×3.3 = 9.9m²  ✓ (>= 9m², both sides >= 3.0)
            RoomDef("Quarto 2", "bedroom", "intimate",
                    0.40, 0.0, 0.40, 1.0),
            # Ban: 1.5×3.3 = 4.95m²  ✓ (>= 2.25m², min side 1.5 >= 1.2)
            RoomDef("Banheiro", "bathroom", "intimate",
                    0.80, 0.0, 0.20, 1.0, is_wet=True),
        ],
        circulation=CirculationGraph(
            entrance="Sala",
            edges={
                "Sala": ["Circulação", "Cozinha"],
                "Cozinha": ["Serviço"],
                "Circulação": ["Quarto 1", "Quarto 2", "Banheiro"],
                "Quarto 1": [],
                "Quarto 2": [],
                "Banheiro": [],
                "Serviço": [],
            },
        ),
        lot_placement=LotPlacement(
            street_facing_zone="social",
            setback_front_m=3.0,
            setback_back_m=2.0,
            setback_side_m=1.5,
            building_coverage_max=0.60,
        ),
        privacy_gradient=["Sala", "Circulação", "Cozinha", "Quarto 1", "Quarto 2"],
    )


# =====================================================================
# 3. Casa em L — ala dos quartos (sem corredor)
# =====================================================================
#
#   Lote (rua embaixo):
#
#     +----------+----------+---------+
#     |          |          |         |
#     | Q1       | Q2       | Ban.    |  ← zona íntima (7.8m × 3.6m)
#     | 3.0×3.6  | 3.0×3.6  | 1.8×3.6|
#     +----------+----------+--+------+
#     |  Hall 2.4×1.5 |        |
#     +--------+               |     ← hall de articulação
#     |              |S.       |
#     | Sala/Coz     |1.8|    |     ← zona social (5.0×4.5) + Serviço
#     | 3.95×4.5     |×1.8| Dk|       Serviço no canto + Deck
#     +--------------+----+---+
#          RUA
#
#   A articulação do L já separa social de íntimo — sem corredor.
#   O espaço livre no canto do L vira deck/área de lazer.
#   Hall pequeno no ponto de articulação distribui para quartos.
#   Serviço adjacente à Sala/Cozinha na zona social.
#
def _2q_l_quartos():
    # intimate width = Q1(3.0) + Q2(3.0) + Ban(1.8) = 7.8m
    # Banheiro agora ocupa altura total (sem Serviço empilhado)
    # Serviço movido para canto da zona social
    return TemplateV2(
        id="2q_l_quartos",
        name="2Q em L — Ala Quartos",
        typology="l_shape",
        target_area_range=(50, 65),
        bedrooms=2,
        bathrooms=1,
        tags=["l_shape", "quintal", "privacidade", "deck"],
        zones=[
            Zone("social", 0, 0, 5.0, 4.5, "both"),
            Zone("deck", 5.0, 0, 2.8, 3.0, "fixed", is_outdoor=True),
            Zone("hall", 0, 4.5, 2.4, 1.5, "fixed"),
            Zone("intimate", 0, 4.5, 7.8, 3.6, "width"),
        ],
        rooms=[
            # --- zona social ---
            # Sala/Cozinha: 1.0×5.0=5.0 × 0.60×4.5=2.7 = 13.5m²  ✓ (>= 12m², min side 2.7 >= 2.4)
            RoomDef("Sala/Cozinha", "living", "social",
                    0.0, 0.0, 1.0, 0.60),
            # Serviço: 0.36×5.0=1.8 × 0.40×4.5=1.8 = 3.24m²  ✓ (>= 2.5m², min 1.8 >= 1.5)
            RoomDef("Serviço", "service", "social",
                    0.64, 0.60, 0.36, 0.40, is_wet=True),
            # Deck: 2.8×3.0 = 8.4m² (outdoor)
            RoomDef("Deck", "varanda", "deck",
                    0.0, 0.0, 1.0, 1.0),
            # --- hall ---
            # Hall: 2.4×1.5 = 3.6m²  ✓ (min side 1.5 >= 0.9)
            RoomDef("Hall", "circulation", "hall",
                    0.0, 0.0, 1.0, 1.0),
            # --- zona íntima ---
            # intimate 7.8m: Q1=3.0(0.3846), Q2=3.0(0.3846), Ban=1.8(0.2308)
            # Q1: 3.0×3.6 = 10.8m²  ✓ (>= 9m², both sides >= 3.0)
            RoomDef("Quarto 1", "bedroom", "intimate",
                    0.0, 0.0, 0.3846, 1.0),
            # Q2: 3.0×3.6 = 10.8m²  ✓ (>= 9m², both sides >= 3.0)
            RoomDef("Quarto 2", "bedroom", "intimate",
                    0.3846, 0.0, 0.3846, 1.0),
            # Ban: 1.8×3.6 = 6.48m²  ✓ (>= 2.25m², min side 1.8 >= 1.2)
            RoomDef("Banheiro", "bathroom", "intimate",
                    0.7692, 0.0, 0.2308, 1.0, is_wet=True),
        ],
        circulation=CirculationGraph(
            entrance="Sala/Cozinha",
            edges={
                "Sala/Cozinha": ["Hall", "Deck", "Serviço"],
                "Hall": ["Quarto 1", "Quarto 2", "Banheiro"],
                "Deck": [],
                "Quarto 1": [],
                "Quarto 2": [],
                "Banheiro": [],
                "Serviço": [],
            },
        ),
        lot_placement=LotPlacement(
            street_facing_zone="social",
            setback_front_m=3.0,
            setback_back_m=1.5,
            setback_side_m=1.5,
            building_coverage_max=0.55,
            garden_side="side",
        ),
        privacy_gradient=["Deck", "Sala/Cozinha", "Hall", "Quarto 1", "Quarto 2"],
    )


# =====================================================================
# 4. Retangular com varanda frontal
# =====================================================================
#
#   +----------+----------+---------+
#   |          |          |         |
#   | Q1       | Q2       | Ban.    |  ← zona íntima (7.8m × 3.6m)
#   | 3.0×3.6  | 3.0×3.6  | 1.8×3.6|
#   |          |          |         |
#   +----------+----------+---------+
#   |       Corredor (7.8×0.9)      |
#   +-----------------------------+-+
#   |                             |S|
#   |     Sala/Cozinha            |e|  ← zona social (7.8m × 3.6m)
#   |     6.0×3.6                 |r|     Serviço no canto dos fundos
#   |                             |v|     1.8×1.8
#   +-----------------------------+-+
#   |     Varanda (4.5×2.0)         |  ← zona outdoor (coberta)
#   +-------------------------------+
#            RUA
#
def _2q_varanda_frontal():
    # intimate width = Q1(3.0) + Q2(3.0) + Ban(1.8) = 7.8m
    # Banheiro agora ocupa altura total
    # Serviço movido para canto da zona social
    return TemplateV2(
        id="2q_varanda_frontal",
        name="2Q com Varanda Frontal",
        typology="rectangle",
        target_area_range=(50, 65),
        bedrooms=2,
        bathrooms=1,
        tags=["varanda", "transicao_social", "acolhedor"],
        zones=[
            Zone("varanda", 0, -2.0, 4.5, 2.0, "width", is_outdoor=True),
            Zone("social", 0, 0, 7.8, 3.6, "both"),
            Zone("corridor", 0, 3.6, 7.8, 0.90, "width"),
            Zone("intimate", 0, 4.5, 7.8, 3.6, "both"),
        ],
        rooms=[
            # Varanda: 4.5×2.0 = 9.0m² (outdoor)
            RoomDef("Varanda", "varanda", "varanda",
                    0.0, 0.0, 1.0, 1.0),
            # --- zona social ---
            # Sala/Cozinha: 0.77×7.8=6.006 × 3.6 = 21.6m²  ✓ (>= 12m², min side 3.6 >= 2.4)
            RoomDef("Sala/Cozinha", "living", "social",
                    0.0, 0.0, 0.77, 1.0),
            # Serviço: 0.23×7.8=1.794 × 0.50×3.6=1.8 = 3.23m²  ✓ (>= 2.5m², min side 1.794 >= 1.5)
            RoomDef("Serviço", "service", "social",
                    0.77, 0.50, 0.23, 0.50, is_wet=True),
            # --- corredor ---
            # Corredor: 7.8×0.9 = 7.02m²  ✓ (min side 0.9 >= 0.9)
            RoomDef("Circulação", "circulation", "corridor",
                    0.0, 0.0, 1.0, 1.0),
            # --- zona íntima ---
            # intimate 7.8m: Q1=3.0(0.3846), Q2=3.0(0.3846), Ban=1.8(0.2308)
            # Q1: 3.0×3.6 = 10.8m²  ✓ (>= 9m², both sides >= 3.0)
            RoomDef("Quarto 1", "bedroom", "intimate",
                    0.0, 0.0, 0.3846, 1.0),
            # Q2: 3.0×3.6 = 10.8m²  ✓ (>= 9m², both sides >= 3.0)
            RoomDef("Quarto 2", "bedroom", "intimate",
                    0.3846, 0.0, 0.3846, 1.0),
            # Ban: 1.8×3.6 = 6.48m²  ✓ (>= 2.25m², min side 1.8 >= 1.2)
            RoomDef("Banheiro", "bathroom", "intimate",
                    0.7692, 0.0, 0.2308, 1.0, is_wet=True),
        ],
        circulation=CirculationGraph(
            entrance="Varanda",
            edges={
                "Varanda": ["Sala/Cozinha"],
                "Sala/Cozinha": ["Circulação", "Serviço"],
                "Circulação": ["Quarto 1", "Quarto 2", "Banheiro"],
                "Quarto 1": [],
                "Quarto 2": [],
                "Banheiro": [],
                "Serviço": [],
            },
        ),
        lot_placement=LotPlacement(
            street_facing_zone="varanda",
            setback_front_m=3.0,
            setback_back_m=2.0,
            setback_side_m=1.5,
            building_coverage_max=0.55,
        ),
        privacy_gradient=["Varanda", "Sala/Cozinha", "Circulação", "Quarto 1", "Quarto 2"],
    )


# =====================================================================
# 5. Com garagem lateral
# =====================================================================
#
#   +----------+----------+---------+
#   |          |          |         |
#   | Q1       | Q2       | Ban.    |  ← zona íntima (8.0m × 3.3m)
#   | 3.0×3.3  | 3.0×3.3  | 2.0×3.3|
#   |          |          |         |
#   +----------+----------+---------+
#   |       Corredor (8.0×0.9)      |
#   +-------------+---------+-------+
#   |             |         |Serv.  |
#   | Sala/Coz    | Garagem |2.0×   |  ← zona social + garagem
#   | 3.8×4.0     | 3.0×4.0 |1.65   |    Serviço no canto social
#   |             |         |       |
#   +-------------+---------+-------+
#            RUA
#
def _2q_gar_lateral():
    # intimate width = Q1(3.0) + Q2(3.0) + Ban(2.0) = 8.0m
    # social width = Sala/Coz(3.0) + Garage(3.0) + Serv col = 8.0m
    # Banheiro agora ocupa altura total
    # Serviço movido para canto da zona social
    return TemplateV2(
        id="2q_gar_lateral",
        name="2Q com Garagem Lateral",
        typology="rectangle",
        target_area_range=(55, 70),
        bedrooms=2,
        bathrooms=1,
        tags=["garagem", "mcmv"],
        zones=[
            Zone("social", 0, 0, 5.0, 4.0, "both"),
            Zone("garage", 5.0, 0, 3.0, 4.0, "depth"),
            Zone("corridor", 0, 4.0, 8.0, 0.90, "width"),
            Zone("intimate", 0, 4.9, 8.0, 3.3, "both"),
        ],
        rooms=[
            # --- zona social ---
            # Sala/Cozinha: 0.60×5.0=3.0 × 4.0 = 12.0m²  ✓ (>= 12m², min side 3.0 >= 2.4)
            # Widened: use 0.64 → 0.64×5.0=3.2 × 4.0 = 12.8m²  ✓ (>= 12m², min side 3.2 >= 2.4)
            RoomDef("Sala/Cozinha", "living", "social",
                    0.0, 0.0, 0.64, 1.0),
            # Serviço: 0.36×5.0=1.8 × 0.50×4.0=2.0 = 3.6m²  ✓ (>= 2.5m², min side 1.8 >= 1.5)
            RoomDef("Serviço", "service", "social",
                    0.64, 0.50, 0.36, 0.50, is_wet=True),
            # Garagem: 3.0×4.0 = 12.0m²  ✓ (>= 12m², min side 3.0 >= 3.0)
            RoomDef("Garagem", "garage", "garage",
                    0.0, 0.0, 1.0, 1.0),
            # --- corredor ---
            # Corredor: 8.0×0.9 = 7.2m²  ✓ (min side 0.9 >= 0.9)
            RoomDef("Circulação", "circulation", "corridor",
                    0.0, 0.0, 1.0, 1.0),
            # --- zona íntima ---
            # intimate 8.0m: Q1=3.0(0.375), Q2=3.0(0.375), Ban=2.0(0.25)
            # Q1: 3.0×3.3 = 9.9m²  ✓ (>= 9m², both sides >= 3.0)
            RoomDef("Quarto 1", "bedroom", "intimate",
                    0.0, 0.0, 0.375, 1.0),
            # Q2: 3.0×3.3 = 9.9m²  ✓ (>= 9m², both sides >= 3.0)
            RoomDef("Quarto 2", "bedroom", "intimate",
                    0.375, 0.0, 0.375, 1.0),
            # Ban: 2.0×3.3 = 6.6m²  ✓ (>= 2.25m², min side 2.0 >= 1.2)
            RoomDef("Banheiro", "bathroom", "intimate",
                    0.75, 0.0, 0.25, 1.0, is_wet=True),
        ],
        circulation=CirculationGraph(
            entrance="Sala/Cozinha",
            edges={
                "Sala/Cozinha": ["Circulação", "Garagem", "Serviço"],
                "Circulação": ["Quarto 1", "Quarto 2", "Banheiro"],
                "Garagem": [],
                "Quarto 1": [],
                "Quarto 2": [],
                "Banheiro": [],
                "Serviço": [],
            },
        ),
        lot_placement=LotPlacement(
            street_facing_zone="social",
            setback_front_m=3.0,
            setback_back_m=2.0,
            setback_side_m=1.5,
            building_coverage_max=0.65,
            driveway_side="right",
        ),
        privacy_gradient=["Garagem", "Sala/Cozinha", "Circulação", "Quarto 1", "Quarto 2"],
    )


# =====================================================================
# 6. Com pátio de serviço coberto lateral
# =====================================================================
#
#   +----------+----------+---------+
#   |          |          |         |
#   | Q1       | Q2       | Ban.    |  ← zona íntima (7.8m × 3.3m)
#   | 3.0×3.3  | 3.0×3.3  | 1.8×3.3|
#   |          |          |         |
#   +----------+----------+---------+
#   |     Corredor (6.0×0.9)|Pátio  |
#   +------------------------|Ser   |  ← pátio de serviço (outdoor)
#   |                  |Serv|vico   |
#   |  Sala/Cozinha    |1.8×|1.8×   |
#   |  4.2×3.6         |1.8 |4.5    |
#   |                  +----+-------+
#   +------------------+
#          RUA
#
def _2q_patio_servico():
    # intimate width = Q1(3.0) + Q2(3.0) + Ban(1.8) = 7.8m
    # Banheiro agora ocupa altura total
    # Serviço movido para zona social, adjacente ao pátio
    return TemplateV2(
        id="2q_patio_servico",
        name="2Q com Pátio de Serviço",
        typology="l_shape",
        target_area_range=(50, 65),
        bedrooms=2,
        bathrooms=1,
        tags=["patio", "servico", "ventilacao"],
        zones=[
            Zone("social", 0, 0, 6.0, 3.6, "both"),
            Zone("corridor", 0, 3.6, 6.0, 0.90, "width"),
            Zone("intimate", 0, 4.5, 7.8, 3.3, "width"),
            Zone("patio", 6.0, 0, 1.8, 4.5, "fixed", is_outdoor=True),
        ],
        rooms=[
            # --- zona social ---
            # Sala/Cozinha: 0.70×6.0=4.2 × 3.6 = 15.12m²  ✓ (>= 12m², min side 3.6 >= 2.4)
            RoomDef("Sala/Cozinha", "living", "social",
                    0.0, 0.0, 0.70, 1.0),
            # Serviço: 0.30×6.0=1.8 × 0.50×3.6=1.8 = 3.24m²  ✓ (>= 2.5m², min side 1.8 >= 1.5)
            RoomDef("Serviço", "service", "social",
                    0.70, 0.50, 0.30, 0.50, is_wet=True),
            # --- corredor ---
            # Corredor: 6.0×0.9 = 5.4m²  ✓ (min side 0.9 >= 0.9)
            RoomDef("Circulação", "circulation", "corridor",
                    0.0, 0.0, 1.0, 1.0),
            # --- zona íntima ---
            # intimate 7.8m: Q1=3.0(0.3846), Q2=3.0(0.3846), Ban=1.8(0.2308)
            # Q1: 3.0×3.3 = 9.9m²  ✓ (>= 9m², both sides >= 3.0)
            RoomDef("Quarto 1", "bedroom", "intimate",
                    0.0, 0.0, 0.3846, 1.0),
            # Q2: 3.0×3.3 = 9.9m²  ✓ (>= 9m², both sides >= 3.0)
            RoomDef("Quarto 2", "bedroom", "intimate",
                    0.3846, 0.0, 0.3846, 1.0),
            # Ban: 1.8×3.3 = 5.94m²  ✓ (>= 2.25m², min side 1.8 >= 1.2)
            RoomDef("Banheiro", "bathroom", "intimate",
                    0.7692, 0.0, 0.2308, 1.0, is_wet=True),
            # Pátio: 1.8×4.5 = 8.1m² (outdoor)
            RoomDef("Pátio Serviço", "service", "patio",
                    0.0, 0.0, 1.0, 1.0),
        ],
        circulation=CirculationGraph(
            entrance="Sala/Cozinha",
            edges={
                "Sala/Cozinha": ["Circulação", "Serviço"],
                "Serviço": ["Pátio Serviço"],
                "Circulação": ["Quarto 1", "Quarto 2", "Banheiro"],
                "Quarto 1": [],
                "Quarto 2": [],
                "Banheiro": [],
                "Pátio Serviço": [],
            },
        ),
        lot_placement=LotPlacement(
            street_facing_zone="social",
            setback_front_m=3.0,
            setback_back_m=1.5,
            setback_side_m=1.5,
            building_coverage_max=0.55,
            garden_side="both",
        ),
        privacy_gradient=["Pátio Serviço", "Sala/Cozinha", "Circulação", "Quarto 1", "Quarto 2"],
    )
