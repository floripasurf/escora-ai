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

# Sobrecarga mínima de trabalho (kN/m²) — NBR 15696:2009 §4.2.e
# Inclui operários, equipamentos e impacto de lançamento.
# Manual §3 (corrigido em 2026-05-27): a NBR exige minimo 2.0 kN/m² para
# concretagem. O valor 1.5 kN/m² corresponde a PLATAFORMA DE TRABALHO local
# (Q_PLATAFORMA_LOCAL_DEFAULT), nao a sobrecarga distribuida geral.
Q_SOBRECARGA_DEFAULT = 2.0

# Sobrecarga local de plataforma de trabalho (kN/m²) — NBR 15696:2009 §4.2.k
# Aplicada apenas quando ha passarela/plataforma modelada.
Q_PLATAFORMA_LOCAL_DEFAULT = 1.5

# Sobrecarga em reescoramento (kN/m²) — NBR 15696:2009 Anexo C.4.a
# Sobrecarga minima durante construcao para escoras remanescentes.
Q_REESCORAMENTO_DEFAULT = 1.0

# Sobrecarga para verificacao de flecha (kN/m²) — NBR 15696:2009 §4.3.2
# Aplicada sem coeficiente de seguranca, junto com peso proprio do concreto.
Q_FLECHA_VERIFICACAO = 1.0

# Carga estatica minima total (kN/m²) — NBR 15696:2009 §4.2.e
# A soma de peso proprio + sobrecargas nao pode ser inferior a este valor
# (verificada apos calculo de cargas).
CARGA_ESTATICA_MIN_TOTAL = 4.0

# Esforco horizontal lateral nas formas de laje — NBR 15696:2009 §4.2.l
# Fracao da carga vertical aplicada nesse nivel, em cada sentido principal.
ESFORCO_HORIZONTAL_FRACAO = 0.05  # 5%

# Coeficiente de majoração de ações — NBR 15696:2009 §4.3.1 (gamma_Q = 1.4,
# psi0 = 1.0 em todas as variaveis). Manual §3.
GAMMA_F = 1.4

# Carga de projeto FALLBACK para laje sem area/carga calculavel (kN/m²).
# Derivacao (laje macica default de 12 cm):
#   (0.12 · GAMMA_CONCRETO + Q_FORMA_DEFAULT + Q_SOBRECARGA_DEFAULT) · GAMMA_F
#   = (0.12 · 25 + 0.5 + 2.0) · 1.4 = 7.7
# NBR 15696:2009 §4.2 (cargas) + §4.3.1 (gamma_f). So deve ser usado quando
# area_m2 == 0 — caminho que tambem gera warning no resultado.
Q_PROJETO_FALLBACK_LAJE_KN_M2 = (
    (0.12 * GAMMA_CONCRETO + Q_FORMA_DEFAULT + Q_SOBRECARGA_DEFAULT) * GAMMA_F
)

# Coeficiente de ponderacao do MATERIAL de escoras/torres em compressao/
# flambagem — NBR 15696:2009 §4.3.1.2 (manual §3, corrigido 2026-06-11;
# pendencia 27). MINORA a RESISTENCIA: Rd = Rk / 1.5. Aplica-se
# SIMULTANEAMENTE com GAMMA_F = 1.4 nas acoes (Fd <= Rd = Rk/1.5) — NAO e
# um majorador alternativo de acoes.
#
# IMPORTANTE — NAO DUPLA-CONTAR (manual §3 e §23.9): as capacidades de
# catalogo usadas pelo motor (tabelas Orguel §13.1/§13.2) ja sao cargas
# ADMISSIVEIS, derivadas de ruptura ensaiada com coeficiente de seguranca
# >= 2.0 do Anexo A. O gamma_m = 1.5 so deve ser aplicado quando a
# resistencia de entrada for CARACTERISTICA/de ruptura (Rk), nunca sobre
# valores ja admissiveis. Vide shore_capacity.design_capacity_kn
# (parametro capacity_basis).
GAMMA_M_ESCORAS_TORRES = 1.5

# DEPRECATED (pendencia 27, 2026-06-11): nome antigo incorreto — o prefixo
# "GAMMA_F" sugeria majoracao de ACOES, mas o coeficiente pondera o
# MATERIAL (minora a resistencia). Usar GAMMA_M_ESCORAS_TORRES. Alias
# mantido apenas para nao quebrar imports existentes.
GAMMA_F_FLAMBAGEM = GAMMA_M_ESCORAS_TORRES

