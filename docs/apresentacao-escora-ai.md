# Escora.AI — Apresentação Técnica e Comercial

## Cálculo Automatizado de Escoramento com Inteligência Artificial

---

## O Problema

O cálculo de escoramento de estruturas de concreto é um processo **manual, demorado e propenso a erros**.

| Etapa Manual | Tempo | Risco |
|---|---|---|
| Receber DXF do cliente | — | Arquivos complexos, layers desconhecidos |
| Identificar vigas, pilares, lajes | 1-2 horas | Vigas esquecidas, pilares mal posicionados |
| Calcular cargas (NBR 15696/6120) | 1-2 horas | Erros de majoração, sobrecarga errada |
| Distribuir escoras | 1-2 horas | Espaçamento irregular, escoras em cima de pilares |
| Selecionar equipamento (catálogo) | 30 min | Modelo incompatível com altura/carga |
| Montar BOM + orçamento | 30 min | Quantidades erradas, preço desatualizado |
| Gerar DXF de saída | 1-2 horas | Posições desenhadas manualmente |
| **Total por projeto** | **5-8 horas** | **Múltiplos pontos de falha humana** |

**Com Escora.AI:** O cliente faz upload do DXF e recebe tudo em **menos de 30 segundos**.

---

## O que a Ferramenta Faz (Passo a Passo)

### Visão Geral do Pipeline

```
   DXF do Cliente
        │
        ▼
┌──────────────────────────────────────────────────┐
│              ESCORA.AI — PIPELINE                │
│                                                  │
│  ① Leitura do DXF (20.000+ entidades CAD)       │
│  ② Filtro de Regiões (cortes, detalhes)          │
│  ③ Classificação da Obra (tipo + normas)         │
│  ④ Separação por Pavimento                       │
│  ⑤ Classificação de Elementos (IA + geometria)   │
│  ⑥ Extração de Metadados (pé-direito, espessura)│
│  ⑦ Cálculo Estrutural (NBR 15696 + 6120)        │
│  ⑧ Revisão Automática (shore_reviewer)           │
│  ⑨ Aprendizado (salva conhecimento)              │
│                                                  │
└──────────────────────────────────────────────────┘
        │
        ▼
   4 Outputs Automáticos
   ├── DXF com escoras posicionadas
   ├── PDF Relatório Técnico
   ├── PDF Memória de Cálculo (NBR)
   └── CSV Bill of Materials (BOM)
```

---

### Etapa ① — Leitura Inteligente do DXF

O sistema lê **todas as entidades** do arquivo CAD:

| Entidade CAD | O que o Escora.AI extrai |
|---|---|
| `LINE` | Segmentos H/V → candidatos a vigas |
| `LWPOLYLINE` | Decompõe em segmentos + detecta contornos |
| `SOLID` | Preenchimentos → candidatos a pilares |
| `TEXT` / `MTEXT` | Nomes de vigas ("V1"), seções ("14x40"), escalas |
| `CIRCLE` | Pilares circulares (quando > 5 círculos de mesmo raio) |
| `HATCH` | Contornos de laje, padrões de preenchimento |
| `DIMENSION` | Cotas → extração de medidas reais |
| `INSERT` (blocos) | Resolve referências + extrai atributos |

**Detecção automática de escala:** O sistema identifica se o DXF está em milímetros (1:50, 1:100) ou metros reais — sem configuração manual.

**Complexidade:** Um DXF típico tem **20.000-50.000 entidades**. O sistema processa todas em ~2 segundos.

---

### Etapa ② — Filtro de Regiões

Arquivos DXF de engenharia contêm muito mais que a planta:
- **Cortes** e **vistas** laterais
- **Detalhes** de armadura
- **Carimbos** e legendas
- **Tabelas** de aço

O sistema identifica e **remove automaticamente** essas regiões, mantendo apenas a planta estrutural.

---

### Etapa ③ — Classificação Automática da Obra

O sistema detecta **que tipo de obra** é o projeto, e seleciona as normas corretas:

| Tipo Detectado | Normas Aplicadas | Sobrecarga |
|---|---|---|
| Edifício Residencial | NBR 15696 + NBR 6120 + NBR 6118 | 1,5 kN/m² |
| Edifício Comercial | NBR 15696 + NBR 6120 | 2,0 kN/m² |
| Industrial / Galpão | NBR 15696 + NBR 8681 | 3,0 kN/m² |
| OAE (Pontes/Viadutos) | NBR 7187 + NBR 7188 | 5,0 kN/m² |

