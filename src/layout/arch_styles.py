"""Architectural design principles and style vocabulary.

This module encodes architectural knowledge so the layout solver can
understand and apply style-specific design decisions when the user
selects a style or describes desired characteristics.

Covers:
- Architectural styles (modern, colonial, minimal, tropical, etc.)
- Design principles (proportion, rhythm, hierarchy, etc.)
- Room relationship rules per style
- Facade characteristics
- Material palettes
- Roof forms
- Window/opening patterns

Reference: Neufert, Francis D.K. Ching, Brazilian colonial architecture,
modernist principles (Corbusier, Niemeyer), tropical architecture (Lúcio Costa).
"""

from typing import Dict, List, Any


# =============================================================================
# ARCHITECTURAL STYLES — Visual language and spatial organization
# =============================================================================

STYLES: Dict[str, Dict[str, Any]] = {
    "modern": {
        "name": "Moderno",
        "description": "Linhas retas, volumes puros, grandes aberturas. Integração interior-exterior.",
        "principles": [
            "Planta livre — mínimo de paredes internas fixas",
            "Grandes aberturas com vidro (janelas piso-teto quando possível)",
            "Telhado plano ou com inclinação mínima (laje impermeabilizada)",
            "Integração sala-cozinha como espaço contínuo",
            "Varanda como transição interior-exterior",
            "Volumetria limpa — caixa retangular ou composição de volumes",
        ],
        "room_rules": {
            "living": {
                "min_aspect_ratio": 0.6,
                "prefer_open_to": ["kitchen"],
                "window_ratio": 0.25,  # 25% da parede externa = vidro
                "prefer_orientation": "afternoon_sun",
            },
            "bedroom": {
                "min_aspect_ratio": 0.65,
                "prefer_orientation": "morning_sun",
                "window_ratio": 0.20,
                "privacy": "high",
            },
            "kitchen": {
                "min_aspect_ratio": 0.5,
                "prefer_adjacent_to": ["service", "living"],
                "ventilation": "cross",
            },
            "bathroom": {
                "window_type": "high_basculante",
                "min_area_m2": 2.8,
            },
        },
        "facade": {
            "materials": ["reboco liso branco", "concreto aparente", "vidro temperado"],
            "colors": ["branco", "cinza claro", "madeira natural"],
            "fenestration": "grandes panos de vidro, esquadrias de alumínio preto",
            "roof_preference": ["flat", "gable"],
            "overhang_m": 0.60,  # beiral para proteção solar
        },
        "proportions": {
            "golden_ratio_preference": True,
            "symmetry": "asymmetric",  # composição assimétrica
            "ceiling_height_min": 2.80,
        },
    },

    "colonial": {
        "name": "Colonial",
        "description": "Telhado cerâmico aparente, varandas, janelas com verga em arco. Tradição luso-brasileira.",
        "principles": [
            "Telhado cerâmico com beiral generoso (60-80cm)",
            "Varandas frontais e/ou laterais",
            "Janelas com proporção vertical (mais altas que largas)",
            "Simetria na fachada principal",
            "Paredes espessas com reboco texturizado",
            "Cores quentes — branco com detalhes em azul, amarelo ou terracota",
        ],
        "room_rules": {
            "living": {
                "min_aspect_ratio": 0.7,
                "prefer_orientation": "front",
                "window_ratio": 0.15,
                "prefer_symmetry": True,
            },
            "bedroom": {
                "min_aspect_ratio": 0.7,
                "prefer_orientation": "lateral",
                "window_ratio": 0.12,
                "privacy": "medium",
            },
            "kitchen": {
                "prefer_orientation": "back",
                "prefer_adjacent_to": ["service"],
                "ventilation": "natural",
            },
        },
        "facade": {
            "materials": ["reboco texturizado", "telha cerâmica colonial", "madeira maciça"],
            "colors": ["branco", "amarelo ocre", "azul colonial", "terracota"],
            "fenestration": "janelas verticais com bandeira, venezianas de madeira",
            "roof_preference": ["gable", "hip"],
            "overhang_m": 0.80,
        },
        "proportions": {
            "golden_ratio_preference": False,
            "symmetry": "symmetric",  # fachada simétrica
            "ceiling_height_min": 2.80,
        },
    },

    "minimal": {
        "name": "Minimalista",
        "description": "Máxima simplicidade. Poucos materiais, cores neutras, sem ornamentação.",
        "principles": [
            "Menos é mais — eliminar todo elemento não essencial",
            "Paleta de no máximo 3 materiais",
            "Cores neutras — branco, cinza, concreto natural",
            "Aberturas precisas e estratégicas",
            "Espaços fluidos sem barreiras visuais",
            "Iluminação natural como elemento de projeto",
        ],
        "room_rules": {
            "living": {
                "min_aspect_ratio": 0.5,
                "prefer_open_to": ["kitchen", "circulation"],
                "window_ratio": 0.30,
                "prefer_orientation": "best_view",
            },
            "bedroom": {
                "min_aspect_ratio": 0.7,
                "window_ratio": 0.15,
                "privacy": "high",
                "prefer_orientation": "morning_sun",
            },
        },
        "facade": {
            "materials": ["concreto aparente", "reboco branco", "aço corten"],
            "colors": ["branco puro", "cinza concreto", "preto"],
            "fenestration": "aberturas recortadas na massa, sem molduras",
            "roof_preference": ["flat"],
            "overhang_m": 0.30,
        },
        "proportions": {
            "golden_ratio_preference": True,
            "symmetry": "asymmetric",
            "ceiling_height_min": 2.70,
        },
    },

    "tropical": {
        "name": "Tropical",
        "description": "Adaptado ao clima quente-úmido. Ventilação cruzada, proteção solar, integração com jardim.",
        "principles": [
            "Ventilação cruzada em todos os ambientes",
            "Proteção solar — brises, pergolados, varandas profundas",
            "Cobogós (elementos vazados) para ventilação com privacidade",
            "Telhado com inclinação adequada para chuvas tropicais",
            "Integração com área externa — quintal, jardim, varanda",
            "Materiais que respiram — cerâmica, madeira, tijolo aparente",
        ],
        "room_rules": {
            "living": {
                "min_aspect_ratio": 0.5,
                "prefer_open_to": ["garden"],
                "window_ratio": 0.30,
                "ventilation": "cross",
                "prefer_orientation": "afternoon_breeze",
            },
            "bedroom": {
                "min_aspect_ratio": 0.6,
                "window_ratio": 0.20,
                "ventilation": "cross",
                "prefer_orientation": "morning_sun",
            },
            "kitchen": {
                "ventilation": "cross",
                "prefer_adjacent_to": ["service", "garden"],
            },
        },
        "facade": {
            "materials": ["tijolo aparente", "madeira", "cobogó cerâmico", "telha cerâmica"],
            "colors": ["terracota", "branco", "cores da terra"],
            "fenestration": "grandes aberturas com proteção solar, venezianas",
            "roof_preference": ["gable", "hip"],
            "overhang_m": 1.00,  # beiral generoso
        },
        "proportions": {
            "golden_ratio_preference": False,
            "symmetry": "organic",
            "ceiling_height_min": 3.00,
        },
    },

    "contemporary": {
        "name": "Contemporâneo",
        "description": "Mix de materiais, volumes articulados, adaptado ao contexto local.",
        "principles": [
            "Composição de volumes com diferentes alturas e recuos",
            "Mix de materiais — concreto + madeira + metal + vidro",
            "Iluminação zenital (clarabóias, sheds)",
            "Permeabilidade visual — interior se conecta ao exterior",
            "Sustentabilidade — aproveitamento de água, energia solar",
            "Adaptação ao terreno — respeitar topografia natural",
        ],
        "room_rules": {
            "living": {
                "min_aspect_ratio": 0.5,
                "prefer_open_to": ["kitchen", "garden"],
                "window_ratio": 0.25,
                "double_height": "optional",
            },
            "bedroom": {
                "min_aspect_ratio": 0.65,
                "window_ratio": 0.18,
                "privacy": "high",
            },
        },
        "facade": {
            "materials": ["concreto", "madeira certificada", "vidro", "aço"],
            "colors": ["neutros com pontos de cor", "cinza", "madeira"],
            "fenestration": "variada — panos de vidro + aberturas recortadas",
            "roof_preference": ["flat", "gable"],
            "overhang_m": 0.50,
        },
        "proportions": {
            "golden_ratio_preference": True,
            "symmetry": "asymmetric",
            "ceiling_height_min": 2.80,
        },
    },
}