# Coeficiente de ponderacao do material aco (uso geral) — NBR 15696 §4.3.1.2
GAMMA_M_ACO = 1.1

# Coeficiente de seguranca minimo contra flambagem (escoras/torres)
# NBR 15696:2009 Anexo A: deve ser >= 2.0 sobre a carga de ruptura ensaiada.
COEF_SEGURANCA_FLAMBAGEM_MIN = 2.0

# Prazo minimo (dias) para desforma/remanejamento - NBR 14931 + NBR 15696.
# Manual §26 item 10 (2026-05-28): piso normativo padrao. Reducao abaixo
# disso so com analise tecnica, comprovacao de fcj/Ec e aprovacao do
# responsavel tecnico. Override deve vir acompanhado de justificativa.
DESFORMA_MIN_DIAS = 14

# Espaçamento máximo entre escoras de LAJE (m) — TETO ABSOLUTO / FALLBACK
# Calibrado com medições de projetos Orguel reais (84678, 92056):
#   ESC310_Laje median = 1.00m, ESC450_Laje median = 1.08m
# IMPORTANTE: este valor é apenas o TETO quando o cálculo adaptativo
# (shore_capacity.compute_adaptive_spacing) não está disponível.
# O espaçamento real é calculado a partir de carga/capacidade_escora.
# Decisao (pendencia 20, 2026-06-11): mantido 1.10 como teto absoluto
# calibrado em projetos reais; o grid de REFERENCIA para lajes macicas e
# 1.00 x 1.00 m (ESPACAMENTO_REFERENCIA_MACICAS abaixo) — espacamentos
# entre 1.00 e 1.10 m exigem verificacao explicita de capacidade da
# escora + VM por momento e flecha (manual §11.1).
ESPACAMENTO_MAX_DEFAULT = 1.10

# Grid de referencia (teto operacional) para lajes MACICAS (m) —
# manual §11.1 (convergencia das fontes da secao 23.3). Espacamentos
# maiores que 1.00 m somente com verificacao de capacidade da escora e
# das VMs por momento e flecha.
ESPACAMENTO_REFERENCIA_MACICAS = 1.00

# Espaçamento máximo entre escoras de VIGA (m) — TETO / FALLBACK
# Referência: projetos executivos de engenharia (mediana real: 0.70m)
# Vigas concentram mais carga que lajes → espaçamento mais denso
# IMPORTANTE: este valor é apenas o TETO quando o cálculo adaptativo
# não está disponível. O espaçamento real varia com vão e seção da viga.
ESPACAMENTO_MAX_VIGA = 1.00

