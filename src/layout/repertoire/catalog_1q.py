"""Catálogo de 1 quarto — 4 templates arquitetônicos.

Habitações compactas 25-48m². Kitnet/studio até 1Q com varanda.
Sem corredor — em 1Q o quarto abre direto da sala.
Sala/Cozinha sempre integradas.
Serviço no canto da zona social, adjacente à cozinha, com acesso ao exterior.
Zona íntima simplificada: apenas Quarto + Banheiro.
"""

from ._base import TemplateV2, Zone, RoomDef, CirculationGraph, LotPlacement


def _templates() -> list:
    return [
        _1q_studio_compact(),
        _1q_rect_open(),
        _1q_rect_largo(),
        _1q_varanda(),
    ]


# =====================================================================
# 1. Kitnet/Studio compacto
# =====================================================================
#
#   +------+------------------+
#   |Serv. |                  |
#   |1.68× |    Quarto        |   ← fundo (exterior)
#   |1.50  |    3.92×3.0      |
#   |------|                  |
#   |Ban.  |                  |
#   |1.68× |                  |
#   |1.50  |                  |
#   +------+------------------+
#   |     Sala/Cozinha        |
#   |     5.6 × 3.0          |
#   +-------------------------+
#            RUA
#
#   Zona única com planta aberta. Serviço no canto do fundo (exterior),
#   acessível pela sala. Banheiro abaixo do serviço (wet stack lateral).
#
def _1q_studio_compact():
    return TemplateV2(
        id="1q_studio_compact",
        name="Kitnet/Studio Compacto",
        typology="rectangle",
        target_area_range=(25, 35),
        bedrooms=1,
        bathrooms=1,
        tags=["kitnet", "studio", "compacto", "cozinha_integrada"],
        zones=[
            Zone("main", 0, 0, 5.6, 6.0, "both"),
        ],
        rooms=[
            # 5.6×6.0 = 33.6m²
            # Sala: 5.6 × 3.0 = 16.80m² ≥12 ✓, min 3.0≥2.4 ✓
            RoomDef("Sala/Cozinha", "living", "main",
                    0.0, 0.0, 1.0, 0.50),
            # Quarto: 0.70×5.6=3.92 × 3.0 = 11.76m² ≥9 ✓, dims 3.92×3.0 both≥3.0 ✓
            RoomDef("Quarto", "bedroom", "main",
                    0.30, 0.50, 0.70, 0.50),
            # Ban: 0.30×5.6=1.68 × 0.25×6.0=1.50 = 2.52m² ≥2.25 ✓, min 1.50≥1.2 ✓
            RoomDef("Banheiro", "bathroom", "main",
                    0.0, 0.50, 0.30, 0.25, is_wet=True),
            # Serv: 0.30×5.6=1.68 × 0.25×6.0=1.50 = 2.52m² ≥2.5 ✓, min 1.50≥1.5 ✓
            RoomDef("Serviço", "service", "main",
                    0.0, 0.75, 0.30, 0.25, is_wet=True),
        ],
        circulation=CirculationGraph(
            entrance="Sala/Cozinha",
            edges={
                "Sala/Cozinha": ["Quarto", "Banheiro", "Serviço"],
                "Quarto": [],
                "Banheiro": [],
                "Serviço": [],
            },
        ),
        lot_placement=LotPlacement(
            street_facing_zone="main",
            setback_front_m=3.0,
            setback_back_m=1.5,
            setback_side_m=1.5,
            building_coverage_max=0.50,
        ),
        privacy_gradient=["Sala/Cozinha", "Quarto"],
    )


