"""
Constantes normativas para cálculo de escoramento.

Referências:
- NBR 15696:2009 — Fôrmas e escoramentos para estruturas de concreto
- NBR 6120:2019 — Ações para cálculo de estruturas de edificações
- NBR 6118:2023 — Projeto de estruturas de concreto
"""

# Peso específico do concreto armado (kN/m³) — NBR 6120:2019 Tabela 1
GAMMA_CONCRETO = 25.0

# Peso próprio do sistema de fôrmas (kN/m²) — NBR 6120:2019
# Compensado 12mm + longarinas + vigas de escoramento ≈ 0.5 kN/m²
Q_FORMA_DEFAULT = 0.50

# Sobrecarga mínima de trabalho (kN/m²) — NBR 15696:2009
# Inclui operários, equipamentos e impacto de lançamento
Q_SOBRECARGA_DEFAULT = 1.5

# Coeficiente de majoração de ações — NBR 15696:2009
GAMMA_F = 1.4

# Espaçamento máximo entre escoras de LAJE (m) — Manual Lajes Martins
# Varia por altura da laje (ver ESPACAMENTO_POR_ALTURA abaixo)
ESPACAMENTO_MAX_DEFAULT = 1.30

# Espaçamento máximo entre escoras de VIGA (m)
# Referência: projetos executivos de engenharia (mediana real: 0.70m)
# Vigas concentram mais carga que lajes → espaçamento mais denso
ESPACAMENTO_MAX_VIGA = 1.00

# Espaçamento por faixa de altura da laje (m) — Manual Lajes Martins
# Chave: (min_cm, max_cm) -> espaçamento máximo em metros
ESPACAMENTO_POR_ALTURA = {
    (10, 16): 1.30,   # lajes leves
    (17, 24): 1.20,   # lajes médias
    (25, 30): 1.10,   # lajes altas
    (31, 99): 1.00,   # lajes muito altas — segurança máxima
}

# Espaçamento mínimo entre escoras (m) — evita acúmulo próximo a apoios
ESPACAMENTO_MIN = 0.30

# Contra-flecha recomendada por faixa de vão (m) — Manual Lajes Martins
# Chave: (vão_min, vão_max) -> contra-flecha em metros
CONTRA_FLECHA = {
    (2.0, 3.0): 0.005,   # 0.5 cm
    (3.0, 4.0): 0.010,   # 1.0 cm
    (4.0, 5.0): 0.015,   # 1.5 cm
    (5.0, 6.0): 0.020,   # 2.0 cm
}

# Distância mínima da escora à borda da laje (m)
DISTANCIA_BORDA_MIN = 0.15

# Distância mínima da escora ao pilar (m) — NBR 6118:2023 + prática
# Zona crítica de punção (NBR 6118 §19.5): 2d da face do pilar.
# Para laje h=12cm, d≈10cm → zona = 0.20m. Adicionamos margem prática
# para circulação na obra. 0.70m da face do pilar.
DISTANCIA_PILAR_MIN = 0.70

# Espessura padrão de laje quando não especificada (m)
ESPESSURA_DEFAULT = 0.12

# Altura padrão do pé-direito (m)
ALTURA_DEFAULT = 2.80
