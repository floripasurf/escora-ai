# Orguel Gold Standard — Regras Extraídas de Projetos Executivos Reais (DXF)

Data: 2026-06-12. Análise via ezdxf 1.4.3 (scripts em `scripts/orguel_*.py`,
dados intermediários em `output/orguel_analysis/`). Unidade dos 3 desenhos:
**centímetros** (deduzido por bbox, comprimentos de blocos VM e cotas).
Todos os valores abaixo já convertidos para metros, histogramas arredondados
a 5 cm.

Arquivos analisados:

1. `78579-12-PE-PAVTO TIPO-TORRE B-LT02-R00.dxf` — alvenaria estrutural,
   lajes maciças, escoras ESC310 (Mecanor 2.00–3.10 m) + guias VM80.
2. `59428-14-PE-ESCTO - PAVTO TIPO(3º AO 25º) - TORRE D-R00.dxf` — estrutura
   convencional (vigas 14/63, 19/63, 19/76; lajes maciças h=10 e h=12 cm),
   torres + ESC310/ESC450, guias VM130.
3. `84678-21-PE-TERREO-PERIFERIA-TRECHO8-R01.dxf` — térreo/periferia/transição
   (laje h=12; transição h=30), torres + ESC450, guias VM130, prancha de
   reescoramento e prancha "LAY-OUT DAS TORRES E VIGAS METÁLICAS".

## 1. Simbologia e organização do desenho (comum aos 3 arquivos)

- **Camadas de escoramento** seguem o padrão `{EQUIP}_{Laje|Viga}`:
  `ESC310_Laje`, `ESC310_Viga`, `ESC450_Laje`, `VM80_Laje`, `VM80_Viga`,
  `VM130_Laje`, `VM130_Viga`, `VM50`, `TORRE_LAJE`/`Torre_Laje`,
  `TORRE_VIGA`, `TA_Viga` (tubos/diagonais), `SF250_Laje`/`SF500_Viga`
  (suporte p/ forcado), `Tirante_Viga`/`Barra_Viga` (travamento lateral),
  `CORTE` (detalhes), `LISTAMAT` (lista de materiais), `Madeira`.
- **Escoras telescópicas** são INSERTs com nome = modelo + tipo de forcado:
  `ESC310-FFS` (forcado fixo simples), `ESC310-FFD` (forcado fixo duplo),
  `ESC450-FFS`, `ESC450-REESC`/`ESC310-REESC` (reescoramento),
  `TRIPEESC` (tripé, símbolo separado ao lado da escora),
  `ESC310-CRUZ` (conjunto escora+cruzeta — usado SOB VIGAS).
- **VMs são INSERTs, não linhas**: bloco `VM{80|130|50}-{comprimento em cm}`
  desenhado do ponto de inserção ao longo de +X com o comprimento real
  (ex.: `VM80-155` = polilinha de 0 a 155 cm), rotação do INSERT dá a direção.
  VM50 ganha sufixo `-TRAV` (travamento).
- **Torres** são INSERTs com nome codificando os painéis: `1001000`
  (painel 1000×1000), `1541000` (1540×1000), `1001250`, `1001550`,
  `100100+1550`, `100155+2050`, `154100+1550` (composições painel+painel/
  extensão). Footprint em planta: 1.00 m ou 1.54 m. `Console-fad` = console
  com forcado ajustável acoplado à torre (94 ocorrências no 59428).
- Pranchas separadas por escopo: "ESCORAMENTO DAS LAJES" e "ESCORAMENTO DAS
  VIGAS" são plantas distintas do mesmo pavimento; reescoramento idem.
