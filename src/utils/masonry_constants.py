"""
Constantes normativas para projeto de alvenaria estrutural.

Referências:
- NBR 15961-1:2011 — Alvenaria estrutural — Blocos de concreto — Projeto
- NBR 15575:2013 — Edificações habitacionais — Desempenho
- NBR 6120:2019 — Ações para o cálculo de estruturas
- NBR 10837:1989 — Alvenaria estrutural (legacy, still widely referenced)
"""

# ============================================================================
# MODULAÇÃO — NBR 15961-1
# ============================================================================

# Módulo horizontal para bloco 14cm (bloco + junta = 15cm)
MODULO_B14 = 0.15  # m

# Módulo horizontal para bloco 19cm (bloco + junta = 20cm)
MODULO_B19 = 0.20  # m

# Espessura da junta de argamassa
JUNTA_ARGAMASSA = 0.01  # m (10mm)

# Dimensões reais do bloco 14cm: 14 x 19 x 39 cm (largura x altura x comprimento)
BLOCO_14_DIMS = (0.14, 0.19, 0.39)

# Dimensões reais do bloco 19cm: 19 x 19 x 39 cm
BLOCO_19_DIMS = (0.19, 0.19, 0.39)

# Meio-bloco 14cm: 14 x 19 x 19 cm
MEIO_BLOCO_14 = (0.14, 0.19, 0.19)

# Meio-bloco 19cm: 19 x 19 x 19 cm
MEIO_BLOCO_19 = (0.19, 0.19, 0.19)

# Canaleta (bloco-U) — mesmas dimensões do bloco inteiro
# Usado em cintas e vergas para receber armadura e graute


# ============================================================================
# ÁREAS MÍNIMAS POR CÔMODO — NBR 15575:2013 Tabela F.1
# ============================================================================

# Dict: room_type -> area_minima_m2
MIN_ROOM_AREAS = {
    "bedroom": 9.00,   # 3×3m mínimo
    "living": 12.00,
    "kitchen": 4.00,
    "bathroom": 2.25,   # 1.5×1.5m mínimo funcional
    "service": 2.50,   # área de serviço
    "circulation": 1.50,
    "garage": 12.00,
    "varanda": 2.00,
}

# Dimensão mínima de qualquer lado do cômodo (m) — NBR 15575
MIN_ROOM_DIMENSION = {
    "bedroom": 3.00,   # quarto mínimo 3×3m
    "living": 2.40,
    "kitchen": 1.80,
    "bathroom": 1.20,  # mínimo funcional (ideal 1.5m)
    "service": 1.50,
    "circulation": 0.90,
    "garage": 2.50,
    "varanda": 1.00,
}

# Area maxima por tipo de comodo (m²) — evita comodos desproporcionais
# Em casas <60m², area e recurso escasso; cada comodo tem um teto
MAX_ROOM_AREAS = {
    "bathroom": 4.00,
    "circulation": 3.50,
    "service": 4.00,
    "kitchen": 7.00,
    "garage": 18.00,
    # bedroom e living nao tem cap — usam area residual
}

# Proporcao maxima (lado maior / lado menor) — aspect ratio
# Acima disso o comodo fica impossivel de mobiliar
MAX_ASPECT_RATIO = {
    "bedroom": 2.0,
    "living": 2.2,
    "kitchen": 2.0,
    "bathroom": 2.0,
    "service": 2.0,
    "circulation": 4.0,  # corredor pode ser alongado
    "garage": 3.0,
}

# Percentual alvo da area total por tipo de comodo (para casas 40-70m²)
# Usado para redistribuir area quando um comodo esta desproporcional
TARGET_AREA_RATIO = {
    "bedroom": 0.18,      # cada quarto ~18% da area total
    "living": 0.28,       # sala/cozinha integrada ~28%
    "kitchen": 0.10,      # cozinha separada ~10%
    "bathroom": 0.06,     # ~6%
    "service": 0.06,      # ~6%
    "circulation": 0.05,  # ~5%
    "garage": 0.20,       # ~20%
}