# Espaçamento por faixa de altura da laje (m).
# PROVENIENCIA (corrigida em 2026-06-11, pendencia 20 / manual §11.1):
# - NAO e da NBR 15696. A norma NAO prescreve espacamento de escoras fora
#   do reescoramento (grid 2.0 x 2.0 m, Anexo C).
# - As 3 primeiras linhas (10-16, 17-24, 25-30) vem da tabela Lajes
#   Martins (manual §23.4) para distancia entre LINHAS de escoramento de
#   lajes PRE-MOLDADAS (escoras perpendiculares as vigotas) — nao para
#   grid bidirecional de lajes macicas.
# - A linha (31, 99) NAO TEM FONTE em nenhum documento; mantida apenas
#   como fallback conservador para o pipeline.
# Para lajes MACICAS o teto operacional e o grid de referencia
# 1.00 x 1.00 m (ESPACAMENTO_REFERENCIA_MACICAS, manual §11.1);
# espacamentos maiores exigem verificacao de capacidade da escora + VM
# por momento e flecha.
# Chave: (min_cm, max_cm) -> espaçamento máximo em metros
ESPACAMENTO_POR_ALTURA = {
    (10, 16): 1.30,   # Lajes Martins — pre-moldadas, linhas de escora
    (17, 24): 1.20,   # Lajes Martins — pre-moldadas, linhas de escora
    (25, 30): 1.10,   # Lajes Martins — pre-moldadas, linhas de escora
    (31, 99): 1.00,   # SEM FONTE — fallback conservador do motor
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

# Tabela de espaçamento de VMs secundárias por espessura de laje + compensado.
# FONTE: tabela canonica Orguel p.89, transcrita no manual §12.2 e verificada
# celula a celula em 600 dpi (2026-06-11, pendencia 20). Cada celula do PDF
# contem "2 apoios / 4 apoios" (cabecalho "PARA 2 / 4 APOIOS"; o segundo
# valor corresponde a 3 vaos, nao a "3+ apoios" generico). Valores do PDF em
# cm, convertidos aqui para metros.
# Colunas de compensado: 12/14/15/17/18/20/21 mm.
# Chave: (espessura_laje_cm, compensado_mm, n_apoios) -> espaçamento_max_m.
# Sem compensado especificado, o pipeline usa ESPACAMENTO_POR_ALTURA acima.
_COMPENSADO_MM = (12, 14, 15, 17, 18, 20, 21)

# laje_cm: celulas (vao_2_apoios_cm, vao_4_apoios_cm) por coluna de compensado
_ESPACAMENTO_SECUNDARIAS_CM = {
    8:   ((42, 50), (48, 61), (50, 61), (58, 69), (61, 71), (68, 84), (71, 84)),
    9:   ((41, 49), (48, 49), (50, 60), (57, 68), (60, 70), (66, 79), (70, 82)),
    10:  ((40, 49), (47, 49), (50, 60), (55, 67), (59, 69), (65, 77), (68, 80)),
    11:  ((39, 48), (46, 48), (49, 59), (54, 66), (58, 68), (64, 76), (67, 79)),
    12:  ((38, 47), (45, 47), (48, 59), (53, 64), (57, 67), (63, 75), (66, 78)),
    13:  ((38, 46), (44, 46), (47, 58), (53, 64), (56, 66), (62, 74), (65, 77)),
    14:  ((37, 45), (44, 45), (47, 57), (52, 63), (55, 64), (61, 73), (64, 76)),
    15:  ((37, 45), (43, 45), (46, 56), (51, 62), (54, 63), (60, 72), (63, 75)),
    16:  ((36, 44), (42, 44), (45, 55), (50, 61), (53, 62), (60, 71), (62, 74)),
    18:  ((35, 43), (41, 43), (44, 54), (50, 60), (52, 62), (58, 70), (61, 72)),
    20:  ((34, 42), (40, 42), (43, 52), (49, 59), (51, 61), (56, 69), (59, 70)),
    22:  ((33, 41), (39, 41), (42, 51), (48, 58), (51, 60), (55, 66), (58, 69)),
    25:  ((33, 40), (38, 40), (41, 50), (46, 56), (49, 60), (53, 65), (56, 67)),
    28:  ((32, 39), (37, 39), (40, 48), (45, 55), (48, 58), (52, 63), (54, 64)),
    30:  ((31, 38), (36, 38), (39, 47), (44, 54), (47, 57), (51, 62), (53, 64)),
    35:  ((30, 36), (35, 36), (37, 46), (42, 51), (45, 54), (50, 60), (51, 62)),
    40:  ((29, 35), (33, 35), (36, 44), (41, 50), (43, 53), (48, 58), (50, 60)),
    50:  ((27, 33), (31, 33), (34, 41), (38, 47), (41, 49), (45, 55), (47, 57)),
    60:  ((25, 31), (30, 31), (32, 39), (36, 44), (38, 47), (43, 52), (45, 54)),
    80:  ((23, 29), (27, 29), (29, 36), (34, 40), (35, 43), (39, 48), (41, 50)),
    100: ((22, 27), (25, 27), (27, 33), (31, 38), (33, 40), (37, 44), (38, 47)),
}

ESPACAMENTO_SECUNDARIAS_MANUAL = {
    (laje_cm, comp_mm, n_apoios): vao_cm / 100.0
    for laje_cm, cells in _ESPACAMENTO_SECUNDARIAS_CM.items()
    for comp_mm, (vao_2, vao_4) in zip(_COMPENSADO_MM, cells)
    for n_apoios, vao_cm in ((2, vao_2), (4, vao_4))
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
# Referência: Orguel SJC padrão de mercado regional
PRECO_POR_KG_MES_BRL = 1.11