- Quadro de notas padrão Orguel (extraído integral do 78579): destaque para
  a **nota 15** ("A ORGUEL NÃO DETERMINA O ESPAÇAMENTO DOS BARROTES 8x8,
  7x7, 6x6 DE MADEIRA... responsabilidade do cliente") e **nota 17**
  ("serão enviados (n) TRIPÉS = 30% da quantidade total", remanejados na
  montagem). No 59428 há nota específica: "FORAM CONSIDERADOS **60% DE
  TRIPÉS** DO TOTAL DE ESCORAS, CONFORME SOLICITADO" — o ratio é negociável.
- Bloco "REFERÊNCIAS TÉCNICAS" repete o catálogo: VM80 212 kgf.m,
  VM130 516 kgf.m, H20 500 kgf.m, ALU14 409 kgf.m, ALU20 800 kgf.m
  (bate com manual §13.3).

## 2. Arquivo 78579 (alvenaria estrutural, lajes maciças, ESC310 + VM80)

### Inventário de escoramento

| Item | Qtde | Camada |
|---|---:|---|
| ESC310-FFS | 323 | ESC310_Laje |
| TRIPEESC | 253 | ESC310_Laje |
| ESC310-FFD | 57 | ESC310_Laje |
| VM80-155 / 205 / 100 / 255 / 310 / 360 | 154/123/99/55/12/4 | VM80_Laje + VM80_Viga |
| VM50-155-TRAV | 27 | VM50 |
| Torres (1541000, 100100+1000, 1001550, 1002050) | 48 | Torre_Laje (sacadas) |
| TA-150 / TA-100, TUBO-DIAG | 28/6/48 | TA_Viga |

Sem VM130 no pavimento: as guias de laje são **VM80** (vãos curtos de
alvenaria estrutural). Comprimentos dominantes VM80: 1.55 e 2.05 m (59%).

### Sistema observado

Linhas de guia VM80 sobre forcados FFS/FFD; escoras ao longo da linha;
barrotes de madeira (cliente, nota 15) por cima — **o projeto Orguel não
desenha barrote de madeira nem compensado**.

- Escoras ao longo da guia (linha y=-156.4 exemplo bruto): passo constante
  **1.085 m** por ~29 m contínuos atravessando o pavimento inteiro (linhas
  alinhadas entre regiões — grid de linhas global, sim).
- Cotas anotadas na planta de lajes (histograma DIMENSION, cm):
  100×66, 30×72, 28×45, 25×20, 109×19, 20×18, 21×14, 138×13, 155×12,
  81×12, 205×12, 154×12, 71×12, 136×8, 131×8, 114×5 →
  **espaçamentos de projeto 1.00 / 1.09 / 0.81 / 0.71 / 1.14–1.38 m**
  (o restante são larguras de parede/viga e comprimentos de VM/painel).
- NN direcional das escoras (FFS+FFD, m): dX → 1.10×38, 0.50×36, 0.45×32,
  0.60×29, 1.00×23, 1.15×15, 1.50×15; dY → 0.50×48, 0.45×28, 0.90×22,
  1.70×16, 1.40×14. Os picos 0.45–0.72 são **pares de escoras nos
  transpasses de VM e sob vigas/sacadas**, não passo de grid.
- **Emendas de VM80 por transpasse (sobreposição)**: gaps entre segmentos
  colineares consecutivos são NEGATIVOS, moda **-0.65/-0.70 m** (17+11
  ocorrências) — duas VMs sobrepõem ~0.65–0.70 m na emenda e cada
  extremidade recebe escora própria (por isso os pares 0.70 m).
- Sob vigas/sacadas (87 escoras a <0.20 m de linha de viga): passo
  0.50–0.60 m dominante (dX 0.50×8, 0.60×4; dY 0.50×8).
- Torres (apenas nas sacadas): NN **2.45–2.50 m** (20+8 de 48), painel
  1000/1540; travadas com tubos diagonais (TA) e VM50-155 c/**1.10 m**
  (passo medido 1.10×19).

## 3. Arquivo 59428 (estrutura convencional, torres + ESC, VM130)

### Inventário de escoramento (cluster principal, plantas lajes+vigas)

| Item | Qtde | Camada |
|---|---:|---|
| ESC310-CRUZ (escora+cruzeta) | 225 | ESC310_Viga |
| ESC310-FFS / FFD | 84 / 38 | ESC310_Laje |
| TRIPEESC | 58 | ESC310_Laje |
| VM130-255/205/310/410/360/155 | 130/80/44/39/36/32 | VM130_Laje + VM130_Viga |
| VM80-255/205/310/155/360 | 74/40/20/13/6 | majoritariamente VM80_Viga |
| Console-fad | 94 | TORRE_VIGA |
| Torres laje (1541000, 1001250, 100155+2050...) | 44 | TORRE_LAJE |
| Torres viga (1001000, 1002050...) | 42 | TORRE_VIGA |
| SF250-FAD (suporte forcado) | 24 | SF250_Laje |
| Tirantes (furo laje + PORCAV + TIRANTE-65) | 156+156+5 | Tirante_Viga / Barra_Viga |

Equipamentos na LISTAMAT: Mecanor 2.00–3.10 m E 3.00–4.50 m, cruzeta,
forcados (FFS/FFD/FAD), painéis 1000×1000/1250/1500 e 1540×1000/1500,
ponta móvel, suporte p/ forcado 250, tripé mod. 4.

### Estatísticas

- **Sob vigas** (ESC310-CRUZ, NN direcional, m): dX → 0.55×37, 0.60×36,
  0.50×6, 0.45×4 (picos 1.65/2.30 = vãos entre vigas); dY → 0.55×42,
  0.60×27, 0.50×20. Cotas anotadas: 60×39, 65×16, 50×12, 57×10, 52×8,
  53×8, 59×7, 56×6, 55×4 → **conjunto escora+cruzeta a cada 0.50–0.65 m
  sob vigas** (cruzeta:escora = 1:1, confirmando manual §10.3, porém mais
  denso que os 0.80 m do manual).
- **Lajes** (h=10–12 cm, ESC310-FFS/FFD sob guias VM130): espaçamento ao
  longo da guia (associação escora→linha VM130, m): **2.00×40**, 1.50×17,
  1.15×13, 2.95×8. Cotas: 100×54, 200×12, 152/148/167/146/176/159 (pitch
  entre linhas por painel). NN direcional: dY → 2.00×24, 1.55×16, 1.00×12,
  1.50×10, 1.25×8; dX → 1.50×12, 1.15×11, 0.70×10.
- **Pitch entre linhas de guia VM130**: 1.10–1.80 m, disperso (0.75–1.25
  e 1.4–1.8) — calculado por painel (vão/n), não tabelado fixo.
- **Direção das guias**: VM130 192 horizontais × 130 verticais — direção
  definida POR PAINEL (perpendicular ao vão menor), não única por pavimento.
- **Extensão das guias**: distância da extremidade do run de VM130 à face
  de viga perpendicular mais próxima: moda **0.00 m** (37 de 170 medições;
  ±0.20 m concentra a maioria) → **a guia para na face da viga de
  concreto**, não na borda do painel teórico nem por cima da viga.
- **Emendas VM130 com transpasse**: gaps colineares negativos, moda
  -0.55/-0.75 m (e -2.05 = VMs lado a lado em paralelo duplo).
- **Torres na laje**: NN 2.25–2.95 m (moda 2.50–2.75), painéis 1540×1000 e
  1000×1250. **Torres sob vigas**: NN bimodal **1.50–1.55 m** (8+8) e
  2.40–3.10 (6+4+4) — 1.50 m onde a carga manda (bate com manual §10.3).
- Consoles-fad ao longo das torres: passo 1.00×16 / 2.05×14 / 1.55×12.
- Travamento lateral de vigas altas (19/76): **tirantes através de furo na
  laje** (blocos `furo laje` + `PORCAV` + `TIRANTE-65`), 156 conjuntos.
- Guarda-corpo: "fixado no barrote no máx. a cada 1.5 m, pranchas pelo
  cliente".

## 4. Arquivo 84678 (térreo/periferia/transição, ESC450 + VM130)

- LISTAMAT: Mecanor **3.00–4.50 m** (ESC450) dominante + 2.00–3.10;
  cruzeta 3–4.5 m; suporte p/ forcado 500; painéis até 1540×1500.
- Cluster 0 ("lay-out torres e VMs", 1:50): torres laje NN **2.55 m**
  (20 de 32; painel 1540 → vão livre ~1.0 m entre torres); torres viga NN
  1.25–3.15 (disperso); VM130 runs dominantes de **3.10 m** (51×) e 3.60
  (24×) apoiados nas torres, transpasse de novo -0.45/-0.55/-0.70;
  pitch entre linhas VM130 ~0.90 m (7×) e 1.40–1.50.
  Escoras complementares: dX 1.20×12, 1.30×4; dY 1.55×16, 1.10×12.
- Cluster 1 (**reescoramento**, ESC450-REESC 96 + FFS 50): grid regular
  **1.00–1.10 × 1.20–1.25 m** (dX 1.10×40, 1.00×40, 0.85×26;
  dY 1.25×57, 1.20×21, 1.15×9).
- Legenda da prancha de lay-out: "**VM 80 - c/48**" ao lado de "VM 130" →
  barrote metálico VM80 com passo **48 cm ≈ 2.44 m / 5** (fração da chapa,
  igual à regra do engine). Única menção explícita a passo de barrote nos
  3 arquivos.
- Regra de gancho de reescoramento anotada: "A = h da laje + h da VM +
  8 cm (folga); L = largura da VM + 8 cm (folga); ganchos a cargo do
  cliente (sugestão ferro ø1/2\")".
- Acessórios de periferia: réguas 834/1668 (simples/duplo encaixe),
  cabeçal de espera, sarrafos 7.5/30, TA 200, ALU14, VM50-410/360/310-TRAV.

## 5. Regras inferidas (metodologia Orguel)

1. **Laje não é grid xadrez de escoras: é sistema de LINHAS de guia.**
   Guia metálica (VM80 em obra de vão curto; VM130 em convencional) sobre
   forcados; escoras ao longo da linha; barrotes (madeira do cliente ou
   VM80 c/48) por cima. A "unidade" de projeto é a linha, não o ponto.
2. **Espaçamento de escora ao longo da guia** depende da guia e da carga:
   VM80+laje maciça alvenaria → 1.00–1.09 m (máx. obs. 1.5);
   VM130+laje h=10–12 → 1.50–2.00 m (moda 2.00). Pitch entre linhas:
   1.10–1.80 m, calculado por painel (vão/n inteiro), não tabela fixa.
3. **Sob vigas: escora+cruzeta 1:1 a cada 0.50–0.65 m** (cotas 50–65 cm);
   torres sob vigas a 1.50–1.55 m onde substituem escoras; consoles-fad
   nas torres a 1.00–2.05 m.
4. **Torres em laje a 2.45–2.75 m centro-a-centro** (painéis 1.00/1.54 m,
   vão livre ~1.0–1.2 m), guias VM130-310/360 vencendo o vão entre torres.
5. **Emendas de VM sempre por transpasse de 0.45–0.75 m** (moda 0.65–0.70),
   com apoio (escora/forcado) em CADA extremidade do transpasse → pares de
   escoras a 0.45–0.72 m nas emendas. Comprimentos usados: kit
   1.00/1.55/2.05/2.55/3.10/3.60/4.10 (catálogo §13.3), com 1.55+2.05
   dominando em pavimento tipo e 3.10/3.60 em torres de transição.
6. **Guia termina na face da viga de concreto** (gap modal 0.00 ± 0.20 m);
   não atravessa a viga nem se estende à borda teórica do painel.
7. **Direção das guias é decidida por painel** (perpendicular ao vão
   menor); num mesmo pavimento convivem ~50/50 horizontais e verticais.
   Mas as linhas são contínuas e alinhadas através de ambientes quando o
   sistema permite (78579: linha única de 29 m com passo 1.085).
8. **Tripés = 30% das escoras (padrão; até 60% a pedido)** — item de BOM.
9. **Reescoramento é prancha própria**, blocos `*-REESC`, grid regular
   ~1.0–1.1 × 1.25 m, ganchos com folga de 8 cm.
10. **Travamento**: VM50-TRAV c/1.10 m; vigas altas com tirante por furo
    na laje (tirante+porca+barra); torres de sacada com tubos diagonais TA.

## 6. Divergências vs engine atual

| # | Regra atual do engine | Observado nos projetos Orguel | Impacto |
|---|---|---|---|
| 1 | Grid global de escoras com passos padrão 0.80/1.00/1.20 m (`grid_distributor` + `compute_adaptive_spacing`), VM grid derivado DEPOIS das escoras (`vm_grid_builder` consome ShorePoints) | Ordem inversa: primeiro linhas de guia (direção+pitch por painel), depois escoras sobre as linhas; passo ao longo da linha chega a **2.00 m** com VM130 verificada (lajes h≤12), e o pitch entre linhas (1.1–1.8 m) é "vão/n", não passo de catálogo | Alto — muda a topologia da solução e reduz nº de escoras em até ~40% em laje fina com VM130 |
| 2 | Eixo de barroteamento único por pavimento (`primary_axis` único por laje/pavimento) | Direção da guia definida por painel (50/50 H/V no mesmo pavimento), perpendicular ao vão menor de cada painel | Alto — afeta todos os painéis não alongados |
| 3 | Guias VM130 estendidas até as bordas do painel (`vm_grid_builder` cobre o bbox) | Guia para na FACE da viga de concreto (gap modal 0.00±0.20 m); sob a viga o escoramento é outro subsistema (cruzetas/torres) | Alto — DXF e BOM atuais esticam VM além do real |
| 4 | Seleção de 1 VM por segmento (menor comprimento ≥ vão, `select_vm_length_mm`) sem emenda explícita | Runs montados com peças de estoque emendadas por **transpasse 0.45–0.75 m**, escora sob cada ponta do transpasse; emenda NUNCA é topo-a-topo | Alto — BOM de VM e contagem de escoras subestimados; manual §11.2 ("barrote extra por emenda") confirmado e quantificado |
| 5 | Sob vigas: `ESPACAMENTO_MAX_VIGA = 1.00` (manual §10.3 fala 0.80 alvo / 1.00 teto) | Prática Orguel: 0.50–0.65 m (cotas 50–65; NN 0.55–0.60) com cruzeta 1:1; torres sob viga a 1.50–1.55 m | Médio/Alto — engine pode estar não conservador vs prática Orguel em vigas pesadas |
| 6 | Torres: espaçamento dirigido por VM/capacidade, sem padrão de malha | Malha de torres 2.45–2.75 m c-a-c (vão livre ~1.0–1.2 m), guias VM130-310/360; consoles-fad p/ complementar bordas | Médio — calibrar tower_selector p/ esses passos |
| 7 | Barrote sempre VM80 com passo = fração da chapa | Confirmado quando barrote é metálico ("VM 80 - c/48" ≈ 2.44/5) — MAS na maioria dos projetos o barrote é madeira do cliente e NÃO é desenhado/quantificado (nota 15) | Médio — BOM/DXF devem ter modo "barrote do cliente" (só guias + escoras) |
| 8 | Tripés não modelados no BOM | 30% das escoras (padrão, nota 17) ou % negociado (60% no 59428) | Baixo/Médio — item de BOM fácil |
| 9 | Travamento lateral de vigas via VM50 genérico | VM50-TRAV c/1.10 m; vigas altas exigem tirantes com furo na laje (kit tirante+porca, 156 conjuntos no 59428) | Médio — regra §15.2 ganha quantificação |
| 10 | Saída DXF com pontos/círculos e camadas próprias | Simbologia Orguel: blocos nomeados por equipamento+comprimento, camadas `{EQUIP}_{Laje|Viga}`, plantas separadas lajes/vigas, unidade cm | Médio — adotar p/ saída "parecer projeto Orguel" |

## 7. Recomendações de mudança no engine (ordem de impacto)

1. **Refatorar o posicionador de laje para "line-first"**: gerar linhas de
   guia por painel (direção = perpendicular ao vão menor; pitch = vão/n com
   verificação do barrote/madeira), depois posicionar escoras sobre as
   linhas com passo verificado pela VM (M=qL²/8, flecha) e pela capacidade
   da escora — permitindo passo até 2.00 m com VM130 em laje fina, em vez
   do teto fixo 1.20.
2. **Permitir eixo de guia por painel** (remover suposição de eixo único
   por pavimento); manter alinhamento/continuidade das linhas entre
   painéis adjacentes quando a direção coincidir.
3. **Parar as guias na face das vigas de concreto** (recorte do painel
   pela face real, gap 0) e tratar o sob-viga como subsistema próprio
   (cruzeta 1:1 c/0.55–0.60, ou torre c/1.50).
4. **Modelar emendas por transpasse**: compor runs com peças do catálogo
   sobrepondo 0.65–0.70 m por emenda, adicionar 1 escora/forcado por ponta
   de transpasse; atualizar `vm_grid_bom_summary`/`aggregate_vm_bom` e o
   desenho DXF (duas linhas paralelas curtas na emenda).
5. **Calibrar sob-vigas**: default Orguel-like 0.60 m (com teto 0.80/1.00
   do manual) para conjunto escora+cruzeta; espelhar a malha de torres
   2.45–2.75 m em laje e 1.50–1.55 m sob vigas no `tower_selector`.
6. **BOM**: adicionar tripés (= 30% escoras, parametrizável), VM50-TRAV
   (passo 1.10), kit tirante para viga alta, consoles de torre; modo
   "barrote de madeira do cliente" (excluir barrote do BOM e do DXF, como
   Orguel faz — nota 15).
7. **Saída DXF estilo Orguel**: camadas `{EQUIP}_{Laje|Viga}`, blocos
   `ESCxxx-FFS/FFD/CRUZ`, `VMxx-<cm>`, torres `WWWHHHH`, plantas
   lajes/vigas separadas, cotas dos passos (c/60, c/100, c/200) e quadro
   de notas padrão.
8. **Gold-standard tests** (manual §28.4 item 6): usar 59428 cluster
   principal (escoras sob vigas 0.55–0.60; laje 2.00 ao longo de VM130;
   torres 2.5–2.75) e 84678 cluster 1 (reescoramento 1.0–1.1×1.25) como
   fixtures de regressão numérica.

---

# Parte 2 — projetos restantes (8 arquivos, análise 2026-06-12)

Mesma metodologia da Parte 1 (`scripts/orguel_extract_all.py` +
`scripts/orguel_part2_battery.sh`, dados em `output/orguel_analysis/`).
**Unidade dos 8 desenhos: centímetros** (verificado por nome de bloco VM/ALU
vs comprimento geométrico). Todos os valores abaixo em metros. Nenhum arquivo
estourou memória/tempo (maior: 97661, 110 MB, 265 k entidades, ~1 min).

## 8. Arquivo 35412 (cobertura, torres + VM130, ESC310-CRUZ)

- Sistema "torre-first": prancha "LAY-OUT DAS TORRES E VIGAS METÁLICAS".
  Inventário: VM130-360 (112), Console-fad (68), TA-50..250 (218),
  ESC310-CRUZ (51), torres 1001000 (44) + 1001550/composições, SF250-FAD
  (44), TIRANTE-100 (35) + Porca Barra Ancoragem (32), H20-450 (8!).
- **Torres laje NN 2.25–2.50 m**; **torres sob viga NN 1.25–1.60 m**
  (1001000 dominante) — sob viga de cobertura a malha fecha p/ ~1.4 m.
- VM130: runs dominantes 3.60 m (59×) vencendo o vão entre torres;
  transpasses −0.85/−0.95; pitch entre linhas ~1.00 m (11×).
- Escoras complementares ao longo de VM: passo 1.60–1.75 m.
- End-gap VM130→face de viga: +0.30 m modal (34×) — guia para ANTES da face.
- Cotas: 1.00 (122), 0.50 (59), 1.55 (43), 1.25/1.50 (22 cada).
- Notas novas: "CONSIDERAR 2xVM80 NAS VIGAS PERPENDICULARES À LONGARINA",
  "VIGA NA BASE DA TORRE", "TUBO DE TRAVAMENTO NO PÉ DA TORRE",
  "VM80 DE APOIO PARA O SUPORTE DE FORCADO"; legenda "VM 80 - c/48" repete.

## 9. Arquivo 110749 (laje nervurada h=30, 410 kgf/m², ALU14 + VM80)

Sistema NOVO: **viga primária ALU14 + secundária VM80** (sem compensado nas
nervuras, "execução das nervuras com régua"; capitéis c/ compensado 14 mm).

- ESC310-FFD = 183 de 190 escoras (**forcado duplo dominante**, segura as
  2 ALU lado a lado); ALU14-350 (107) + 150/250/300/400 (catálogo LISTAMAT
  ALU14 1500–4500 mm); torres 1001000 (77) e SÓ 5 tripés em planta.
- **Grid de escoras 1.00 × 2.85 m** (dX 1.00×70; dY 2.85×77; ao longo das
  linhas verticais de ALU14: 2.85×121). Pitch entre linhas ALU = 1.00 m
  (cota 1.00×69). Passo 2.85 = ALU 3.50 − transpasse (~0.65); escora fica a
  ~0.60–0.70 da extremidade de cada peça (medido), 1 escora por peça.
- Emendas de ALU14 também por transpasse: −0.45/−0.55 m.
- **Texto de calibração-chave**: "PARA LAJE MACIÇA: VM 80 C/36.7 cm" e
  "PARA LAJE NERVURADA: VM 80 C/60 cm" → o passo do barrote VM80 depende do
  tipo de laje (36.7 ≈ 1.10/3 da chapa; 60 = nervura).
- Torres laje NN 2.45–2.85 m (moda 2.60). Pé-direito 3.24 m.

## 10. Arquivo 101112 (prédio industrial de desaguamento, ALU14 + torres 2050)

- Mesmo sistema ALU14: legenda explícita "**VIGA PRIMÁRIA (ALU14)** /
  **VIGA SECUNDÁRIA (VM80)**" + "POSTE ESCORAMENTO" + "VIGA ORGUEL (BARROTE)".
- Pé-direito alto: painéis de torre **2050** (1002050 = 20 de 39 torres);
  torres sob viga NN 1.95–2.55 m; torres laje (1001000) NN 1.75–1.80 m.
- Nota nova: "**2x ALU14 P/ APOIO DA TORRE**" (torre apoiada em par de ALU).
- Escoras: NN 1.00 m dominante (26×); ao longo de ALU 1.0–1.9.
- Regra de gancho generalizada: "L = largura da 2 VM 130 **ou PERFIL I**
  + 8 cm (folga)". Cotas: 1.00 (41), 0.50 (26), 1.25 (16), 1.50 (14).

## 11. Arquivo 87845 (2º pavimento, ESC310 + VM130 + reescoramento + tirantes)

- Inventário pesado de travamento: PORCABARRA (805) + TIRANTE-65 (663) +
  TIRANTE-100/150, DetalheTravv (107), APRUMADORPILAR (32), CANTFIX (31),
  **ESC310I/ESC310S em pares (32/32 — escora inclinada de aprumo)**.
- Reescoramento na mesma prancha-arquivo: ESC310-REESC 255 + ESC450-REESC 85.
- Escoras de laje ao longo de VM130: **1.40×33, 1.85×30, 1.0–1.95 disperso**
  (passo calculado por painel, não tabelado).
- Sob vigas: cruzetas 350; cota dominante **0.60 m (127×)**.
- VM130: transpasses −0.70/−0.80; runs 2.55/4.10/3.10.
  **End-gap +0.30/+0.35/+0.40 m modal (146 de 246)** — guia para
  0.3–0.4 m antes da face da viga (difere do flush do 59428).
- Torres escassas (49) e periféricas: NN 2.85–4.5 (sem malha regular).

## 12. Arquivo 104004 (térreo R02, vigas oblíquas + travamento de pilares)

- Prancha de escoramento de VIGAS (cluster 0: 141 torres + 187 cruzetas +
  370 VM130) + **2 pranchas só de travamento** (clusters 1–2: 671 VM50-TRAV).
- **Edifício não-ortogonal**: VM130 em 35 ângulos distintos (114°, 66°, 24°,
  9°...) — a direção da guia ACOMPANHA cada viga, não eixo global.
- Torres sob vigas NN 1.45–2.7 m (moda 1.9–2.4), painéis altos
  (1002050=28, composições 100205+2050); escora+cruzeta c/0.45–0.66
  (cotas 0.45–0.66 somam ~80).
- **Travamento de pilares em escala industrial**: PORCABARRA 1779 +
  TIRANTE-65 1441 + TIRANTE-100 262 + APRUMADORPILAR 94 + CANTFIX 240 +
  VM50-{100..410}-TRAV 667. Térreo de pé-direito alto = projeto de
  travamento próprio, tão grande quanto o de escoramento.
- Cotas: 1.00 (92), 1.55 (74), 0.50 (71), 2.05 (54).

## 13. Arquivo 105475 (1º subsolo Plaenge, trecho 3 — o mais "didático")

- ESC310-FFS (108) sob VM130 verticais; torres 1001550 (33).
- **Escoras ao longo da guia: 1.00–1.55 m (moda 1.35 e 1.00)**; pitch entre
  linhas VM130 0.95–1.25 m; cota repetida 1.33 (36×) = pitch por painel.
- **Torres laje NN 2.35 m (16 de 29)** — malha regular de 1001550.
- VM130: runs 3.60 (58×); transpasses −0.35..−0.60;
  **end-gap modal 0.00–0.125 m (62 de 108) → guia na face da viga**
  (confirma o flush do 59428).
- Textos: "**barrote 48cm**" (10×), "**barrote no capitel a cada 48cm**",
  "RETIRADA DO ESCORAMENTO DEVERÁ SER DO MEIO DO VÃO PARA OS APOIOS",
  "Faixa de reescoramento".

## 14. Arquivo 92056 (1º subsolo torre B, 5 pranchas, reescoramento 1.8×1.4)

- **Cinco plantas do mesmo nível**: "ESCORAMENTO DAS LAJES", "ESCORAMENTO
  DAS VIGAS", "REESCORAMENTO DAS LAJES E VIGAS", "TRAVAMENTO DAS VIGAS",
  "TRAVAMENTO DOS PILARES" (+ cita NBR 15696 nominalmente).
- Lajes: ESC310-FFS/FFD ao longo de VM130: 1.00×89, 1.25–1.60 (picos 3.3/3.85
  = vãos sobre vigas); dY FFS 1.55×107. Pitch linhas VM130 0.9–1.45.
- **Reescoramento (cluster 1, 827 REESC): grid 1.80 × 1.40 m** (dX 1.80×268;
  dY 1.40×317; cotas 1.80×178, 1.43×89) — bem mais largo que o 1.0×1.25 do
  84678: grid de reescoramento é dimensionado por projeto.
- Torres laje 1001550: NN 2.35–2.45; torres viga NN 3.0–3.35 (+ Console-fad
  126). VM130 oblíquas 168°/78° acompanham ala inclinada do edifício.
- VM130 end-gap +0.30 modal; transpasses −0.55 mas também gaps POSITIVOS
  +0.20/+0.25 (41×) = runs interrompidos (consoles/torres entre eles).
- ESC310I/S 100 pares (escoras inclinadas); TA-300 (70) diagonais.

## 15. Arquivo 97661 (cobertura 2 folhas — o maior; Mecanflex + ESC450)

- Maior amostra: 2009 escoras, 1433 cruzetas, 1115 "torres", 1239 VM130.
  ESC310-CRUZ 1309 (!) sob vigas de cobertura 19/95–19/165; ESC450-FFS/FFD
  740; SF250/SF500-FAD; 4 pranchas-detalhe "MONTAGEM DAS TORRES".
- **Sistema NOVO: "ANDAIME MULTIDIRECIONAL MECANFLEX PARA ESCORAMENTO DE
  SACADAS"** — postes (bloco ETI/POSTE PLANTA, 768) em **malha perfeita
  1.50 × 1.20 m** (dX 1.50×704; dY 1.20×352), travessas "Tr 1.50"
  (LC150VP, 200) e pinças (pincaP, 200).
- Lajes: escoras ao longo de VM130 **moda 1.20–1.40 m** (1.20×169, 1.25×142,
  1.35×97, 1.40×88, 1.00×86); ao longo de VM80 moda 1.00–1.45.
- VM130: transpasses fortíssimos −0.60 m (68×) horizontais, −0.65..−0.85
  verticais; runs 1.55/2.05 dominantes (kit curto, muitas emendas).
- End-gap VM130 bimodal: **+0.10 (190×) e +0.30/+0.35 (340×)** —
  cobertura também para a guia antes da face.
- Torres laje NN 2.2–3.9 (esparso); torres sob viga 1.65 e 3.2–3.6;
  REESC grid irregular ~1.05–1.20 × 0.95–2.4.
- Cotas: 1.50 (236!), 0.30 (221), 0.50 (139), 1.00 (136) — o 1.50/1.20 do
  Mecanflex e o 0.30–0.50 do sob-viga dominam o desenho.

---

# Síntese consolidada (11 projetos)

## Espaçamentos dominantes consolidados

| Subsistema | Faixa observada (11 proj.) | Moda global |
|---|---|---|
| Escora ao longo de guia VM130 (laje) | 1.00–2.00 m | **1.20–1.55 m** (2.00 só no 59428 laje h≤12; 1.00 recorrente em todos) |
| Escora ao longo de guia VM80 (laje) | 0.85–1.45 m | **1.00–1.09 m** |
| Pitch entre linhas de guia | 0.90–1.80 m | **0.95–1.35 m** (vão/n por painel; cota 1.33 no 105475) |
| Escora+cruzeta sob viga | 0.45–0.66 m | **0.50–0.60 m** (cotas 0.60×127 no 87845, 0.60×88 no 92056) |
| Torre em laje (c-a-c) | 2.20–2.90 m | **2.35–2.60 m** (2.35×16 no 105475; 2.60×29 no 110749) |
| Torre sob viga (c-a-c) | 1.25–2.55 m | **1.35–1.60 m** (cobertura) / 1.9–2.4 (térreo alto) |
| Transpasse de emenda VM/ALU | 0.35–0.95 m | **0.45–0.70 m** |
| Grid ALU14 (primária 1.00 m × escora) | — | **1.00 × 2.85 m** (FFD) |
| Barrote VM80 (quando metálico) | — | **c/48** (padrão), **c/36.7** maciça, **c/60** nervurada |
| Reescoramento (grid) | 1.0×1.25 a 1.8×1.4 m | dimensionado por projeto |
| Mecanflex (postes) | — | **1.50 × 1.20 m** |

## Confirmação/refutação das regras da Parte 1 (amostra 11 projetos)

| Regra Parte 1 | Veredicto | Evidência ampliada |
|---|---|---|
| 1. Sistema de LINHAS de guia, não grid de pontos | **CONFIRMADA** | Escoras associadas a linhas de VM em 87845/105475/92056/97661; novo sistema ALU14 é igualmente line-first em 2 níveis |
| 2. Passo ao longo da guia 1.5–2.0 (VM130) | **REFINADA** | Moda global 1.20–1.55 m; 2.00 m foi o EXTREMO (59428, laje h≤12). Distribuição real: 1.0–1.55 domina 6 de 8 projetos novos |
| 3. Sob viga 0.50–0.65 m, cruzeta 1:1 | **CONFIRMADA (forte)** | 104004 (cotas 0.45–0.66), 87845 (0.60×127), 92056, 97661 (1309 CRUZ); torres sob viga 1.35–1.65 na cobertura |
| 4. Torres laje 2.45–2.75 m | **REFINADA p/ 2.35–2.85** | 105475: 2.35; 92056: 2.35–2.45; 110749: 2.60; 35412: 2.25–2.50 — faixa desce a 2.35 e o painel 1540 não é pré-requisito (1001550/1001000 dominam) |
| 5. Emendas por transpasse 0.45–0.75 | **CONFIRMADA** | Em TODOS os arquivos com VM130/VM80/ALU14 (até −0.95 na cobertura); exceção: 92056 tem runs com gap +0.20/0.25 (interrupção em console/torre, não emenda) |
| 6. Guia para na FACE da viga (gap 0) | **REFUTADA como universal → faixa 0 a +0.40** | Flush só em 59428 e 105475; 87845/92056/35412/97661 param a guia 0.10–0.40 m ANTES da face (modas +0.30/+0.35). Regra segura p/ engine: 0 ≤ gap ≤ 0.40, nunca atravessar |
| 7. Direção da guia por painel | **CONFIRMADA E AMPLIADA** | 97661 ~50/50 H/V; 104004 e 92056: em edifício não-ortogonal a guia acompanha o ÂNGULO de cada viga/ala (35 direções no 104004) |
| 8. Tripés = 30% (negociável) | **CONFIRMADA como item de BOM** | Símbolos em planta variam 3–29% (110749: 5; 97661: 566 ≈ 29%); o % é do BOM, não da planta |
| 9. Reescoramento prancha própria, grid ~1.0–1.1×1.25 | **CONFIRMADA a prancha; grid REFUTADO como fixo** | 92056: 1.80×1.40 (n=827, regularíssimo). Grid de reescoramento é calculado por projeto (carga/ciclo), não constante |
| 10. VM50-TRAV c/1.10 + tirantes p/ vigas altas | **CONFIRMADA E AMPLIADA** | 104004/87845/92056: kits de tirante na casa dos MILHARES; travamento vira prancha própria (pilares E vigas) |

## Regras NOVAS (só visíveis nos projetos maiores)

1. **Sistema ALU14 primária + VM80 secundária** (lajes nervuradas e obra
   industrial — 110749, 101112): linhas de ALU14 a **1.00 m**; escoras com
   FORCADO DUPLO a **2.85 m** ao longo da linha (= peça 3.50 − transpasse
   0.65, 1 escora por peça a ~0.65 da ponta); barrote VM80 por cima com
   passo POR TIPO DE LAJE (c/36.7 maciça, c/60 nervurada); torre apoia em
   **2x ALU14**; nervuras executadas com régua, sem compensado.
2. **Andaime multidirecional Mecanflex** para sacadas/bordas de cobertura
   (97661): malha de postes **1.50 × 1.20 m**, travessas Tr 1.50, pinças —
   terceiro sistema vertical além de escora e torre.
3. **Cobertura é torre-first** (35412, 97661): malha de torres + VM130-360
   no lugar de escoras isoladas; torres sob viga fecham para 1.25–1.65 m;
   exige "viga na base da torre" + "tubo de travamento no pé da torre" e
   2xVM80 nas vigas perpendiculares à longarina; aparecem SF250/SF500 e até
   H20 de madeira como acessório.
4. **Pé-direito alto muda o painel, não a malha**: painéis 2050
   (1002050/100205+2050) entram no térreo/industrial/cobertura; NN das
   torres sobe só ~10–20% (1.9–2.55 sob viga).
5. **Travamento é um projeto em si** nos térreos/subsolos: pranchas próprias
   de TRAVAMENTO DE VIGAS e DE PILARES com kit tirante (PORCABARRA +
   TIRANTE-65/100/150), APRUMADORPILAR, CANTFIX e VM50-TRAV aos milhares
   (104004: 1779 porcas + 1441 tirantes-65).
6. **Escoras inclinadas em pares ESC310I/ESC310S** (aprumo/escora de talude
   de fachada) presentes em todos os projetos grandes (até 100 pares).
7. **Edifício não-ortogonal**: a direção da guia segue cada viga
   individualmente (104004: 35 ângulos) — o engine precisa aceitar eixo de
   barroteamento POR VIGA/painel oblíquo, não apenas H/V.
8. **Reescoramento dimensionado por projeto**: grids reais de 1.0×1.25 até
   1.8×1.4 — modelar como cálculo (carga de reescoramento/decréscimo de
   carga, tabela citada nos desenhos), não como constante.
9. **Retirada do escoramento do meio do vão para os apoios** (105475) e
   "TABELA DE DECRÉSCIMO DE CARGA" / "TABELA DE CONSUMOS DO PAVIMENTO"
   (97661) — candidatos a saída documental do engine.