# =====================================================================
# 2. 1Q retangular — sem corredor
# =====================================================================
#
#   +------------+------+
#   |            |      |
#   |  Quarto    | Ban. |   ← fundo (exterior)
#   |  4.16×3.0  |1.24× |
#   |            |3.0   |
#   +------------+------+
#   |            |Serv. |   ← canto fundo da zona social (exterior)
#   | Sala/Coz.  |1.51× |
#   | 3.89×3.6   |1.80  |
#   |            |      |   ← frente aberta para sala
#   +------------+------+
#          RUA
#
#   Sem corredor: quarto abre direto da sala.
#   Serviço no canto da zona social, adjacente à cozinha,
#   com acesso ao exterior (fundo). Zona íntima: só quarto + banheiro.
#
def _1q_rect_open():
    return TemplateV2(
        id="1q_rect_open",
        name="1Q Compacto",
        typology="rectangle",
        target_area_range=(35, 45),
        bedrooms=1,
        bathrooms=1,
        tags=["mcmv", "compacto", "cozinha_integrada", "sem_corredor"],
        zones=[
            Zone("social", 0, 0, 5.4, 3.6, "both"),
            Zone("intimate", 0, 3.6, 5.4, 3.0, "both"),
        ],
        rooms=[
            # --- Zona social 5.4×3.6 = 19.44m² ---
            # Sala: 0.72×5.4=3.888 × 3.6 = 14.00m² ≥12 ✓, min 3.6≥2.4 ✓
            RoomDef("Sala/Cozinha", "living", "social",
                    0.0, 0.0, 0.72, 1.0),
            # Serv: 0.28×5.4=1.512 × 0.50×3.6=1.80 = 2.72m² ≥2.5 ✓, min 1.512≥1.5 ✓
            RoomDef("Serviço", "service", "social",
                    0.72, 0.50, 0.28, 0.50, is_wet=True),
            # --- Zona íntima 5.4×3.0 = 16.20m² ---
            # Quarto: 0.77×5.4=4.158 × 3.0 = 12.47m² ≥9 ✓, dims 4.16×3.0 both≥3.0 ✓
            RoomDef("Quarto", "bedroom", "intimate",
                    0.0, 0.0, 0.77, 1.0),
            # Ban: 0.23×5.4=1.242 × 3.0 = 3.73m² ≥2.25 ✓, min 1.242≥1.2 ✓
            RoomDef("Banheiro", "bathroom", "intimate",
                    0.77, 0.0, 0.23, 1.0, is_wet=True),
        ],
        circulation=CirculationGraph(
            entrance="Sala/Cozinha",
            edges={
                "Sala/Cozinha": ["Quarto", "Banheiro", "Serviço"],
                "Quarto": [],
                "Banheiro": [],
                "Serviço": [],
            },
        ),
        lot_placement=LotPlacement(
            street_facing_zone="social",
            setback_front_m=3.0,
            setback_back_m=2.0,
            setback_side_m=1.5,
            building_coverage_max=0.55,
        ),
        privacy_gradient=["Sala/Cozinha", "Quarto"],
    )


# =====================================================================
# 3. 1Q largo — mais espaço
# =====================================================================
#
#   +-------------+------+
#   |             |      |
#   |   Quarto    | Ban. |   ← fundo (exterior)
#   |   5.08×3.3  |1.52× |
#   |             |3.3   |
#   +-------------+------+
#   |             |Serv. |   ← canto fundo da zona social
#   |  Sala/Coz.  |1.65× |
#   |  4.95×3.3   |1.65  |
#   |             |      |
#   +-------------+------+
#            RUA
#
#   Versão espaçosa. Serviço no canto da zona social,
#   adjacente à cozinha, acesso exterior pelo fundo.
#
def _1q_rect_largo():
    return TemplateV2(
        id="1q_rect_largo",
        name="1Q Espaçoso",
        typology="rectangle",
        target_area_range=(38, 48),
        bedrooms=1,
        bathrooms=1,
        tags=["cozinha_integrada", "sem_corredor", "espaçoso"],
        zones=[
            Zone("social", 0, 0, 6.6, 3.3, "both"),
            Zone("intimate", 0, 3.3, 6.6, 3.3, "both"),
        ],
        rooms=[
            # --- Zona social 6.6×3.3 = 21.78m² ---
            # Sala: 0.75×6.6=4.95 × 3.3 = 16.34m² ≥12 ✓, min 3.3≥2.4 ✓
            RoomDef("Sala/Cozinha", "living", "social",
                    0.0, 0.0, 0.75, 1.0),
            # Serv: 0.25×6.6=1.65 × 0.50×3.3=1.65 = 2.72m² ≥2.5 ✓, min 1.65≥1.5 ✓
            RoomDef("Serviço", "service", "social",
                    0.75, 0.50, 0.25, 0.50, is_wet=True),
            # --- Zona íntima 6.6×3.3 = 21.78m² ---
            # Quarto: 0.77×6.6=5.082 × 3.3 = 16.77m² ≥9 ✓, dims 5.08×3.3 both≥3.0 ✓
            RoomDef("Quarto", "bedroom", "intimate",
                    0.0, 0.0, 0.77, 1.0),
            # Ban: 0.23×6.6=1.518 × 3.3 = 5.01m² ≥2.25 ✓, min 1.518≥1.2 ✓
            RoomDef("Banheiro", "bathroom", "intimate",
                    0.77, 0.0, 0.23, 1.0, is_wet=True),
        ],
        circulation=CirculationGraph(
            entrance="Sala/Cozinha",
            edges={
                "Sala/Cozinha": ["Quarto", "Banheiro", "Serviço"],
                "Quarto": [],
                "Banheiro": [],
                "Serviço": [],
            },
        ),
        lot_placement=LotPlacement(
            street_facing_zone="social",
            setback_front_m=3.0,
            setback_back_m=2.0,
            setback_side_m=1.5,
            building_coverage_max=0.55,
        ),
        privacy_gradient=["Sala/Cozinha", "Quarto"],
    )


