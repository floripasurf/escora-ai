"""
Constantes normativas para cálculo de escoramento.

Referências:
- NBR 15696:2009 — Fôrmas e escoramentos para estruturas de concreto
- NBR 6120:2019 — Ações para cálculo de estruturas de edificações
"""

# Peso específico do concreto armado (kN/m³) — NBR 6120:2019
GAMMA_CONCRETO = 25.0

# Sobrecarga mínima de trabalho (kN/m²) — NBR 15696:2009
# Inclui operários, equipamentos e impacto de lançamento
Q_SOBRECARGA_DEFAULT = 1.5

# Coeficiente de majoração de ações — NBR 15696:2009
GAMMA_F = 1.4

# Espaçamento máximo entre escoras (m) — prática de projeto
ESPACAMENTO_MAX_DEFAULT = 1.5

# Distância mínima da escora à borda da laje (m)
DISTANCIA_BORDA_MIN = 0.15

# Espessura padrão de laje quando não especificada (m)
ESPESSURA_DEFAULT = 0.12

# Altura padrão do pé-direito (m)
ALTURA_DEFAULT = 2.80