# ============================================================================
# RESISTÊNCIA DOS BLOCOS — NBR 15961-1 Tabela 1
# ============================================================================

# Resistências características disponíveis (MPa)
BLOCK_STRENGTHS_MPA = [4.5, 6.0, 8.0, 10.0, 12.0, 16.0]

# Fator de eficiência prisma/bloco η — NBR 15961-1 §7.3.2
# fp = η × fbk (resistência do prisma = η × resistência do bloco)
ETA_PRISMA = 0.70  # conservador para blocos de concreto vazados

# Coeficiente de minoração da alvenaria — NBR 15961-1 §7.4
GAMMA_M = 2.0  # γm para combinação normal

# Peso específico da alvenaria de blocos de concreto (kN/m³)
# Blocos vazados grauteados parcialmente ≈ 14 kN/m³
GAMMA_ALVENARIA = 14.0

# Peso específico do concreto para graute (kN/m³)
GAMMA_GRAUTE = 24.0


# ============================================================================
# CAPACIDADE DE CARGA DE PAREDES — NBR 15961-1 simplificado
# ============================================================================

# Tensão admissível simplificada (kN/m²) por fbk
# Rd = (η × fbk) / γm × t × 1m  → kN/m (por metro linear de parede)
# Para t=14cm:
#   fbk=4.5 → Rd = 0.70×4500/2.0 × 0.14 = 220.5 kN/m
#   fbk=6.0 → Rd = 0.70×6000/2.0 × 0.14 = 294.0 kN/m
#   fbk=8.0 → Rd = 0.70×8000/2.0 × 0.14 = 392.0 kN/m

WALL_CAPACITY_KN_PER_M = {
    # (fbk_mpa, thickness_cm) -> capacity kN/m
    (4.5, 14): 220.5,
    (6.0, 14): 294.0,
    (8.0, 14): 392.0,
    (10.0, 14): 490.0,
    (12.0, 14): 588.0,
    (16.0, 14): 784.0,
    (4.5, 19): 299.3,
    (6.0, 19): 399.0,
    (8.0, 19): 532.0,
    (10.0, 19): 665.0,
    (12.0, 19): 798.0,
    (16.0, 19): 1064.0,
}


# ============================================================================
# CARGAS TÍPICAS — NBR 6120:2019
# ============================================================================

# Peso próprio de laje maciça de concreto por cm de espessura (kN/m²/cm)
PP_LAJE_POR_CM = 0.25  # γc × 0.01 = 25 × 0.01

# Sobrecarga de uso residencial (kN/m²) — NBR 6120:2019 Tab. 2
Q_RESIDENCIAL = 1.5

# Peso próprio da cobertura — telha cerâmica + madeiramento (kN/m²)
PP_COBERTURA_CERAMICA = 1.0

# Peso próprio da cobertura — telha fibrocimento (kN/m²)
PP_COBERTURA_FIBROCIMENTO = 0.5

# Sobrecarga na cobertura (kN/m²) — NBR 6120:2019
Q_COBERTURA = 0.50

# Peso do revestimento (kN/m²) — argamassa + piso cerâmico
PP_REVESTIMENTO = 1.0

# Peso de contra-piso (kN/m²) — ~4cm de argamassa
PP_CONTRAPISO = 1.0

# Coeficiente de majoração de ações — NBR 15961-1
GAMMA_F = 1.4

# Coeficiente de combinação para ação variável principal
PSI_0 = 0.5  # NBR 8681 Tabela 6 — edificações residenciais


# ============================================================================
# ABERTURAS PADRÃO MCMV — Portaria 660/2018 + NBR 15575
# ============================================================================

# Portas (largura × altura em metros)
DOOR_SIZES = {
    "entrance": (0.90, 2.10),
    "internal": (0.80, 2.10),
    "bathroom": (0.70, 2.10),
    "service": (0.80, 2.10),
    "garage": (2.50, 2.10),
}