# =====================================================================
# 4. 1Q com varanda frontal — sem corredor
# =====================================================================
#
#   +------------+------+
#   |            |      |
#   |  Quarto    | Ban. |   ← fundo (exterior)
#   |  4.16×3.0  |1.24× |
#   |            |3.0   |
#   +------------+------+
#   |            |Serv. |   ← canto fundo da zona social
#   | Sala/Coz.  |1.51× |
#   | 3.89×3.6   |1.80  |
#   |            |      |
#   +------------+------+
#   |  Varanda         |   ← outdoor
#   +------------------+
#          RUA
#
#   Varanda frontal de transição social.
#   Serviço no canto da zona social, adjacente à cozinha.
#
def _1q_varanda():
    return TemplateV2(
        id="1q_varanda",
        name="1Q com Varanda",
        typology="rectangle",
        target_area_range=(35, 45),
        bedrooms=1,
        bathrooms=1,
        tags=["varanda", "transicao_social", "cozinha_integrada", "sem_corredor"],
        zones=[
            Zone("varanda", 0, -2.0, 4.0, 2.0, "width", is_outdoor=True),
            Zone("social", 0, 0, 5.4, 3.6, "both"),
            Zone("intimate", 0, 3.6, 5.4, 3.0, "both"),
        ],
        rooms=[
            RoomDef("Varanda", "varanda", "varanda",
                    0.0, 0.0, 1.0, 1.0),
            # --- Zona social 5.4×3.6 = 19.44m² ---
            # Sala: 0.72×5.4=3.888 × 3.6 = 14.00m² ≥12 ✓, min 3.6≥2.4 ✓
            RoomDef("Sala/Cozinha", "living", "social",
                    0.0, 0.0, 0.72, 1.0),
            # Serv: 0.28×5.4=1.512 × 0.50×3.6=1.80 = 2.72m² ≥2.5 ✓, min 1.512≥1.5 ✓
            RoomDef("Serviço", "service", "social",
                    0.72, 0.50, 0.28, 0.50, is_wet=True),
            # --- Zona íntima 5.4×3.0 = 16.20m² ---
            # Quarto: 0.77×5.4=4.158 × 3.0 = 12.47m² ≥9 ✓, dims 4.16×3.0 both≥3.0 ✓
            RoomDef("Quarto", "bedroom", "intimate",
                    0.0, 0.0, 0.77, 1.0),
            # Ban: 0.23×5.4=1.242 × 3.0 = 3.73m² ≥2.25 ✓, min 1.242≥1.2 ✓
            RoomDef("Banheiro", "bathroom", "intimate",
                    0.77, 0.0, 0.23, 1.0, is_wet=True),
        ],
        circulation=CirculationGraph(
            entrance="Varanda",
            edges={
                "Varanda": ["Sala/Cozinha"],
                "Sala/Cozinha": ["Quarto", "Banheiro", "Serviço"],
                "Quarto": [],
                "Banheiro": [],
                "Serviço": [],
            },
        ),
        lot_placement=LotPlacement(
            street_facing_zone="varanda",
            setback_front_m=3.0,
            setback_back_m=2.0,
            setback_side_m=1.5,
            building_coverage_max=0.50,
        ),
        privacy_gradient=["Varanda", "Sala/Cozinha", "Quarto"],
    )
