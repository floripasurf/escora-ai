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

# Espaçamento máximo entre escoras de LAJE (m) — TETO / FALLBACK
# Calibrado com medições de projetos Supplier reais (84678, 92056):
#   ESC310_Laje median = 1.00m, ESC450_Laje median = 1.08m
# IMPORTANTE: este valor é apenas o TETO quando o cálculo adaptativo
# O espaçamento real é calculado a partir de carga/capacidade_escora.
ESPACAMENTO_MAX_DEFAULT = 1.10

# Espaçamento máximo entre escoras de VIGA (m) — TETO / FALLBACK
# Referência: projetos executivos de engenharia (mediana real: 0.70m)
# Vigas concentram mais carga que lajes → espaçamento mais denso
# IMPORTANTE: este valor é apenas o TETO quando o cálculo adaptativo
# não está disponível. O espaçamento real varia com vão e seção da viga.
ESPACAMENTO_MAX_VIGA = 1.00

# Espaçamento por faixa de altura da laje (m) — NBR 15696:2009 + prática de projeto
# Chave: (min_cm, max_cm) -> espaçamento máximo em metros
ESPACAMENTO_POR_ALTURA = {
    (10, 16): 1.30,   # lajes leves
    (17, 24): 1.20,   # lajes médias
    (25, 30): 1.10,   # lajes altas
    (31, 99): 1.00,   # lajes muito altas — segurança máxima
}

# Espaçamento mínimo entre escoras (m) — evita acúmulo próximo a apoios
ESPACAMENTO_MIN = 0.30

# Contra-flecha recomendada por faixa de vão (m) — NBR 6118:2023 §13.4.2
# Chave: (vão_min, vão_max) -> contra-flecha em metros
CONTRA_FLECHA = {
    (2.0, 3.0): 0.005,   # 0.5 cm
    (3.0, 4.0): 0.010,   # 1.0 cm
    (4.0, 5.0): 0.015,   # 1.5 cm
    (5.0, 6.0): 0.020,   # 2.0 cm
}

# Tabela de espaçamento de VMs secundárias por espessura de laje + compensado
# (manual p.55-60). Chave: (espessura_laje_cm, compensado_mm, n_apoios) -> espaçamento_max_m.
# Registrada para uso futuro quando o usuário especificar espessura do compensado.
# Sem compensado especificado, o pipeline usa ESPACAMENTO_POR_ALTURA acima.
ESPACAMENTO_SECUNDARIAS_MANUAL = {
    # (laje_cm, compensado_mm, n_apoios): espaçamento_max_m
    (8, 12, 2): 0.38, (8, 15, 2): 0.45, (8, 18, 2): 0.50, (8, 21, 2): 0.55,
    (10, 12, 2): 0.36, (10, 15, 2): 0.42, (10, 18, 2): 0.48, (10, 21, 2): 0.53,
    (12, 12, 2): 0.33, (12, 15, 2): 0.40, (12, 18, 2): 0.54, (12, 21, 2): 0.50,
    (15, 12, 2): 0.30, (15, 15, 2): 0.36, (15, 18, 2): 0.42, (15, 21, 2): 0.46,
    (20, 12, 2): 0.26, (20, 15, 2): 0.31, (20, 18, 2): 0.36, (20, 21, 2): 0.40,
    (25, 12, 2): 0.23, (25, 15, 2): 0.28, (25, 18, 2): 0.32, (25, 21, 2): 0.36,
    (30, 12, 2): 0.21, (30, 15, 2): 0.25, (30, 18, 2): 0.30, (30, 21, 2): 0.33,
    # 4+ apoios: ~15-20% mais do que 2 apoios
    (8, 12, 4): 0.44, (8, 15, 4): 0.52, (8, 18, 4): 0.58, (8, 21, 4): 0.63,
    (10, 12, 4): 0.41, (10, 15, 4): 0.49, (10, 18, 4): 0.55, (10, 21, 4): 0.61,
    (12, 12, 4): 0.38, (12, 15, 4): 0.46, (12, 18, 4): 0.62, (12, 21, 4): 0.58,
    (15, 12, 4): 0.35, (15, 15, 4): 0.41, (15, 18, 4): 0.48, (15, 21, 4): 0.53,
    (20, 12, 4): 0.30, (20, 15, 4): 0.36, (20, 18, 4): 0.41, (20, 21, 4): 0.46,
    (25, 12, 4): 0.27, (25, 15, 4): 0.32, (25, 18, 4): 0.37, (25, 21, 4): 0.41,
    (30, 12, 4): 0.24, (30, 15, 4): 0.29, (30, 18, 4): 0.34, (30, 21, 4): 0.38,
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

# Preço por kg de equipamento por mês de locação (R$/kg/mês)
# Referência: Supplier SJC padrão de mercado regional
PRECO_POR_KG_MES_BRL = 1.11