**Como detecta:** Analisa nomes de layers, textos ("PAVIMENTO", "TABULEIRO", "GALPÃO"), distribuição de entidades, e faixa de coordenadas.

**Detecta também o tipo de laje:**
- Maciça (sólida)
- Nervurada (cubetas)
- Treliçada / Pré-moldada
- Protendida
- Steel Deck

---

### Etapa ④ — Separação por Pavimento

Se o DXF contém múltiplos pavimentos, o sistema separa cada um e processa independentemente.

Detecta nomes de pavimento: "TÉRREO", "1º PAV", "COBERTURA", etc.

---

### Etapa ⑤ — Classificação de Elementos Estruturais (IA)

Esta é a **etapa mais complexa** — onde a inteligência artificial realmente atua.

#### 5a. Classificação de Layers

Para cada layer do DXF, o sistema roda dois detectores geométricos:

**Detector de Vigas** (`find_beam_candidates`):
- Procura **pares de linhas paralelas** (espaçamento 0,08-0,50m)
- Ratio comprimento/largura > 5:1
- Score geométrico 0,0-1,0

**Detector de Pilares** (`find_pillar_candidates`):
- Procura **retângulos** 0,10-1,0m × 0,10-1,0m
- Filtra nervuras (>60 retângulos uniformes = nervura, não pilares)
- Score geométrico 0,0-1,0

**Múltiplos layers aceitos:** O sistema aceita vigas em 2-3 layers simultaneamente (DXFs reais distribuem vigas por layers diferentes).

#### 5b. Classificação Textual

Para cada elemento detectado geometricamente, o sistema busca **textos próximos** (raio de 3m):

| Padrão de Texto | Classificação |
|---|---|
| "V1", "V10a", "V-PAV02" | Viga (BEAM) |
| "P1", "P70", "PILAR 5" | Pilar (PILLAR) |
| "LAJE_20CM", "e=15cm" | Laje (SLAB) |
| "14x40", "30x60" | Seção da viga (largura × altura) |

#### 5c. Fusão de Sinais (Confiança Final)

```
Confiança Final = f(Score Geométrico, Score Textual, Boost de Aprendizado)
```

- Geometria + texto concordam → confiança alta (>85%)
- Geometria forte, sem texto → confiança média (~70%)
- Texto contradiz geometria → penalização
- **Layer aprendido de runs anteriores → boost de +20%**

**Elementos com confiança < 50% são descartados** (evita falsos positivos).

#### 5d. Detecção de Pilares por Texto (Fallback)

Quando um pilar não tem preenchimento SOLID no DXF, mas tem texto "P1" com seção "30x19" próximo:
- O sistema cria um pilar "virtual" na posição do texto
- Procura o retângulo SOLID mais próximo para refinar a posição

---

### Etapa ⑥ — Extração de Metadados

O sistema busca automaticamente nos textos do DXF:

| Parâmetro | Padrão Textual | Exemplo |
|---|---|---|
| Pé-direito | "PD 3.00", "PE-DIREITO 2.80" | 2,80m |
| Espessura da laje | "LAJE_25CM", "e=12cm" | 0,12m |
| Escala | "ESC 1:50", "1:100" | Fator de conversão |

**Fallback aprendido:** Se o pé-direito não é encontrado neste DXF mas foi encontrado em DXFs anteriores, usa o valor mais comum do histórico.

---

### Etapa ⑦ — Cálculo Estrutural (NBR 15696 + 6120)

#### 7a. Montagem do Modelo Estrutural

1. **Associação viga-pilar:** Para cada viga, identifica quais pilares estão a menos de 1,0m do eixo
2. **Detecção de balanço:** Se a extremidade da viga não tem pilar → balanço (cantilever)
3. **Derivação de lajes (3 estratégias com merge):**
   - **Tier 1 — Malha de vigas:** Poligoniza o grid de vigas (Shapely polygonize) → cada polígono fechado = 1 painel de laje
   - **Tier 2 — Eixos estendidos:** Se Tier 1 produz poucos painéis, usa todos os candidatos a viga com tolerância de 2,0m para fechar gaps em pilares
   - **Tier 3 — Contornos do DXF:** Extrai polígonos diretamente de HATCH (preenchimentos CONCRETE, SOLID, ANSI31) e POLYLINE fechados em layers de laje (LAJE, FORMA, SLAB, PISO)
   - **Merge inteligente:** Combina resultados dos 3 tiers, eliminando duplicatas (sobreposição > 50% = duplicata)
