"""Catálogo de 3 quartos — 6 templates arquitetônicos.

Habitações 60-100m². Inclui configurações com suíte, garagem, 2 banheiros.

REGRA: todo quarto deve ter AMBAS dimensões >= 3.0m (mínimo 3×3 = 9m²).

MUDANÇA ARQUITETÔNICA: Serviço fica na zona social (canto dos fundos,
adjacente à cozinha, com acesso ao exterior), NUNCA empilhado com banheiro
na zona íntima.
"""

from ._base import TemplateV2, Zone, RoomDef, CirculationGraph, LotPlacement


def _templates() -> list:
    return [
        _3q_rect_compact(),
        _3q_rect_2ban(),
        _3q_l_suite(),
        _3q_gar_lateral(),
        _3q_gar_2ban(),
        _3q_varanda_quintal(),
    ]


# =====================================================================
# 1. 3Q retangular compacto
# =====================================================================
#
#   Zona íntima = 3×3.0 + 1.8(ban) = 10.8m
#
#   +-------+-------+-------+------+
#   |       |       |       |      |
#   | Q1    | Q2    | Q3    | Ban. |  3.6m
#   |       |       |       |      |
#   +-------+-------+-------+------+
#   |           Corredor            |  0.9m
#   +------------------------+-----+
#   |                        |Serv.|
#   |      Sala/Cozinha      |     |  3.6m
#   |                        |     |
#   +------------------------+-----+
#               RUA
#
#   Largura total: 10.8m
#   Serviço no canto posterior da zona social, adjacente à cozinha.
#   Banheiro ocupa coluna inteira na zona íntima (full height).
#
def _3q_rect_compact():
    return TemplateV2(
        id="3q_rect_compact",
        name="3Q Retangular Compacto",
        typology="rectangle",
        target_area_range=(60, 78),
        bedrooms=3,
        bathrooms=1,
        tags=["mcmv", "compacto", "cozinha_integrada"],
        zones=[
            Zone("social", 0, 0, 10.8, 3.6, "both"),          # 10.8×3.6 = 38.88m²
            Zone("corridor", 0, 3.6, 10.8, 0.90, "width"),    # 10.8×0.9 = 9.72m²
            Zone("intimate", 0, 4.5, 10.8, 3.6, "both"),      # 10.8×3.6 = 38.88m²
        ],
        rooms=[
            # Sala: 0.83×10.8=8.96 × 3.6 = 32.27m² ≥12m² ✓, min side 3.6≥2.4 ✓
            RoomDef("Sala/Cozinha", "living", "social",
                    0.0, 0.0, 0.83, 1.0),
            # Serv: 0.17×10.8=1.84 × 0.50×3.6=1.80 = 3.31m² ≥2.5m² ✓, 1.80≥1.5 ✓, 1.84≥1.5 ✓
            RoomDef("Serviço", "service", "social",
                    0.83, 0.50, 0.17, 0.50, is_wet=True),
            # Corredor: 10.8×0.9 = 9.72m², min side 0.9≥0.9 ✓
            RoomDef("Circulação", "circulation", "corridor",
                    0.0, 0.0, 1.0, 1.0),
            # Q1: 0.2778×10.8=3.0 × 3.6 = 10.80m² ≥9m² ✓, 3.0≥3.0 ✓, 3.6≥3.0 ✓
            RoomDef("Quarto 1", "bedroom", "intimate",
                    0.0, 0.0, 0.2778, 1.0),
            # Q2: 0.2778×10.8=3.0 × 3.6 = 10.80m² ≥9m² ✓, 3.0≥3.0 ✓, 3.6≥3.0 ✓
            RoomDef("Quarto 2", "bedroom", "intimate",
                    0.2778, 0.0, 0.2778, 1.0),
            # Q3: 0.2778×10.8=3.0 × 3.6 = 10.80m² ≥9m² ✓, 3.0≥3.0 ✓, 3.6≥3.0 ✓
            RoomDef("Quarto 3", "bedroom", "intimate",
                    0.5556, 0.0, 0.2778, 1.0),
            # Ban: 0.1666×10.8=1.80 × 3.6 = 6.48m² ≥2.25m² ✓, 1.80≥1.2 ✓
            RoomDef("Banheiro", "bathroom", "intimate",
                    0.8334, 0.0, 0.1666, 1.0, is_wet=True),
        ],
        circulation=CirculationGraph(
            entrance="Sala/Cozinha",
            edges={
                "Sala/Cozinha": ["Circulação", "Serviço"],
                "Circulação": ["Quarto 1", "Quarto 2", "Quarto 3",
                               "Banheiro"],
                "Quarto 1": [],
                "Quarto 2": [],
                "Quarto 3": [],
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
        privacy_gradient=["Sala/Cozinha", "Circulação", "Quarto 1", "Quarto 2", "Quarto 3"],
    )


# =====================================================================
# 2. 3Q com 2 banheiros — todos tocam corredor
# =====================================================================
#
#   Zona íntima = 3×3.0 + 1.5(ban1) + 1.5(ban2) = 12.0m
#
#   +------+------+------+-----+-----+
#   |      |      |      |     |     |
#   | Q1   | Q2   | Q3   |Ban1 |Ban2 |  3.6m
#   |      |      |      |     |     |
#   +------+------+------+-----+-----+
#   |           Corredor              |  0.9m
#   +---------------------------+-----+
#   |                           |Serv.|
#   |        Sala/Cozinha       |     |  3.6m
#   |                           |     |
#   +---------------------------+-----+
#                 RUA
#
#   Largura total: 12.0m
#   Serviço no canto posterior da zona social.
#   Ban2 agora ocupa coluna inteira na zona íntima (full height).
#
def _3q_rect_2ban():
    return TemplateV2(
        id="3q_rect_2ban",
        name="3Q com 2 Banheiros",
        typology="rectangle",
        target_area_range=(70, 88),
        bedrooms=3,
        bathrooms=2,
        tags=["mcmv", "2_banheiros", "cozinha_integrada"],
        zones=[
            Zone("social", 0, 0, 12.0, 3.6, "both"),          # 12.0×3.6 = 43.20m²
            Zone("corridor", 0, 3.6, 12.0, 0.90, "width"),    # 12.0×0.9 = 10.80m²
            Zone("intimate", 0, 4.5, 12.0, 3.6, "both"),      # 12.0×3.6 = 43.20m²
        ],
        rooms=[
            # Sala: 0.85×12.0=10.20 × 3.6 = 36.72m² ≥12m² ✓, min side 3.6≥2.4 ✓
            RoomDef("Sala/Cozinha", "living", "social",
                    0.0, 0.0, 0.85, 1.0),
            # Serv: 0.15×12.0=1.80 × 0.50×3.6=1.80 = 3.24m² ≥2.5m² ✓, 1.80≥1.5 ✓
            RoomDef("Serviço", "service", "social",
                    0.85, 0.50, 0.15, 0.50, is_wet=True),
            # Corredor: 12.0×0.9 = 10.80m², min side 0.9≥0.9 ✓
            RoomDef("Circulação", "circulation", "corridor",
                    0.0, 0.0, 1.0, 1.0),
            # Q1: 0.25×12.0=3.0 × 3.6 = 10.80m² ≥9m² ✓, 3.0≥3.0 ✓, 3.6≥3.0 ✓
            RoomDef("Quarto 1", "bedroom", "intimate",
                    0.0, 0.0, 0.25, 1.0),
            # Q2: 0.25×12.0=3.0 × 3.6 = 10.80m² ≥9m² ✓, 3.0≥3.0 ✓, 3.6≥3.0 ✓
            RoomDef("Quarto 2", "bedroom", "intimate",
                    0.25, 0.0, 0.25, 1.0),
            # Q3: 0.25×12.0=3.0 × 3.6 = 10.80m² ≥9m² ✓, 3.0≥3.0 ✓, 3.6≥3.0 ✓
            RoomDef("Quarto 3", "bedroom", "intimate",
                    0.50, 0.0, 0.25, 1.0),
            # Ban1: 0.125×12.0=1.50 × 3.6 = 5.40m² ≥2.25m² ✓, 1.50≥1.2 ✓
            RoomDef("Banheiro 1", "bathroom", "intimate",
                    0.75, 0.0, 0.125, 1.0, is_wet=True),
            # Ban2: 0.125×12.0=1.50 × 3.6 = 5.40m² ≥2.25m² ✓, 1.50≥1.2 ✓
            RoomDef("Banheiro 2", "bathroom", "intimate",
                    0.875, 0.0, 0.125, 1.0, is_wet=True),
        ],
        circulation=CirculationGraph(
            entrance="Sala/Cozinha",
            edges={
                "Sala/Cozinha": ["Circulação", "Serviço"],
                "Circulação": ["Quarto 1", "Quarto 2", "Quarto 3",
                               "Banheiro 1", "Banheiro 2"],
                "Quarto 1": [],
                "Quarto 2": [],
                "Quarto 3": [],
                "Banheiro 1": [],
                "Banheiro 2": [],
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
        privacy_gradient=["Sala/Cozinha", "Circulação", "Quarto 1", "Quarto 2", "Quarto 3"],
    )


# =====================================================================
# 3. 3Q em L — suíte na ala
# =====================================================================
#
#   Zona íntima = 3×3.0 + 1.5(ban1) + 1.5(ban2) = 12.0m
#
#   +------+------+-------+------+
#   |      |      |       |      |
#   | Q1   | Q2   | Q3    | Ban2 |  4.2m
#   |      |      |(suíte)|      |
#   |      |      |       |      |
#   +------+------+-------+------+
#   |  Hall  | Ban1 |
#   +--------+------+
#   |           |Serv.|
#   | Sala/Coz  |     |    ← zona social + serviço no canto
#   |           |     |
#   +-----------+-----+
#          RUA
#
#   Q3 é suíte com Ban2 privativo. Ban1 é social (acesso pelo hall).
#   Serviço no canto posterior da zona social, adjacente à cozinha.
#
def _3q_l_suite():
    return TemplateV2(
        id="3q_l_suite",
        name="3Q em L — Suíte",
        typology="l_shape",
        target_area_range=(75, 92),
        bedrooms=3,
        bathrooms=2,
        tags=["l_shape", "suite", "deck", "privacidade", "2_banheiros"],
        zones=[
            Zone("social", 0, 0, 5.4, 4.5, "both"),           # 5.4×4.5 = 24.30m²
            Zone("deck", 5.4, 0, 2.5, 3.0, "fixed", is_outdoor=True),  # 2.5×3.0 = 7.50m²
            Zone("hall", 0, 4.5, 2.7, 1.5, "fixed"),          # 2.7×1.5 = 4.05m²
            Zone("intimate", 0, 4.5, 12.0, 4.2, "width"),     # 12.0×4.2 = 50.40m²
        ],
        rooms=[
            # Sala: 0.70×5.4=3.78 × 4.5 = 17.01m² ≥12m² ✓, min side 3.78≥2.4 ✓
            RoomDef("Sala/Cozinha", "living", "social",
                    0.0, 0.0, 0.70, 1.0),
            # Serv: 0.30×5.4=1.62 × 0.50×4.5=2.25 = 3.65m² ≥2.5m² ✓, 1.62≥1.5 ✓, 2.25≥1.5 ✓
            RoomDef("Serviço", "service", "social",
                    0.70, 0.50, 0.30, 0.50, is_wet=True),
            # Deck: 2.5×3.0 = 7.50m² (outdoor)
            RoomDef("Deck", "varanda", "deck",
                    0.0, 0.0, 1.0, 1.0),
            # Hall: 2.7×1.5 = 4.05m², min side 1.5≥0.9 ✓
            RoomDef("Hall", "circulation", "hall",
                    0.0, 0.0, 1.0, 1.0),
            # Q1: 0.25×12.0=3.0 × 4.2 = 12.60m² ≥9m² ✓, 3.0≥3.0 ✓, 4.2≥3.0 ✓
            RoomDef("Quarto 1", "bedroom", "intimate",
                    0.0, 0.0, 0.25, 1.0),
            # Q2: 0.25×12.0=3.0 × 4.2 = 12.60m² ≥9m² ✓, 3.0≥3.0 ✓, 4.2≥3.0 ✓
            RoomDef("Quarto 2", "bedroom", "intimate",
                    0.25, 0.0, 0.25, 1.0),
            # Ban1: 0.125×12.0=1.50 × 4.2 = 6.30m² ≥2.25m² ✓, 1.50≥1.2 ✓
            RoomDef("Banheiro 1", "bathroom", "intimate",
                    0.50, 0.0, 0.125, 1.0, is_wet=True),
            # Q3 (suíte): 0.25×12.0=3.0 × 4.2 = 12.60m² ≥9m² ✓, 3.0≥3.0 ✓, 4.2≥3.0 ✓
            RoomDef("Quarto 3", "bedroom", "intimate",
                    0.625, 0.0, 0.25, 1.0),
            # Ban2: 0.125×12.0=1.50 × 4.2 = 6.30m² ≥2.25m² ✓, 1.50≥1.2 ✓
            RoomDef("Banheiro 2", "bathroom", "intimate",
                    0.875, 0.0, 0.125, 1.0, is_wet=True),
        ],
        circulation=CirculationGraph(
            entrance="Sala/Cozinha",
            edges={
                "Sala/Cozinha": ["Hall", "Deck", "Serviço"],
                "Hall": ["Quarto 1", "Quarto 2", "Banheiro 1", "Quarto 3"],
                "Quarto 3": ["Banheiro 2"],  # suíte: banheiro privativo
                "Deck": [],
                "Quarto 1": [],
                "Quarto 2": [],
                "Banheiro 1": [],
                "Banheiro 2": [],
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
        privacy_gradient=["Deck", "Sala/Cozinha", "Hall", "Quarto 1", "Quarto 2", "Quarto 3"],
    )


# =====================================================================
# 4. 3Q com garagem lateral
# =====================================================================
#
#   Zona íntima = 3×3.0 + 1.8(ban) = 10.8m
#   Social (6.8m) + Garagem (4.0m) = 10.8m
#
#   +-------+-------+-------+------+
#   |       |       |       |      |
#   | Q1    | Q2    | Q3    | Ban. |  3.6m
#   |       |       |       |      |
#   +-------+-------+-------+------+
#   |           Corredor            |  0.9m
#   +----------+-----+-------------+
#   |          |Serv.|             |
#   | Sala/Coz |     |  Garagem   |  4.0m
#   |  4.8m    |2.0m |   4.0m     |
#   +----------+-----+-------------+
#               RUA
#
#   Largura total: 10.8m
#   Serviço entre Sala/Cozinha e Garagem, no fundo da zona social.
#   Banheiro ocupa coluna inteira na zona íntima.
#
def _3q_gar_lateral():
    return TemplateV2(
        id="3q_gar_lateral",
        name="3Q com Garagem Lateral",
        typology="rectangle",
        target_area_range=(72, 92),
        bedrooms=3,
        bathrooms=1,
        tags=["garagem", "mcmv"],
        zones=[
            Zone("social", 0, 0, 6.8, 4.0, "both"),           # 6.8×4.0 = 27.20m²
            Zone("garage", 6.8, 0, 4.0, 4.0, "depth"),        # 4.0×4.0 = 16.00m²
            Zone("corridor", 0, 4.0, 10.8, 0.90, "width"),    # 10.8×0.9 = 9.72m²
            Zone("intimate", 0, 4.9, 10.8, 3.6, "both"),      # 10.8×3.6 = 38.88m²
        ],
        rooms=[
            # Sala: 0.71×6.8=4.83 × 4.0 = 19.31m² ≥12m² ✓, min side 4.0≥2.4 ✓
            RoomDef("Sala/Cozinha", "living", "social",
                    0.0, 0.0, 0.71, 1.0),
            # Serv: 0.29×6.8=1.97 × 0.50×4.0=2.00 = 3.94m² ≥2.5m² ✓, 1.97≥1.5 ✓, 2.00≥1.5 ✓
            RoomDef("Serviço", "service", "social",
                    0.71, 0.50, 0.29, 0.50, is_wet=True),
            # Garagem: 4.0×4.0 = 16.00m² ≥12m² ✓, min side 4.0≥3.0 ✓
            RoomDef("Garagem", "garage", "garage",
                    0.0, 0.0, 1.0, 1.0),
            # Corredor: 10.8×0.9 = 9.72m², min side 0.9≥0.9 ✓
            RoomDef("Circulação", "circulation", "corridor",
                    0.0, 0.0, 1.0, 1.0),
            # Q1: 0.2778×10.8=3.0 × 3.6 = 10.80m² ≥9m² ✓, 3.0≥3.0 ✓, 3.6≥3.0 ✓
            RoomDef("Quarto 1", "bedroom", "intimate",
                    0.0, 0.0, 0.2778, 1.0),
            # Q2: 0.2778×10.8=3.0 × 3.6 = 10.80m² ≥9m² ✓, 3.0≥3.0 ✓, 3.6≥3.0 ✓
            RoomDef("Quarto 2", "bedroom", "intimate",
                    0.2778, 0.0, 0.2778, 1.0),
            # Q3: 0.2778×10.8=3.0 × 3.6 = 10.80m² ≥9m² ✓, 3.0≥3.0 ✓, 3.6≥3.0 ✓
            RoomDef("Quarto 3", "bedroom", "intimate",
                    0.5556, 0.0, 0.2778, 1.0),
            # Ban: 0.1666×10.8=1.80 × 3.6 = 6.48m² ≥2.25m² ✓, 1.80≥1.2 ✓
            RoomDef("Banheiro", "bathroom", "intimate",
                    0.8334, 0.0, 0.1666, 1.0, is_wet=True),
        ],
        circulation=CirculationGraph(
            entrance="Sala/Cozinha",
            edges={
                "Sala/Cozinha": ["Circulação", "Garagem", "Serviço"],
                "Circulação": ["Quarto 1", "Quarto 2", "Quarto 3",
                               "Banheiro"],
                "Garagem": [],
                "Quarto 1": [],
                "Quarto 2": [],
                "Quarto 3": [],
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
        privacy_gradient=["Garagem", "Sala/Cozinha", "Circulação",
                          "Quarto 1", "Quarto 2", "Quarto 3"],
    )


# =====================================================================
# 5. 3Q completa: garagem + 2 banheiros
# =====================================================================
#
#   Zona íntima = 3×3.0 + 1.5(ban1) + 1.5(ban2) = 12.0m
#   Social (7.0m) + Garagem (5.0m) = 12.0m
#
#   +------+------+------+-----+-----+
#   |      |      |      |     |     |
#   | Q1   | Q2   | Q3   |Ban1 |Ban2 |  4.2m
#   |      |      |      |     |     |
#   +------+------+------+-----+-----+
#   |           Corredor              |  0.9m
#   +------------+-----+-------------+
#   |            |Serv.|             |
#   |  Sala/Coz  |     |  Garagem   |  4.0m
#   |   5.0m     |2.0m |   5.0m     |
#   +------------+-----+-------------+
#                RUA
#
#   Largura total: 12.0m
#   Serviço no canto posterior da zona social, entre cozinha e garagem.
#   Ambos banheiros com coluna inteira na zona íntima.
#
def _3q_gar_2ban():
    return TemplateV2(
        id="3q_gar_2ban",
        name="3Q Garagem + 2 Banheiros",
        typology="rectangle",
        target_area_range=(85, 105),
        bedrooms=3,
        bathrooms=2,
        tags=["garagem", "2_banheiros", "cozinha_integrada", "completa"],
        zones=[
            Zone("social", 0, 0, 7.0, 4.0, "both"),           # 7.0×4.0 = 28.00m²
            Zone("garage", 7.0, 0, 5.0, 4.0, "depth"),        # 5.0×4.0 = 20.00m²
            Zone("corridor", 0, 4.0, 12.0, 0.90, "width"),    # 12.0×0.9 = 10.80m²
            Zone("intimate", 0, 4.9, 12.0, 4.2, "both"),      # 12.0×4.2 = 50.40m²
        ],
        rooms=[
            # Sala: 0.72×7.0=5.04 × 4.0 = 20.16m² ≥12m² ✓, min side 4.0≥2.4 ✓
            RoomDef("Sala/Cozinha", "living", "social",
                    0.0, 0.0, 0.72, 1.0),
            # Serv: 0.28×7.0=1.96 × 0.50×4.0=2.00 = 3.92m² ≥2.5m² ✓, 1.96≥1.5 ✓, 2.00≥1.5 ✓
            RoomDef("Serviço", "service", "social",
                    0.72, 0.50, 0.28, 0.50, is_wet=True),
            # Garagem: 5.0×4.0 = 20.00m² ≥12m² ✓, min side 4.0≥3.0 ✓
            RoomDef("Garagem", "garage", "garage",
                    0.0, 0.0, 1.0, 1.0),
            # Corredor: 12.0×0.9 = 10.80m², min side 0.9≥0.9 ✓
            RoomDef("Circulação", "circulation", "corridor",
                    0.0, 0.0, 1.0, 1.0),
            # Q1: 0.25×12.0=3.0 × 4.2 = 12.60m² ≥9m² ✓, 3.0≥3.0 ✓, 4.2≥3.0 ✓
            RoomDef("Quarto 1", "bedroom", "intimate",
                    0.0, 0.0, 0.25, 1.0),
            # Q2: 0.25×12.0=3.0 × 4.2 = 12.60m² ≥9m² ✓, 3.0≥3.0 ✓, 4.2≥3.0 ✓
            RoomDef("Quarto 2", "bedroom", "intimate",
                    0.25, 0.0, 0.25, 1.0),
            # Q3: 0.25×12.0=3.0 × 4.2 = 12.60m² ≥9m² ✓, 3.0≥3.0 ✓, 4.2≥3.0 ✓
            RoomDef("Quarto 3", "bedroom", "intimate",
                    0.50, 0.0, 0.25, 1.0),
            # Ban1: 0.125×12.0=1.50 × 4.2 = 6.30m² ≥2.25m² ✓, 1.50≥1.2 ✓
            RoomDef("Banheiro 1", "bathroom", "intimate",
                    0.75, 0.0, 0.125, 1.0, is_wet=True),
            # Ban2: 0.125×12.0=1.50 × 4.2 = 6.30m² ≥2.25m² ✓, 1.50≥1.2 ✓
            RoomDef("Banheiro 2", "bathroom", "intimate",
                    0.875, 0.0, 0.125, 1.0, is_wet=True),
        ],
        circulation=CirculationGraph(
            entrance="Sala/Cozinha",
            edges={
                "Sala/Cozinha": ["Circulação", "Garagem", "Serviço"],
                "Circulação": ["Quarto 1", "Quarto 2", "Quarto 3",
                               "Banheiro 1", "Banheiro 2"],
                "Garagem": [],
                "Quarto 1": [],
                "Quarto 2": [],
                "Quarto 3": [],
                "Banheiro 1": [],
                "Banheiro 2": [],
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
        privacy_gradient=["Garagem", "Sala/Cozinha", "Circulação",
                          "Quarto 1", "Quarto 2", "Quarto 3"],
    )


# =====================================================================
# 6. 3Q com varanda + quintal nos fundos
# =====================================================================
#
#   Zona íntima = 3×3.0 + 1.8(ban) = 10.8m
#
#   +-------+-------+-------+------+
#   |       |       |       |      |
#   | Q1    | Q2    | Q3    | Ban. |  3.6m
#   |       |       |       |      |
#   +-------+-------+-------+------+
#   |           Corredor            |  0.9m
#   +------------------------+-----+
#   |                        |Serv.|
#   |      Sala/Cozinha      |     |  3.3m
#   |                        |     |
#   +------------------------+-----+
#   |         Varanda               |  2.0m (outdoor)
#   +-------------------------------+
#               RUA
#
#   Largura total: 10.8m
#   Quintal fica atrás da zona íntima (recuo de fundos generoso).
#   Serviço no canto posterior da zona social.
#   Banheiro ocupa coluna inteira na zona íntima.
#
def _3q_varanda_quintal():
    return TemplateV2(
        id="3q_varanda_quintal",
        name="3Q Varanda + Quintal",
        typology="rectangle",
        target_area_range=(68, 82),
        bedrooms=3,
        bathrooms=1,
        tags=["varanda", "quintal", "cozinha_integrada"],
        zones=[
            Zone("varanda", 0, -2.0, 5.0, 2.0, "width", is_outdoor=True),  # 5.0×2.0 = 10.0m²
            Zone("social", 0, 0, 10.8, 3.3, "both"),          # 10.8×3.3 = 35.64m²
            Zone("corridor", 0, 3.3, 10.8, 0.90, "width"),    # 10.8×0.9 = 9.72m²
            Zone("intimate", 0, 4.2, 10.8, 3.6, "both"),      # 10.8×3.6 = 38.88m²
        ],
        rooms=[
            # Varanda: 5.0×2.0 = 10.0m² (outdoor)
            RoomDef("Varanda", "varanda", "varanda",
                    0.0, 0.0, 1.0, 1.0),
            # Sala: 0.83×10.8=8.96 × 3.3 = 29.57m² ≥12m² ✓, min side 3.3≥2.4 ✓
            RoomDef("Sala/Cozinha", "living", "social",
                    0.0, 0.0, 0.83, 1.0),
            # Serv: 0.17×10.8=1.84 × 0.50×3.3=1.65 = 3.03m² ≥2.5m² ✓, 1.65≥1.5 ✓, 1.84≥1.5 ✓
            RoomDef("Serviço", "service", "social",
                    0.83, 0.50, 0.17, 0.50, is_wet=True),
            # Corredor: 10.8×0.9 = 9.72m², min side 0.9≥0.9 ✓
            RoomDef("Circulação", "circulation", "corridor",
                    0.0, 0.0, 1.0, 1.0),
            # Q1: 0.2778×10.8=3.0 × 3.6 = 10.80m² ≥9m² ✓, 3.0≥3.0 ✓, 3.6≥3.0 ✓
            RoomDef("Quarto 1", "bedroom", "intimate",
                    0.0, 0.0, 0.2778, 1.0),
            # Q2: 0.2778×10.8=3.0 × 3.6 = 10.80m² ≥9m² ✓, 3.0≥3.0 ✓, 3.6≥3.0 ✓
            RoomDef("Quarto 2", "bedroom", "intimate",
                    0.2778, 0.0, 0.2778, 1.0),
            # Q3: 0.2778×10.8=3.0 × 3.6 = 10.80m² ≥9m² ✓, 3.0≥3.0 ✓, 3.6≥3.0 ✓
            RoomDef("Quarto 3", "bedroom", "intimate",
                    0.5556, 0.0, 0.2778, 1.0),
            # Ban: 0.1666×10.8=1.80 × 3.6 = 6.48m² ≥2.25m² ✓, 1.80≥1.2 ✓
            RoomDef("Banheiro", "bathroom", "intimate",
                    0.8334, 0.0, 0.1666, 1.0, is_wet=True),
        ],
        circulation=CirculationGraph(
            entrance="Varanda",
            edges={
                "Varanda": ["Sala/Cozinha"],
                "Sala/Cozinha": ["Circulação", "Serviço"],
                "Circulação": ["Quarto 1", "Quarto 2", "Quarto 3",
                               "Banheiro"],
                "Quarto 1": [],
                "Quarto 2": [],
                "Quarto 3": [],
                "Banheiro": [],
                "Serviço": [],
            },
        ),
        lot_placement=LotPlacement(
            street_facing_zone="varanda",
            setback_front_m=3.0,
            setback_back_m=3.0,  # generous back for quintal
            setback_side_m=1.5,
            building_coverage_max=0.50,
            garden_side="back",
        ),
        privacy_gradient=["Varanda", "Sala/Cozinha", "Circulação",
                          "Quarto 1", "Quarto 2", "Quarto 3"],
    )