# Vehicle access and garage dimensions (meters)
VEHICLE_ACCESS = {
    "min_garage_width_m": 3.00,        # single car, NBR 15575
    "min_garage_depth_m": 5.00,        # min depth for 1 car
    "double_garage_width_m": 5.50,     # 2 cars side by side
    "min_driveway_width_m": 2.80,      # min approach lane width
    "min_turning_radius_m": 5.00,      # passenger car turning radius
    "garage_door_width_m": 2.50,       # single garage door
    "garage_door_double_m": 4.80,      # double garage door
    "setback_driveway_min_m": 3.00,    # min frontal setback for maneuver area
    "car_length_m": 4.50,              # reference sedan length
    "car_width_m": 1.80,               # reference sedan width
}

# Janelas (largura × altura × peitoril em metros)
WINDOW_SIZES = {
    "bedroom": (1.20, 1.20, 1.00),
    "living": (1.50, 1.20, 1.00),
    "kitchen": (1.20, 1.00, 1.20),
    "bathroom": (0.60, 0.60, 1.60),
    "service": (0.80, 0.80, 1.40),
}


# ============================================================================
# VERGAS E CONTRAVERGAS — NBR 15961-1 §8.2.3
# ============================================================================

# Apoio mínimo da verga além da abertura (cm) — cada lado
VERGA_APOIO_MIN_CM = 30  # 30cm ou 2 blocos de cada lado

# Seção mínima da verga: largura = espessura da parede, altura ≥ 15cm (1 fiada)
VERGA_ALTURA_MIN = 0.15  # m

# Armadura mínima de verga — 2 barras de 8mm para vãos ≤ 1.20m
VERGA_ARMADURA_PADRAO = "2φ8mm"

# Contraverga: mesma seção abaixo da janela para vãos > 0.60m
CONTRAVERGA_VAO_MIN = 0.60  # m — acima desse vão, contraverga é obrigatória


# ============================================================================
# CINTAS DE AMARRAÇÃO — NBR 15961-1 §8.2.1
# ============================================================================

# Cinta de respaldo (topo da parede, sob a laje)
CINTA_RESPALDO_ALTURA = 0.20  # m (1 fiada de canaleta)

# Cinta intermediária a cada 3m de altura (para edificações > 1 pavimento)
CINTA_INTERMEDIARIA_INTERVALO = 3.0  # m

# Armadura mínima das cintas
CINTA_ARMADURA_MIN = "4φ8mm + estr. φ5c/20cm"

# Seção mínima da cinta = largura da parede × 20cm (1 fiada de canaleta)


# ============================================================================
# FUNDAÇÕES — Sapata corrida para MCMV (NBR 6122:2019)
# ============================================================================

# Capacidade de suporte do solo padrão conservador (kPa)
SOLO_CAPACIDADE_PADRAO = 100.0

# Largura mínima da sapata corrida (m) — boa prática
SAPATA_LARGURA_MIN = 0.40

# Profundidade mínima de assentamento (m) — NBR 6122
SAPATA_PROFUNDIDADE_MIN = 0.40

# Altura mínima da base da sapata (m)
SAPATA_ALTURA_MIN = 0.20

# Armadura padrão de sapata para MCMV
SAPATA_ARMADURA_PADRAO = "φ8c/20 ambas direções"

# Radier — espessura mínima (m)
RADIER_ESPESSURA_MIN = 0.12

# Taxa mínima de armadura do radier
RADIER_ARMADURA_PADRAO = "tela Q-138 (φ4.2c/10)"


# ============================================================================
# LAJE PRÉ-MOLDADA (Padrão MCMV) — NBR 14859-1
# ============================================================================

# Espessura total típica (vigota + capeamento) em cm
LAJE_PRE_ESPESSURA = 12  # cm