4. **Detecção de shafts/vazios:** Identifica aberturas de elevadores, poços e furos por 3 métodos:
   - **Padrão X:** Detecta linhas diagonais cruzadas (marcação padrão CAD para aberturas)
   - **Texto:** Reconhece rótulos como "ELEVADOR", "POÇO", "FURO", "VAZIO"
   - **Layer:** Entidades em layers com palavras-chave de abertura (ABER, FURO, SHAFT)
   - Regiões de shaft são **excluídas** do cálculo de laje (não recebem escoras)
5. **Detecção de lajes em balanço:** Painéis fora do envelope de pilares → espaçamento reduzido

#### 7b. Cálculo de Cargas por Elemento

**Vigas:**
```
q_viga = b × h × γc                        (peso próprio)
       + e_laje × γc × faixa_influência    (carga da laje)
       + q_forma × faixa_influência         (peso das fôrmas)
       + q_sobrecarga × faixa_influência    (operários + equipamentos)

Q_total = q_viga × comprimento × γf (1,4)
```

**Lajes:**
```
q_laje = e × γc + q_forma + q_sobrecarga   (kN/m²)
Q_total = q_laje × área × γf (1,4)         (kN)
```

Onde:
- γc = 25,0 kN/m³ (concreto armado, NBR 6120)
- γf = 1,4 (coeficiente de majoração, NBR 15696)
- q_forma = 0,5 kN/m² (compensado + longarinas)
- q_sobrecarga = 1,5 kN/m² (residencial, NBR 15696)

#### 7c. Distribuição de Escoras (Multi-Span)

**Para vigas:**
1. Divide a viga em **vãos independentes** nos pontos de apoio (pilares)
2. Para cada vão, distribui escoras respeitando:
   - Espaçamento máximo: 1,00m (vigas)
   - Distância mínima do pilar: 0,70m da face
   - Espaçamento mínimo entre escoras: 0,30m
3. Em trechos em balanço: escora a 0,10m da extremidade livre

**Para lajes:**
1. Grid regular (X × Y) respeitando espaçamento por espessura:
   - 10-16cm: 1,30m | 17-24cm: 1,20m | 25-30cm: 1,10m | >30cm: 1,00m
2. Em balanço: espaçamento × 0,7 (30% mais denso)
3. Exclusão de zonas de pilares e eixos de vigas

#### 7d. Seleção de Equipamento (Catálogo)

Para cada escora posicionada:
1. Calcula altura necessária (pé-direito − altura da viga)
2. Calcula carga por escora (Q_total / n_escoras)
3. Seleciona do catálogo o modelo que atende:
   - Faixa de altura compatível
   - Capacidade de carga ≥ carga calculada
   - Menor custo entre os compatíveis

**Decisão automática: escora telescópica vs torre:**
- Altura > 4,5m → torre
- Carga > 30 kN/ponto → torre
- Laje nervurada espessa → torre
- Senão → escora telescópica

#### 7e. Recomendação de Contra-Flecha

| Vão da Viga | Contra-Flecha Recomendada |
|---|---|
| 2,0-3,0m | 0,5 cm |
| 3,0-4,0m | 1,0 cm |
| 4,0-5,0m | 1,5 cm |
| 5,0-6,0m | 2,0 cm |
| > 6,0m | Consultar projetista |

---

### Etapa ⑧ — Revisão Automática (Quality Assurance)

Após o cálculo, um módulo de revisão verifica **todo o projeto**:

| Verificação | Ação |
|---|---|
| Escora sobre pilar | Remove (redundante) |
| Escora de laje sobre eixo de viga | Remove (viga já tem suas escoras) |
| Duas escoras < 0,50m uma da outra | Remove a mais fraca |
| Escora fora do perímetro da laje | Remove |
| Espaçamento excede máximo normativo | Alerta + recalcula |
| Carga > capacidade do equipamento | Alerta + sugere modelo maior |

**Recálculo automático:** Após remover escoras, recalcula a carga por escora para manter a precisão.

---

### Etapa ⑨ — Aprendizado (Machine Learning)

**A cada projeto processado, o sistema fica mais inteligente.**

#### O que o sistema aprende:

| Conhecimento | Exemplo | Impacto |
|---|---|---|
| Quais layers têm vigas | Layer "11" = vigas (95% confiança) | Próximo DXF: classifica layer "11" instantaneamente |
| Quais layers têm pilares | Layer "22" = pilares (100% confiança) | Reduz falsos positivos |
| Seções mais comuns | 19×25cm (302 ocorrências) | Fallback quando seção não encontrada |
| Espessura de laje típica | 12cm (mais comum) | Default mais preciso |
| Pé-direito mais comum | 2,80m | Fallback quando não detectado |