# =============================================================================
# DESIGN PRINCIPLES — Universal architectural rules
# =============================================================================

DESIGN_PRINCIPLES = {
    "solar_orientation": {
        "rule": "Ambientes de permanência prolongada devem receber insolação adequada",
        "details": {
            "bedrooms": "Sol da manhã (nascente/leste) — aquecimento suave para despertar",
            "living": "Sol da tarde (poente/oeste) — aproveitamento no final do dia",
            "kitchen": "Ventilação prioritária sobre insolação",
            "bathroom": "Evitar insolação direta — posição interna ou norte/sul",
            "service": "Insolação para secagem — qualquer orientação com sol",
        },
        "brazil_specifics": {
            "hemisphere": "south",
            "note": "No hemisfério sul, a fachada norte recebe mais sol ao longo do ano",
            "summer_sun": "Sol mais alto — proteção por beirais horizontais",
            "winter_sun": "Sol mais baixo — permitir entrada nos ambientes",
        },
    },

    "ventilation": {
        "rule": "Ventilação cruzada é essencial em clima tropical brasileiro",
        "details": {
            "cross_ventilation": "Aberturas em paredes opostas ou adjacentes",
            "stack_effect": "Abertura baixa na entrada de ar, alta na saída",
            "min_opening_area": "1/6 da área do piso (NBR 15575 para dormitórios)",
            "prevailing_wind": "Identificar vento predominante da região",
        },
    },

    "privacy_zoning": {
        "rule": "Zoneamento funcional — separar áreas sociais, íntimas e de serviço",
        "zones": {
            "social": {
                "rooms": ["living", "kitchen"],
                "position": "Próximo à entrada e à rua",
                "noise_tolerance": "alta",
            },
            "intimate": {
                "rooms": ["bedroom", "bathroom"],
                "position": "Afastado da rua, interior do lote",
                "noise_tolerance": "baixa",
            },
            "service": {
                "rooms": ["service", "garage"],
                "position": "Lateral ou fundos",
                "noise_tolerance": "alta",
            },
        },
    },

    "circulation": {
        "rule": "Circulação eficiente — mínima área de corredor, máxima conectividade",
        "details": {
            "min_corridor_width": 0.90,   # metros (NBR 15575)
            "max_corridor_ratio": 0.15,    # máx 15% da área total
            "dead_end_forbidden": True,
            "kitchen_living_connection": "Direta, sem corredor intermediário",
        },
    },

    "proportions": {
        "rule": "Proporções harmônicas para conforto visual e funcional",
        "details": {
            "golden_ratio": 1.618,
            "max_room_aspect": 2.5,        # comprimento/largura máximo
            "min_room_dimension": 2.40,     # metros
            "min_window_height_ratio": 0.4, # janela = 40% da altura da parede
            "ceiling_proportion": "Pé-direito proporcional ao maior vão do ambiente",
        },
    },

    "furniture_fit": {
        "rule": "Ambientes devem comportar mobiliário padrão",
        "standard_furniture": {
            "bedroom": {
                "single_bed": (0.90, 1.90),      # largura × comprimento
                "double_bed": (1.40, 1.90),
                "queen_bed": (1.60, 2.00),
                "wardrobe": (0.55, 1.60),         # profundidade × largura
                "nightstand": (0.40, 0.40),
                "clearance_min": 0.60,             # circulação mínima ao redor
            },
            "living": {
                "sofa_3seat": (0.85, 2.00),
                "armchair": (0.85, 0.85),
                "coffee_table": (0.60, 1.10),
                "tv_wall": (0.40, 1.20),           # profundidade × largura
                "dining_4": (0.80, 1.20),           # mesa 4 lugares
                "dining_6": (0.90, 1.60),
                "clearance_min": 0.60,
            },
            "kitchen": {
                "counter_depth": 0.60,
                "counter_min_length": 2.40,
                "fridge_space": (0.70, 0.70),
                "stove_space": (0.60, 0.60),
                "sink_space": (0.60, 0.55),
                "circulation_front": 0.90,          # espaço frontal para abrir armários
            },
            "bathroom": {
                "toilet": (0.40, 0.65),
                "sink": (0.50, 0.45),
                "shower": (0.80, 0.80),
                "clearance_front": 0.60,
            },
        },
    },
}


# =============================================================================
# ROOF FORMS — Geometry and style association
# =============================================================================