# Peso próprio médio de laje pré-moldada (kN/m²) — catálogos fabricantes
PP_LAJE_PRE = 1.80  # kN/m² para h=12cm (vigota + EPS + capeamento 4cm)


# ============================================================================
# SOLUÇÕES CONSTRUTIVAS — Custo e desempenho por sistema
# ============================================================================

# Estimativas de custo relativo (1.0 = referência base sapata+cerâmica+madeira)
# Fonte: SINAPI, CUB médio regional 2024, práticas construtivas MCMV

FOUNDATION_SYSTEMS = {
    "sapata_corrida": {
        "name": "Sapata Corrida",
        "cost_ratio": 1.0,
        "execution_time_ratio": 1.0,
        "description": "Fundação linear sob paredes. Boa para solos firmes.",
        "best_for": "solo firme (σ ≥ 100kPa), terreno plano",
        "rebar": "φ8c/20 ambas direções",
        "min_width_m": 0.40,
        "min_depth_m": 0.40,
    },
    "radier": {
        "name": "Radier",
        "cost_ratio": 0.75,  # 25% mais barato que sapata
        "execution_time_ratio": 0.60,  # 40% mais rápido
        "description": "Laje de fundação. Econômico, rápido, distribui cargas.",
        "best_for": "solos fracos, terrenos úmidos, obras econômicas",
        "rebar": "tela Q-138 (φ4.2c/10)",
        "min_thickness_m": 0.12,
    },
}

ROOF_SYSTEMS = {
    "ceramic": {
        "name": "Telha Cerâmica",
        "material": "Telha cerâmica + madeiramento",
        "cost_ratio": 1.0,
        "weight_kn_m2": 1.0,
        "thermal_rating": "media",
        "description": "Tradicional. Boa estética, peso elevado.",
        "min_slope_pct": 30,
    },
    "fiber_cement": {
        "name": "Fibrocimento",
        "material": "Telha fibrocimento + madeiramento leve",
        "cost_ratio": 0.65,
        "weight_kn_m2": 0.50,
        "thermal_rating": "baixa",
        "description": "Econômico, leve. Desempenho térmico inferior.",
        "min_slope_pct": 10,
    },
    "sandwich": {
        "name": "Telha Sanduíche",
        "material": "Telha sanduíche (aço+EPS/PIR+aço)",
        "cost_ratio": 0.80,
        "weight_kn_m2": 0.25,
        "thermal_rating": "alta",
        "description": "Econômico, leve, excelente isolamento térmico.",
        "best_for": "obras econômicas, galpões, shed",
        "min_slope_pct": 5,
    },
    "metal": {
        "name": "Telha Metálica",
        "material": "Telha galvanizada trapézio",
        "cost_ratio": 0.55,
        "weight_kn_m2": 0.15,
        "thermal_rating": "muito_baixa",
        "description": "Mais barato, mais leve. Sem isolamento térmico.",
        "min_slope_pct": 5,
    },
}

STRUCTURE_SYSTEMS = {
    "masonry": {
        "name": "Alvenaria Estrutural",
        "cost_ratio": 1.0,
        "description": "Blocos de concreto estruturais. Paredes = estrutura.",
        "max_floors": 5,
        "block_sizes_cm": [14, 19],
    },
    "self_supporting": {
        "name": "Autoportante",
        "cost_ratio": 0.90,
        "description": "Estrutura independente (pilares+vigas) com vedação em bloco.",
        "max_floors": 10,
        "block_sizes_cm": [9, 14],
    },
}

# Combinação econômica recomendada (MCMV Faixa 1)
ECONOMY_PRESET = {
    "foundation": "radier",
    "roof_style": "shed",
    "roof_material": "sandwich",
    "structure": "masonry",
    "block_size": "14",
    "ceiling_height_m": 2.60,
    "cost_savings_pct": 20,  # economia estimada vs. padrão
    "description": "Radier + Alvenaria Estrutural B14 + Telhado Shed Sanduíche",
}