#### Sistema de Aprendizado v2:

- **Deduplicação por arquivo:** Cada arquivo conta uma vez (não importa quantas vezes foi processado)
- **Decay temporal:** Runs recentes têm mais peso que runs antigos
- **Quality gates:** Layers com < 3 vigas ou < 2% taxa de detecção são descartados
- **Cap de 200 records:** Previne crescimento descontrolado

#### Modelo de ML Preditivo (Opcional):

Quando treinado com dados suficientes, um modelo sklearn pode:
- **Prever tipo de suporte** (telescópica vs torre) — classificador
- **Recomendar espaçamento** — regressão
- **Sugerir equipamento** (VM130 vs VM80) — classificador

Features: comprimento da viga, ângulo, distância ao pilar mais próximo, quantidade de vigas vizinhas, posição no pavimento (perímetro vs interior).

---

## Outputs Gerados

### 1. DXF com Escoras Posicionadas

O DXF de saída **preserva todo o desenho original** e adiciona layers organizados:

| Layer | Cor | Conteúdo |
|---|---|---|
| `ESCORAS_VIGAS` | Magenta | Posição de cada escora de viga (círculos) |
| `ESCORAS_LAJES` | Verde | Posição de cada escora de laje (quadrados) |
| `PILARES` | Vermelho | Contorno dos pilares detectados |
| `VIGAS` | Azul | Eixo das vigas detectadas |
| `LAJES` | Branco | Perímetro dos painéis de laje |
| `TEXTO` | Cinza | Nomes dos elementos |
| `INFO` | Ciano | Quantidade de escoras por painel |

**O engenheiro abre no AutoCAD e vê as escoras posicionadas sobre o projeto original.**

### 2. PDF — Relatório Técnico

- Resumo geral (total de escoras, carga total, status)
- Tabela de vigas (nome, seção, comprimento, escoras, espaçamento, modelo)
- Tabela de lajes (painel, área, espessura, grid, espaçamento)
- Lista de equipamentos (BOM)
- Avisos e alertas

### 3. PDF — Memória de Cálculo

- Referências normativas (NBR 15696, NBR 6120, NBR 6118)
- Dados de entrada com rastreabilidade (DXF / padrão / aprendido)
- Fórmulas de cálculo por elemento
- Verificação de espaçamento por eixo
- Status por elemento: **CONFORME** / **NÃO CONFORME**

### 4. CSV — Bill of Materials

Tabela exportável com:
- Tipo, nome do elemento, comprimento/área, seção
- Quantidade de escoras, espaçamento
- Modelo do equipamento, capacidade

---

## Por Que Não Desenvolver Internamente?

### Complexidade Real do Software

| Componente | Linhas de Código | Meses de Dev |
|---|---|---|
| Parser de DXF (20+ tipos de entidade) | ~2.000 | 2-3 meses |
| Classificação geométrica (vigas + pilares) | ~1.500 | 2-3 meses |
| Classificação textual (NLP para nomes de elementos) | ~800 | 1 mês |
| Classificação de layers (multi-layer + nervura filter) | ~600 | 1 mês |
| Motor de cálculo (NBR 15696 + 6120 + 6118) | ~2.500 | 3-4 meses |
| Distribuição de escoras (multi-span + cantilever) | ~1.200 | 2 meses |
| Seleção de equipamento (catálogo + torre vs escora) | ~800 | 1 mês |
| Derivação de lajes (polygonize + snap) | ~600 | 1-2 meses |
| Revisão automática (shore_reviewer) | ~400 | 1 mês |
| Geração de DXF de saída | ~800 | 1-2 meses |
| Geração de PDF (3 relatórios) | ~1.500 | 2 meses |
| Sistema de aprendizado (ML + learning store) | ~800 | 1-2 meses |
| API web (upload + processamento assíncrono) | ~600 | 1 mês |
| Testes automatizados | ~3.000 | Contínuo |
| **Total** | **~16.000+** | **18-24 meses** |

**Custo estimado de desenvolvimento interno:**
- 1 engenheiro de software sênior: R$ 15-25k/mês
- 1 engenheiro civil consultor: R$ 8-12k/mês
- 18-24 meses de desenvolvimento
- **Total: R$ 400k-800k** (sem contar manutenção)

### Desafios Não Óbvios

1. **Cada escritório de engenharia usa DXF diferente** — layers com nomes numéricos ("11", "22") vs nomes descritivos ("FORMA", "PILAR_SOLID"). O sistema precisa lidar com TODOS.