ROOF_FORMS = {
    "gable": {
        "name": "Duas águas",
        "description": "Forma clássica com cumeeira central",
        "typical_slope_deg": 25,  # graus
        "ridge_height_factor": 0.3,  # % da menor dimensão
        "overhang_m": 0.60,
        "styles": ["colonial", "tropical", "contemporary"],
        "material": "telha cerâmica ou concreto",
    },
    "hip": {
        "name": "Quatro águas",
        "description": "Quatro planos inclinados, visual mais suave",
        "typical_slope_deg": 22,
        "ridge_height_factor": 0.25,
        "overhang_m": 0.70,
        "styles": ["colonial", "tropical"],
        "material": "telha cerâmica ou concreto",
    },
    "flat": {
        "name": "Laje plana",
        "description": "Cobertura plana com impermeabilização. Visual moderno.",
        "typical_slope_deg": 2,  # caimento mínimo
        "ridge_height_factor": 0.0,
        "overhang_m": 0.30,
        "styles": ["modern", "minimal", "contemporary"],
        "material": "laje impermeabilizada + proteção mecânica",
    },
    "butterfly": {
        "name": "Borboleta",
        "description": "V invertido — captação de água pluvial central",
        "typical_slope_deg": 10,
        "ridge_height_factor": -0.15,  # negativo = inverso
        "overhang_m": 0.50,
        "styles": ["modern", "contemporary"],
        "material": "laje ou telha metálica",
    },
    "shed": {
        "name": "Uma água (shed)",
        "description": "Plano único inclinado — iluminação zenital possível",
        "typical_slope_deg": 15,
        "ridge_height_factor": 0.20,
        "overhang_m": 0.50,
        "styles": ["modern", "minimal", "contemporary"],
        "material": "telha metálica ou laje",
    },
}


# =============================================================================
# CLIMATE ZONES — NBR 15220 bioclimatic zoning
# =============================================================================

CLIMATE_ZONES_BR = {
    "Z1": {
        "name": "Subtropical frio",
        "cities": ["Curitiba", "Lages", "São Joaquim"],
        "strategies": ["aquecimento passivo", "inércia térmica", "paredes pesadas"],
        "ventilation": "controlada — evitar correntes frias",
        "window_orientation": "fachada norte para captação solar",
    },
    "Z2": {
        "name": "Subtropical",
        "cities": ["São Paulo", "Porto Alegre", "Florianópolis"],
        "strategies": ["ventilação cruzada no verão", "inércia térmica"],
        "ventilation": "cruzada seletiva",
        "window_orientation": "norte e leste — evitar oeste",
    },
    "Z3": {
        "name": "Tropical de altitude",
        "cities": ["Belo Horizonte", "Goiânia", "Brasília"],
        "strategies": ["ventilação cruzada", "sombreamento"],
        "ventilation": "cruzada permanente",
        "window_orientation": "norte com proteção solar",
    },
    "Z5": {
        "name": "Tropical quente-seco",
        "cities": ["Petrolina", "Teresina", "Montes Claros"],
        "strategies": ["massa térmica", "ventilação noturna", "sombreamento"],
        "ventilation": "noturna — fechado durante o dia",
        "window_orientation": "norte e sul com brises",
    },
    "Z7": {
        "name": "Tropical quente-úmido",
        "cities": ["Manaus", "Belém", "São Luís"],
        "strategies": ["ventilação permanente", "sombreamento total", "coberturas ventiladas"],
        "ventilation": "cruzada permanente — máxima abertura",
        "window_orientation": "todas com proteção solar (beiral + brise)",
    },
    "Z8": {
        "name": "Tropical litorâneo",
        "cities": ["Salvador", "Recife", "Rio de Janeiro", "Fortaleza"],
        "strategies": ["ventilação cruzada", "brises", "cobogós"],
        "ventilation": "cruzada — aproveitar brisa marítima",
        "window_orientation": "mar/vento predominante, evitar oeste",
    },
}


# =============================================================================
# HELPER — Get style config or fallback
# =============================================================================

# =============================================================================
# REGIONAL BUILDING REGULATIONS — Min room areas, structural standards, codes
# =============================================================================