2. **Vigas não são linhas simples** — são pares de linhas paralelas, espaçadas pela largura da viga, que param na face do pilar (não no centro). O gap entre viga e pilar precisa ser "costurado" geometricamente.

3. **Pilares aparecem como SOLID fills** — não como retângulos explícitos. O parser precisa reconstruir geometria a partir de preenchimentos triangulares.

4. **Lajes precisam de detecção multi-estratégia** — não existe entidade "LAJE" no DXF. O sistema usa 3 estratégias simultâneas: (1) polygonize da malha de vigas, (2) extensão de eixos com tolerância de 2m, (3) extração direta de contornos a partir de HATCH e POLYLINE fechados em layers de laje. Se uma falha, as outras cobrem.

5. **Textos "V1 (14x40)" podem estar a 3 metros da viga** — o sistema precisa associar texto a elemento por proximidade ao eixo inteiro, não apenas ao ponto mais próximo.

6. **Nervuras de laje parecem pilares** — 200+ retângulos uniformes que o detector de pilares vê como pilares. Precisam ser filtrados por análise de padrão.

7. **NBR 15696 não dá espaçamento exato** — o engenheiro usa tabelas práticas (Manual Lajes Martins), experiência, e catálogo do fabricante. Automatizar isso exige anos de calibração.

---

## Evolução Futura

### Curto Prazo (3-6 meses)

| Feature | Valor |
|---|---|
| **Catálogo integrado da locadora** | BOM com preços reais, estoque disponível |
| **Feedback loop com engenheiro** | Upload da revisão → sistema aprende correções |
| **Dashboard de métricas** | Precisão por arquivo, tendências de melhoria |
| **API para integração** | ERP da locadora consulta diretamente |

### Médio Prazo (6-12 meses)

| Feature | Valor |
|---|---|
| **Otimização de estoque** | Dado o estoque atual, redistribui equipamentos |
| **Cálculo de re-escoramento** | NBR 14931 — cronograma de retirada parcial |
| **Suporte a DWG nativo** | Sem necessidade de converter para DXF |
| **Detecção de armadura** | Extrai bitolas e posições do DXF de armação |

### Longo Prazo (12-24 meses)

| Feature | Valor |
|---|---|
| **Cálculo estrutural completo** | Verificação de punção, flexão, cisalhamento |
| **Desenho técnico automatizado** | Gera planta de escoramento executiva |
| **Integração BIM (IFC)** | Importa modelos 3D do Revit/TQS |
| **Orçamento automatizado** | Preço final com frete, montagem, locação |
| **App mobile** | Engenheiro de obra escaneia planta → recebe escoramento |

### Visão de Longo Prazo

```
DXF/DWG/IFC → Escora.AI → Projeto Executivo Completo
                             ├── Planta de escoramento
                             ├── Planta de fôrmas
                             ├── Lista de materiais
                             ├── Orçamento com preços
                             ├── Cronograma de montagem/desmontagem
                             └── Relatório normativo assinável
```

---

## Métricas Atuais

| Métrica | Valor |
|---|---|
| Arquivos DXF processados | 34 únicos |
| Vigas detectadas (acumulado) | 5.633 |
| Pilares detectados (acumulado) | 5.020 |
| Escoras calculadas (acumulado) | 66.137 |
| Score médio de confiança (vigas) | 85% |
| Testes automatizados | 190 (100% passando) |
| Tempo de processamento | < 30 segundos por DXF |
| Seção mais comum aprendida | 19×25cm |
| Espessura de laje mais comum | 12cm |

---

## Resumo

**Escora.AI não é um script simples — é um sistema de engenharia completo:**

1. **Interpreta** qualquer DXF de forma estrutural automaticamente
2. **Classifica** obra, elementos e layers sem configuração manual
3. **Calcula** cargas conforme NBR 15696, 6120 e 6118
4. **Distribui** escoras com inteligência multi-span e detecção de balanço
5. **Seleciona** equipamento do catálogo por compatibilidade técnica
6. **Revisa** posicionamento automaticamente (quality assurance)
7. **Aprende** com cada projeto processado (machine learning)
8. **Gera** DXF + 3 PDFs + BOM em 30 segundos

**Cada projeto processado torna o sistema mais inteligente.**

**O custo de desenvolver algo equivalente internamente seria R$ 400-800k e 18-24 meses.
A parceria com o Escora.AI dá acesso imediato a toda essa tecnologia.**