REGIONAL_REGULATIONS: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # BRAZIL
    # -------------------------------------------------------------------------
    "BR": {
        "name": "Brasil",
        "region": "latin_america",
        "hemisphere": "south",
        "codes": {
            "structural_masonry": "NBR 15961-1:2011",
            "performance": "NBR 15575:2013",
            "concrete": "NBR 6118:2023",
            "foundations": "NBR 6122:2022",
            "loads": "NBR 6120:2019",
            "thermal": "NBR 15220:2005",
            "accessibility": "NBR 9050:2020",
            "fire": "NBR 14432:2001",
            "architectural_drawing": "NBR 6492:1994",
        },
        "min_room_areas_m2": {
            "bedroom": 9.0,
            "living": 12.0,
            "kitchen": 4.0,
            "bathroom": 2.25,
            "service": 2.5,
            "circulation": 1.5,
            "varanda": 2.0,
        },
        "min_room_dimensions_m": {
            "bedroom": 3.00,
            "living": 2.40,
            "kitchen": 1.50,
            "bathroom": 1.20,
            "varanda": 1.00,
        },
        "min_ceiling_height_m": 2.50,
        "standard_ceiling_m": 2.80,
        "min_corridor_width_m": 0.90,
        "min_door_height_m": 2.10,
        "setbacks": {
            "front_m": 3.0,
            "rear_m": 2.0,
            "side_m": 1.50,
            "note": "Varies by municipality (Código de Obras local)",
        },
        "masonry_modules_cm": [14, 19],
        "block_strengths_mpa": [4.5, 6.0, 8.0, 10.0, 12.0],
        "seismic_zone": "low",
        "social_housing": {
            "program": "Minha Casa Minha Vida (MCMV)",
            "area_range_m2": (40, 70),
            "max_floors": 2,
        },
        "unit_system": "metric",
        "currency": "BRL",
    },

    # -------------------------------------------------------------------------
    # MEXICO
    # -------------------------------------------------------------------------
    "MX": {
        "name": "México",
        "region": "latin_america",
        "hemisphere": "north",
        "codes": {
            "structural": "NTC-2017 (Normas Técnicas Complementarias CDMX)",
            "masonry": "NTC-Mampostería 2017",
            "concrete": "NTC-Concreto 2017",
            "seismic": "NTC-Sismo 2017",
            "general": "Reglamento de Construcciones para el DF",
        },
        "min_room_areas_m2": {
            "bedroom": 7.0,
            "living": 7.0,
            "kitchen": 3.0,
            "bathroom": 2.0,
            "service": 2.5,
        },
        "min_room_dimensions_m": {
            "bedroom": 2.20,
            "living": 2.40,
            "kitchen": 1.50,
            "bathroom": 1.10,
        },
        "min_ceiling_height_m": 2.30,
        "standard_ceiling_m": 2.60,
        "min_corridor_width_m": 0.90,
        "min_door_height_m": 2.10,
        "setbacks": {
            "front_m": 3.0,
            "rear_m": 3.0,
            "side_m": 1.50,
        },
        "masonry_modules_cm": [12, 15, 20],
        "block_strengths_mpa": [3.5, 6.0, 10.0, 15.0],
        "seismic_zone": "high",
        "social_housing": {
            "program": "INFONAVIT / CONAVI",
            "area_range_m2": (38, 65),
            "max_floors": 2,
        },
        "unit_system": "metric",
        "currency": "MXN",
    },

    # -------------------------------------------------------------------------
    # COLOMBIA
    # -------------------------------------------------------------------------
    "CO": {
        "name": "Colombia",
        "region": "latin_america",
        "hemisphere": "north",
        "codes": {
            "seismic": "NSR-10 (Norma Sismo Resistente 2010)",
            "structural": "NSR-10 Título D (Mampostería Estructural)",
            "concrete": "NSR-10 Título C",
            "general": "POT (Plan de Ordenamiento Territorial)",
        },
        "min_room_areas_m2": {
            "bedroom": 7.5,
            "living": 9.0,
            "kitchen": 3.6,
            "bathroom": 2.0,
            "service": 2.0,
        },
        "min_room_dimensions_m": {
            "bedroom": 2.20,
            "living": 2.60,
            "kitchen": 1.50,
            "bathroom": 1.00,
        },
        "min_ceiling_height_m": 2.30,
        "standard_ceiling_m": 2.50,
        "min_corridor_width_m": 0.90,
        "min_door_height_m": 2.00,
        "setbacks": {
            "front_m": 3.0,
            "rear_m": 3.0,
            "side_m": 2.0,
        },
        "masonry_modules_cm": [10, 12, 15, 20],
        "block_strengths_mpa": [5.0, 7.5, 10.0, 15.0],
        "seismic_zone": "high",
        "social_housing": {
            "program": "VIS (Vivienda de Interés Social)",
            "area_range_m2": (35, 70),
            "max_floors": 2,
        },
        "unit_system": "metric",
        "currency": "COP",
    },

    # -------------------------------------------------------------------------
    # ARGENTINA
    # -------------------------------------------------------------------------
    "AR": {
        "name": "Argentina",
        "region": "latin_america",
        "hemisphere": "south",
        "codes": {
            "structural": "CIRSOC 501 (Mampostería)",
            "seismic": "INPRES-CIRSOC 103",
            "concrete": "CIRSOC 201",
            "thermal": "IRAM 11603 / 11604 / 11605",
            "general": "Código de Edificación (varies by province)",
        },
        "min_room_areas_m2": {
            "bedroom": 9.0,
            "living": 12.0,
            "kitchen": 3.5,
            "bathroom": 2.5,
            "service": 2.5,
        },
        "min_room_dimensions_m": {
            "bedroom": 2.50,
            "living": 2.60,
            "kitchen": 1.50,
            "bathroom": 1.20,
        },
        "min_ceiling_height_m": 2.60,
        "standard_ceiling_m": 2.70,
        "min_corridor_width_m": 0.90,
        "min_door_height_m": 2.00,
        "setbacks": {
            "front_m": 3.0,
            "rear_m": 4.0,
            "side_m": 1.50,
        },
        "masonry_modules_cm": [12, 18, 20],
        "block_strengths_mpa": [4.0, 6.0, 8.0, 13.0],
        "seismic_zone": "medium",
        "social_housing": {
            "program": "PROCREAR / Plan Federal",
            "area_range_m2": (40, 70),
            "max_floors": 2,
        },
        "unit_system": "metric",
        "currency": "ARS",
    },

    # -------------------------------------------------------------------------
    # CHILE
    # -------------------------------------------------------------------------
    "CL": {
        "name": "Chile",
        "region": "latin_america",
        "hemisphere": "south",
        "codes": {
            "structural": "NCh 1928 (Albañilería Armada)",
            "seismic": "NCh 433 (Diseño Sísmico de Edificios)",
            "concrete": "NCh 430",
            "thermal": "NCh 1079 (Zonificación climático-habitacional)",
            "general": "OGUC (Ordenanza General de Urbanismo y Construcciones)",
        },
        "min_room_areas_m2": {
            "bedroom": 8.0,
            "living": 11.0,
            "kitchen": 3.5,
            "bathroom": 2.5,
            "service": 2.0,
        },
        "min_room_dimensions_m": {
            "bedroom": 2.50,
            "living": 2.80,
            "kitchen": 1.50,
            "bathroom": 1.10,
        },
        "min_ceiling_height_m": 2.30,
        "standard_ceiling_m": 2.50,
        "min_corridor_width_m": 0.85,
        "min_door_height_m": 2.00,
        "setbacks": {
            "front_m": 3.0,
            "rear_m": 2.0,
            "side_m": 2.0,
        },
        "masonry_modules_cm": [14, 19],
        "block_strengths_mpa": [5.0, 10.0, 15.0],
        "seismic_zone": "very_high",
        "social_housing": {
            "program": "DS 49 (Fondo Solidario de Vivienda)",
            "area_range_m2": (42, 55),
            "max_floors": 2,
        },
        "unit_system": "metric",
        "currency": "CLP",
    },

    # -------------------------------------------------------------------------
    # PERU
    # -------------------------------------------------------------------------
    "PE": {
        "name": "Perú",
        "region": "latin_america",
        "hemisphere": "south",
        "codes": {
            "masonry": "E.070 Albañilería (RNE)",
            "seismic": "E.030 Diseño Sismorresistente (RNE)",
            "concrete": "E.060 Concreto Armado (RNE)",
            "general": "Reglamento Nacional de Edificaciones (RNE)",
        },
        "min_room_areas_m2": {
            "bedroom": 6.0,
            "living": 7.5,
            "kitchen": 3.0,
            "bathroom": 2.0,
            "service": 2.0,
        },
        "min_room_dimensions_m": {
            "bedroom": 2.10,
            "living": 2.40,
            "kitchen": 1.50,
            "bathroom": 1.00,
        },
        "min_ceiling_height_m": 2.30,
        "standard_ceiling_m": 2.50,
        "min_corridor_width_m": 0.90,
        "min_door_height_m": 2.10,
        "setbacks": {
            "front_m": 3.0,
            "rear_m": 2.0,
            "side_m": 1.50,
        },
        "masonry_modules_cm": [12, 15],
        "block_strengths_mpa": [4.0, 7.0, 10.0, 14.0],
        "seismic_zone": "very_high",
        "social_housing": {
            "program": "Techo Propio / Fondo Mivivienda",
            "area_range_m2": (35, 65),
            "max_floors": 2,
        },
        "unit_system": "metric",
        "currency": "PEN",
    },

    # -------------------------------------------------------------------------
    # UNITED STATES
    # -------------------------------------------------------------------------
    "US": {
        "name": "United States",
        "region": "north_america",
        "hemisphere": "north",
        "codes": {
            "building": "IBC 2021 (International Building Code)",
            "residential": "IRC 2021 (International Residential Code)",
            "masonry": "TMS 402/602 (Building Code Requirements for Masonry Structures)",
            "concrete": "ACI 318-19",
            "seismic": "ASCE 7-22",
            "energy": "IECC 2021 (International Energy Conservation Code)",
            "accessibility": "ADA Standards for Accessible Design",
        },
        "min_room_areas_m2": {
            "bedroom": 6.5,      # 70 sq ft (IRC R304.1)
            "living": 11.1,      # 120 sq ft (IRC R304.2)
            "kitchen": 4.6,      # 50 sq ft typical
            "bathroom": 2.3,     # 25 sq ft typical
        },
        "min_room_dimensions_m": {
            "bedroom": 2.13,     # 7 ft (IRC R304.1)
            "living": 2.13,      # 7 ft
            "kitchen": 1.52,     # 5 ft
            "bathroom": 1.22,    # 4 ft
        },
        "min_ceiling_height_m": 2.13,    # 7 ft (IRC R305.1)
        "standard_ceiling_m": 2.44,       # 8 ft standard
        "min_corridor_width_m": 0.91,     # 36 in
        "min_door_height_m": 2.03,        # 6'8"
        "setbacks": {
            "front_m": 7.62,     # 25 ft typical
            "rear_m": 6.10,      # 20 ft
            "side_m": 1.52,      # 5 ft
            "note": "Varies greatly by zoning district",
        },
        "masonry_modules_cm": [10, 15, 20],  # 4", 6", 8" CMU
        "block_strengths_mpa": [8.6, 12.4, 17.2, 20.7],  # 1250-3000 psi
        "seismic_zone": "variable",
        "social_housing": {
            "program": "HUD / Section 8 / LIHTC",
            "area_range_m2": (46, 93),   # 500-1000 sq ft
            "max_floors": 3,
        },
        "unit_system": "imperial",
        "currency": "USD",
    },

    # -------------------------------------------------------------------------
    # CANADA
    # -------------------------------------------------------------------------
    "CA": {
        "name": "Canada",
        "region": "north_america",
        "hemisphere": "north",
        "codes": {
            "building": "NBC 2020 (National Building Code of Canada)",
            "masonry": "CSA S304-14 (Design of Masonry Structures)",
            "concrete": "CSA A23.3",
            "energy": "NECB 2017 (National Energy Code for Buildings)",
            "seismic": "NBC Part 4 Div B",
        },
        "min_room_areas_m2": {
            "bedroom": 7.0,      # NBC 9.5.7
            "living": 11.0,
            "kitchen": 4.5,
            "bathroom": 2.5,
        },
        "min_room_dimensions_m": {
            "bedroom": 2.40,
            "living": 2.40,
            "kitchen": 1.50,
            "bathroom": 1.20,
        },
        "min_ceiling_height_m": 2.30,    # NBC 9.5.3.1
        "standard_ceiling_m": 2.44,       # 8 ft
        "min_corridor_width_m": 0.86,
        "min_door_height_m": 2.03,
        "setbacks": {
            "front_m": 6.0,
            "rear_m": 7.5,
            "side_m": 1.20,
        },
        "masonry_modules_cm": [10, 15, 20],  # 4", 6", 8"
        "block_strengths_mpa": [10.0, 15.0, 20.0, 30.0],
        "seismic_zone": "variable",
        "social_housing": {
            "program": "CMHC National Housing Strategy",
            "area_range_m2": (46, 84),
            "max_floors": 3,
        },
        "unit_system": "metric",
        "currency": "CAD",
    },

    # -------------------------------------------------------------------------
    # SPAIN
    # -------------------------------------------------------------------------
    "ES": {
        "name": "España",
        "region": "europe",
        "hemisphere": "north",
        "codes": {
            "building": "CTE (Código Técnico de la Edificación)",
            "structural": "CTE DB-SE (Seguridad Estructural)",
            "masonry": "CTE DB-SE-F (Fábrica)",
            "seismic": "NCSE-02 / Anejo Nacional del Eurocódigo 8",
            "thermal": "CTE DB-HE (Ahorro de Energía)",
            "fire": "CTE DB-SI (Seguridad en caso de Incendio)",
            "accessibility": "CTE DB-SUA (Seguridad de Utilización y Accesibilidad)",
            "eurocode_masonry": "EN 1996-1-1 (Eurocode 6)",
        },
        "min_room_areas_m2": {
            "bedroom": 6.0,      # CTE DB-SU / regional hab. decrees
            "living": 10.0,
            "kitchen": 5.0,
            "bathroom": 1.5,
            "service": 1.5,
        },
        "min_room_dimensions_m": {
            "bedroom": 2.00,
            "living": 2.50,
            "kitchen": 1.60,
            "bathroom": 1.00,
        },
        "min_ceiling_height_m": 2.50,    # General, varies by region
        "standard_ceiling_m": 2.70,
        "min_corridor_width_m": 0.90,
        "min_door_height_m": 2.03,
        "setbacks": {
            "front_m": 3.0,
            "rear_m": 3.0,
            "side_m": 2.0,
            "note": "Defined by PGOU (Plan General de Ordenación Urbana) per municipality",
        },
        "masonry_modules_cm": [11.5, 14, 19, 24],  # termoarcilla, bloque
        "block_strengths_mpa": [5.0, 10.0, 15.0, 25.0],
        "seismic_zone": "low_to_medium",
        "social_housing": {
            "program": "VPO (Vivienda de Protección Oficial)",
            "area_range_m2": (30, 90),
            "max_floors": 4,
        },
        "unit_system": "metric",
        "currency": "EUR",
    },

    # -------------------------------------------------------------------------
    # PORTUGAL
    # -------------------------------------------------------------------------
    "PT": {
        "name": "Portugal",
        "region": "europe",
        "hemisphere": "north",
        "codes": {
            "building": "RGEU (Regulamento Geral das Edificações Urbanas)",
            "structural": "Eurocódigos (EN 1990-1999)",
            "masonry": "EN 1996-1-1 (Eurocódigo 6)",
            "seismic": "EN 1998-1 (Eurocódigo 8) + Anexo Nacional",
            "thermal": "REH (Regulamento de Desempenho Energético de Habitação)",
        },
        "min_room_areas_m2": {
            "bedroom": 6.5,      # RGEU Art. 66
            "living": 10.0,      # RGEU Art. 66
            "kitchen": 6.0,      # RGEU
            "bathroom": 2.5,
        },
        "min_room_dimensions_m": {
            "bedroom": 2.10,
            "living": 2.40,
            "kitchen": 1.80,
            "bathroom": 1.10,
        },
        "min_ceiling_height_m": 2.40,    # RGEU Art. 65
        "standard_ceiling_m": 2.70,
        "min_corridor_width_m": 0.90,
        "min_door_height_m": 2.00,
        "setbacks": {
            "front_m": 3.0,
            "rear_m": 3.0,
            "side_m": 1.50,
            "note": "Defined by PDM (Plano Director Municipal)",
        },
        "masonry_modules_cm": [11, 15, 20, 25],
        "block_strengths_mpa": [5.0, 10.0, 15.0, 20.0],
        "seismic_zone": "medium",
        "social_housing": {
            "program": "Habitação a Custos Controlados",
            "area_range_m2": (35, 80),
            "max_floors": 3,
        },
        "unit_system": "metric",
        "currency": "EUR",
    },

    # -------------------------------------------------------------------------
    # ITALY
    # -------------------------------------------------------------------------
    "IT": {
        "name": "Italia",
        "region": "europe",
        "hemisphere": "north",
        "codes": {
            "building": "DM 17/01/2018 (NTC 2018 — Norme Tecniche per le Costruzioni)",
            "masonry": "NTC 2018 Cap. 4.5 + Eurocode 6",
            "seismic": "NTC 2018 Cap. 3.2 (classificazione sismica)",
            "thermal": "DLgs 192/2005 + DM 26/06/2015",
            "fire": "DM 03/08/2015",
            "general": "DM 5/7/1975 (Requisiti igienico-sanitari abitazioni)",
        },
        "min_room_areas_m2": {
            "bedroom": 9.0,      # DM 5/7/1975 — singola; 14 m² doppia
            "living": 14.0,      # soggiorno
            "kitchen": 3.0,      # angolo cottura
            "bathroom": 2.5,
        },
        "min_room_dimensions_m": {
            "bedroom": 2.70,
            "living": 2.70,
            "kitchen": 1.50,
            "bathroom": 1.00,
        },
        "min_ceiling_height_m": 2.70,    # DM 5/7/1975
        "standard_ceiling_m": 2.70,
        "min_corridor_width_m": 1.00,
        "min_door_height_m": 2.10,
        "setbacks": {
            "front_m": 5.0,
            "rear_m": 5.0,
            "side_m": 5.0,
            "note": "Defined by PRG/PGT per municipality; distanza minima tra fabbricati = 10m (DM 1444/68)",
        },
        "masonry_modules_cm": [12, 20, 25, 30, 38],  # laterizio
        "block_strengths_mpa": [5.0, 10.0, 15.0, 25.0],
        "seismic_zone": "high",
        "social_housing": {
            "program": "ERP (Edilizia Residenziale Pubblica)",
            "area_range_m2": (38, 95),
            "max_floors": 4,
        },
        "unit_system": "metric",
        "currency": "EUR",
    },

    # -------------------------------------------------------------------------
    # FRANCE
    # -------------------------------------------------------------------------
    "FR": {
        "name": "France",
        "region": "europe",
        "hemisphere": "north",
        "codes": {
            "building": "Code de la Construction et de l'Habitation (CCH)",
            "structural": "Eurocodes (NF EN 1990-1999)",
            "masonry": "NF EN 1996 (Eurocode 6) + Annexe Nationale",
            "seismic": "NF EN 1998 (Eurocode 8) + Arrêté 22/10/2010",
            "thermal": "RE 2020 (Réglementation Environnementale)",
            "accessibility": "Arrêté 24/12/2015",
            "fire": "Arrêté 31/01/1986 (habitations)",
        },
        "min_room_areas_m2": {
            "bedroom": 9.0,      # Art. R111-2 CCH
            "living": 9.0,       # séjour
            "kitchen": 3.0,
            "bathroom": 2.5,
        },
        "min_room_dimensions_m": {
            "bedroom": 2.10,
            "living": 2.10,
            "kitchen": 1.50,
            "bathroom": 1.00,
        },
        "min_ceiling_height_m": 2.50,    # Art. R111-2 CCH
        "standard_ceiling_m": 2.50,
        "min_corridor_width_m": 0.90,
        "min_door_height_m": 2.04,
        "setbacks": {
            "front_m": 5.0,
            "rear_m": 4.0,
            "side_m": 3.0,
            "note": "PLU (Plan Local d'Urbanisme) per municipality",
        },
        "masonry_modules_cm": [15, 20, 25, 30],  # parpaing
        "block_strengths_mpa": [4.0, 6.0, 10.0, 16.0],
        "seismic_zone": "low_to_medium",
        "social_housing": {
            "program": "HLM (Habitation à Loyer Modéré)",
            "area_range_m2": (28, 85),
            "max_floors": 4,
        },
        "unit_system": "metric",
        "currency": "EUR",
    },

    # -------------------------------------------------------------------------
    # GREECE
    # -------------------------------------------------------------------------
    "GR": {
        "name": "Greece / Ελλάδα",
        "region": "europe",
        "hemisphere": "north",
        "codes": {
            "building": "NOK (Nέος Oικοδομικός Kανονισμός) / GBR 2012",
            "structural": "Eurocodes + Greek National Annexes",
            "seismic": "EAK 2000 / EN 1998 (Eurocode 8)",
            "thermal": "KENAK (Κανονισμός Ενεργειακής Απόδοσης Κτιρίων)",
            "masonry": "EN 1996 + National Annex",
        },
        "min_room_areas_m2": {
            "bedroom": 8.0,
            "living": 12.0,
            "kitchen": 5.0,
            "bathroom": 2.5,
        },
        "min_room_dimensions_m": {
            "bedroom": 2.40,
            "living": 2.50,
            "kitchen": 1.60,
            "bathroom": 1.00,
        },
        "min_ceiling_height_m": 2.65,
        "standard_ceiling_m": 2.80,
        "min_corridor_width_m": 0.90,
        "min_door_height_m": 2.10,
        "setbacks": {
            "front_m": 4.0,
            "rear_m": 4.0,
            "side_m": 2.50,
        },
        "masonry_modules_cm": [10, 15, 20, 25],
        "block_strengths_mpa": [5.0, 10.0, 15.0],
        "seismic_zone": "very_high",
        "unit_system": "metric",
        "currency": "EUR",
    },

    # -------------------------------------------------------------------------
    # TURKEY
    # -------------------------------------------------------------------------
    "TR": {
        "name": "Türkiye",
        "region": "europe",
        "hemisphere": "north",
        "codes": {
            "building": "İmar Kanunu (Zoning Law 3194)",
            "seismic": "TBDY 2018 (Turkish Building Earthquake Code)",
            "masonry": "TS 2510 / TS EN 1996",
            "thermal": "TS 825 (Thermal Insulation)",
        },
        "min_room_areas_m2": {
            "bedroom": 8.0,
            "living": 12.0,
            "kitchen": 5.0,
            "bathroom": 2.5,
        },
        "min_room_dimensions_m": {
            "bedroom": 2.50,
            "living": 2.60,
            "kitchen": 1.50,
            "bathroom": 1.00,
        },
        "min_ceiling_height_m": 2.40,
        "standard_ceiling_m": 2.80,
        "min_corridor_width_m": 1.00,
        "min_door_height_m": 2.10,
        "setbacks": {
            "front_m": 5.0,
            "rear_m": 3.0,
            "side_m": 3.0,
        },
        "masonry_modules_cm": [10, 13.5, 19, 25],
        "block_strengths_mpa": [5.0, 7.5, 10.0, 15.0],
        "seismic_zone": "very_high",
        "unit_system": "metric",
        "currency": "TRY",
    },

    # -------------------------------------------------------------------------
    # MOROCCO
    # -------------------------------------------------------------------------
    "MA": {
        "name": "Morocco / المغرب",
        "region": "mediterranean",
        "hemisphere": "north",
        "codes": {
            "building": "RPS 2011 (Règlement de Construction Parasismique)",
            "seismic": "RPS 2000 (revised 2011)",
            "concrete": "BAEL 91 / Eurocode transition",
            "thermal": "RTCM (Règlement Thermique de Construction au Maroc)",
        },
        "min_room_areas_m2": {
            "bedroom": 8.0,
            "living": 10.0,
            "kitchen": 4.0,
            "bathroom": 2.0,
        },
        "min_room_dimensions_m": {
            "bedroom": 2.20,
            "living": 2.50,
            "kitchen": 1.50,
            "bathroom": 1.00,
        },
        "min_ceiling_height_m": 2.60,
        "standard_ceiling_m": 2.80,
        "min_corridor_width_m": 0.90,
        "min_door_height_m": 2.10,
        "setbacks": {
            "front_m": 4.0,
            "rear_m": 3.0,
            "side_m": 2.0,
        },
        "masonry_modules_cm": [10, 15, 20],
        "block_strengths_mpa": [4.0, 6.0, 10.0],
        "seismic_zone": "medium",
        "social_housing": {
            "program": "Habitat Social (ALEM)",
            "area_range_m2": (50, 80),
            "max_floors": 3,
        },
        "unit_system": "metric",
        "currency": "MAD",
    },
}


# =============================================================================
# INTERNATIONAL CLIMATE ZONES — Köppen-Geiger based
# =============================================================================

CLIMATE_ZONES_INTERNATIONAL: Dict[str, Dict[str, Any]] = {
    "Af": {
        "name": "Tropical Rainforest",
        "koppen": "Af",
        "description": "Hot and wet year-round, no dry season",
        "regions": ["Amazon", "Central Africa", "Southeast Asia", "Caribbean coast"],
        "strategies": [
            "Maximum cross-ventilation — openings on all facades",
            "Deep overhangs and shading devices",
            "Elevated construction for air circulation",
            "Light-colored roofs to reflect solar radiation",
            "Natural materials that breathe (wood, bamboo)",
        ],
        "ventilation": "permanent cross-ventilation, maximum openings",
        "window_recommendation": "Large openings with insect screens, operable louvers",
        "insulation_priority": "roof (reflect heat), walls secondary",
        "heating_needed": False,
        "cooling_strategy": "passive — ventilation + shading",
    },
    "Aw": {
        "name": "Tropical Savanna",
        "koppen": "Aw",
        "description": "Hot with distinct wet and dry seasons",
        "regions": ["Brazil central", "Sub-Saharan Africa", "India", "Northern Australia", "Mexico south"],
        "strategies": [
            "Cross-ventilation with adjustable openings",
            "Thermal mass for nighttime cooling in dry season",
            "Rain protection — generous overhangs for wet season",
            "Shading on west and north (southern hemisphere) or south (northern)",
        ],
        "ventilation": "cross-ventilation, adjustable for seasons",
        "window_recommendation": "Medium openings with solar protection",
        "insulation_priority": "roof primary",
        "heating_needed": False,
        "cooling_strategy": "passive — ventilation + thermal mass",
    },
    "BSh": {
        "name": "Hot Semi-Arid (Steppe)",
        "koppen": "BSh",
        "description": "Hot and dry, large temperature swings day-night",
        "regions": ["Northeast Brazil", "Sahel", "Middle East", "Northwest Mexico", "Murcia (Spain)"],
        "strategies": [
            "Heavy thermal mass (thick masonry walls)",
            "Small windows on east/west, moderate on north/south",
            "Compact building form to minimize exposed surface",
            "Internal courtyard for natural cooling (patio)",
            "Night ventilation to cool thermal mass",
            "Light-colored exterior to reflect heat",
        ],
        "ventilation": "night ventilation, closed during day",
        "window_recommendation": "Small, deeply recessed, with shutters",
        "insulation_priority": "roof and walls equally important",
        "heating_needed": False,
        "cooling_strategy": "thermal mass + night ventilation",
    },
    "Csa": {
        "name": "Hot-Summer Mediterranean",
        "koppen": "Csa",
        "description": "Hot dry summers, mild wet winters",
        "regions": ["Mediterranean coast", "Southern California", "Central Chile", "Western Australia", "Southern Portugal/Spain/Italy/Greece/Turkey"],
        "strategies": [
            "Thermal mass for both summer and winter performance",
            "Operable shading — allow winter sun, block summer sun",
            "Cross-ventilation for summer, sealed for winter",
            "Internal courtyards (traditional Mediterranean plan)",
            "White or light-colored exteriors",
            "Overhangs calculated for latitude (block high summer sun, admit low winter sun)",
        ],
        "ventilation": "summer cross-ventilation, winter sealed",
        "window_recommendation": "South-facing large (winter sun), west small (summer heat), shutters on all",
        "insulation_priority": "walls and roof — both heating and cooling seasons",
        "heating_needed": True,
        "cooling_strategy": "thermal mass + ventilation + shading",
    },
    "Csb": {
        "name": "Warm-Summer Mediterranean",
        "koppen": "Csb",
        "description": "Warm dry summers, cool wet winters",
        "regions": ["Northern Portugal", "Galicia", "Pacific Northwest (US)", "Central Chile"],
        "strategies": [
            "Moderate thermal mass",
            "Good insulation for winter",
            "Natural ventilation in summer",
            "Maximize south-facing glazing for passive solar heating",
        ],
        "ventilation": "natural summer ventilation, controlled winter",
        "window_recommendation": "Large south windows for solar gain, moderate elsewhere",
        "insulation_priority": "walls and roof — winter focus",
        "heating_needed": True,
        "cooling_strategy": "natural ventilation sufficient",
    },
    "Cfa": {
        "name": "Humid Subtropical",
        "koppen": "Cfa",
        "description": "Hot humid summers, mild to cool winters",
        "regions": ["Southeast US", "Southern Brazil", "Buenos Aires", "Northern Italy (Po Valley)", "Tokyo"],
        "strategies": [
            "Cross-ventilation essential for summer humidity",
            "Moderate insulation for winter",
            "Dehumidification strategies",
            "Covered porches/verandas for rain protection",
            "Elevated floor for moisture control",
        ],
        "ventilation": "cross-ventilation year-round, adjustable",
        "window_recommendation": "Large openings with screens, operable",
        "insulation_priority": "balanced — both seasons matter",
        "heating_needed": True,
        "cooling_strategy": "ventilation + dehumidification",
    },
    "Cfb": {
        "name": "Oceanic",
        "koppen": "Cfb",
        "description": "Cool summers, mild winters, rain year-round",
        "regions": ["Western Europe", "UK", "New Zealand", "Southern Chile", "Pacific NW coast"],
        "strategies": [
            "High insulation — heating-dominated climate",
            "Maximize passive solar gain (south-facing glazing)",
            "Rain protection — overhangs, rain screens",
            "Airtight construction to prevent heat loss",
            "Minimal cooling needed",
        ],
        "ventilation": "controlled — avoid heat loss, ensure air quality",
        "window_recommendation": "South: large for solar gain. North: small, well-insulated",
        "insulation_priority": "maximum — walls, roof, floor, windows",
        "heating_needed": True,
        "cooling_strategy": "rarely needed — natural ventilation sufficient",
    },
    "Dfa": {
        "name": "Hot-Summer Continental",
        "koppen": "Dfa",
        "description": "Hot summers, cold winters, large temperature range",
        "regions": ["US Midwest", "Northern China", "Central Canada"],
        "strategies": [
            "Very high insulation for cold winters",
            "Thermal mass to moderate temperature swings",
            "South-facing glazing for winter solar gain",
            "Summer shading on south and west",
            "Airtight construction with controlled ventilation",
        ],
        "ventilation": "controlled in winter, natural in summer",
        "window_recommendation": "South: large (triple-glazed). West: small with shading",
        "insulation_priority": "maximum — all surfaces",
        "heating_needed": True,
        "cooling_strategy": "ventilation + shading, may need AC",
    },
    "Dfb": {
        "name": "Warm-Summer Continental",
        "koppen": "Dfb",
        "description": "Warm summers, cold to very cold winters",
        "regions": ["Southern Canada", "Scandinavia", "Northern US", "Moscow region"],
        "strategies": [
            "Maximum insulation — heating dominated",
            "Triple-glazed windows, minimize north glazing",
            "Passive solar design critical",
            "Snow load considerations for roof",
            "Vestibule/airlock entry to prevent heat loss",
        ],
        "ventilation": "mechanical with heat recovery (HRV/ERV)",
        "window_recommendation": "South: moderate (triple-glazed). Minimize north/east/west",
        "insulation_priority": "extreme — Passive House levels",
        "heating_needed": True,
        "cooling_strategy": "rarely needed",
    },
}


# =============================================================================
# HELPER — Lookup region regulations
# =============================================================================

def get_regulations(country_code: str) -> Dict[str, Any]:
    """Return building regulations for a country code (ISO 3166-1 alpha-2)."""
    return REGIONAL_REGULATIONS.get(country_code.upper(), REGIONAL_REGULATIONS["BR"])


def get_min_room_area(country_code: str, room_type: str) -> float:
    """Return minimum room area in m² for a given country and room type."""
    regs = get_regulations(country_code)
    return regs.get("min_room_areas_m2", {}).get(room_type, 6.0)


def get_climate_zone(koppen_code: str) -> Dict[str, Any]:
    """Return climate zone info by Köppen-Geiger code."""
    return CLIMATE_ZONES_INTERNATIONAL.get(koppen_code, CLIMATE_ZONES_INTERNATIONAL.get("Cfa", {}))


def get_countries_for_region(region: str) -> List[str]:
    """Return country codes for a region (latin_america, north_america, europe, mediterranean)."""
    return [
        code for code, reg in REGIONAL_REGULATIONS.items()
        if reg.get("region") == region
    ]


def get_style_config(style_key: str) -> Dict[str, Any]:
    """Return style configuration dict, defaulting to 'modern' if unknown."""
    return STYLES.get(style_key, STYLES["modern"])


def get_room_rules(style_key: str, room_type: str) -> Dict[str, Any]:
    """Return room-specific rules for a given style."""
    style = get_style_config(style_key)
    return style.get("room_rules", {}).get(room_type, {})


def get_roof_config(roof_key: str) -> Dict[str, Any]:
    """Return roof form configuration."""
    return ROOF_FORMS.get(roof_key, ROOF_FORMS["gable"])


def suggest_roof_for_style(style_key: str) -> str:
    """Suggest the best roof form for a given architectural style."""
    style = get_style_config(style_key)
    prefs = style.get("facade", {}).get("roof_preference", ["gable"])
    return prefs[0] if prefs else "gable"
