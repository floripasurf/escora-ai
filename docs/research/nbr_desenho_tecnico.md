# NBR 10126 + NBR 6492 + NBR 8403 — Referência para Leitura de DXF

Compilação das normas ABNT relevantes para interpretação de desenhos estruturais em DXF.

---

## NBR 10126:1987 — Cotagem em Desenho Técnico

### 1. Objetivo
Fixa os princípios gerais de cotagem a serem aplicados em todos os desenhos técnicos.

### 2. Definições

| Termo | Definição |
|-------|-----------|
| **Cota** | Representação gráfica no desenho da característica do elemento, por meio de linhas, símbolos, notas e valor numérico numa unidade de medida |
| **Cota Funcional (F)** | Essencial para a função da peça/elemento |
| **Cota Não Funcional (NF)** | Necessária para fabricação mas não para função |
| **Cota Auxiliar (A)** | Informativa, entre parênteses, não governa fabricação |
| **Linha de cota** | Linha contínua estreita, paralela à dimensão cotada, delimitada por setas ou traços oblíquos |
| **Linha auxiliar (de chamada)** | Linha contínua estreita, perpendicular ao elemento dimensionado, que parte do elemento até além da linha de cota |
| **Limite da linha de cota** | Seta ou traço oblíquo (45°) nas extremidades da linha de cota |

### 3. Elementos Gráficos da Cota

Uma cota completa é formada por:
1. **Linha de cota** — contínua estreita (0.25mm)
2. **Linha auxiliar (de chamada)** — contínua estreita, perpendicular ao elemento
3. **Limite da linha de cota** — seta fechada ou traço oblíquo a 45°
4. **Valor numérico** — dimensão em unidade do desenho

### 4. Regras Fundamentais

#### 4.1 Posicionamento
- Cotas devem ficar **preferencialmente fora** do contorno do desenho
- Linha auxiliar deve partir a **2-3mm** do contorno do objeto
- Linha auxiliar deve se prolongar **ligeiramente além** da linha de cota (~2mm)
- **Não cruzar** linhas de cota com outras linhas de cota
- Se cruzamento for inevitável, as linhas **NÃO** devem ser interrompidas

#### 4.2 Valor Numérico
- Posicionado **acima e paralelamente** à linha de cota
- **Preferencialmente no centro** da linha de cota
- Nunca deve ser cortado por qualquer linha do desenho
- Se espaço insuficiente: valor numérico posicionado externamente com linha de chamada

#### 4.3 Orientação do Texto
- Cotas horizontais: texto lido da **esquerda para direita**
- Cotas verticais: texto lido de **baixo para cima** (lado esquerdo)
- Cotas inclinadas: seguem a inclinação da linha de cota

#### 4.4 Espaçamento entre Linhas de Cota
- Mínimo **7mm** entre linha de cota e contorno do objeto
- Mínimo **7mm** entre linhas de cota paralelas
- Em desenhos arquitetônicos: geralmente **10mm** entre linhas

### 5. Métodos de Cotagem

#### 5.1 Cotagem em Série (Cadeia)
- Cotas alinhadas sequencialmente ao longo do elemento
- Cada cota toca a próxima
- **Cuidado:** erros acumulam

#### 5.2 Cotagem Paralela (Baseline)
- Todas as cotas partem de uma mesma referência (linha base)
- Linhas de cota paralelas, espaçadas igualmente
- Evita acúmulo de erros

#### 5.3 Cotagem Combinada
- Mistura de série e paralela conforme necessidade

#### 5.4 Cotagem por Coordenadas (Aditiva)
- Uma única linha com origem marcada (0)
- Valores se somam a partir da origem
- Comum em desenhos CNC e estruturais

### 6. Cotas Especiais

| Tipo | Símbolo | Exemplo |
|------|---------|---------|
| Diâmetro | Ø | Ø20 |
| Raio | R | R10 |
| Quadrado | □ | □15 |
| Esfera | SØ ou SR | SØ20 |
| Chanfro | C ou 45° | C2 ou 2x45° |

### 7. Unidades
- Sistema métrico (milímetros para mecânica, metros para arquitetura/estrutural)
- **Em um único desenho, usar a mesma unidade**
- Se unidade diferente: indicar junto ao valor (ex: "2.80m")

### 8. Escala e Cotagem
- Valores numéricos representam **sempre a dimensão REAL** do objeto
- A escala do desenho **NÃO** altera os valores de cota
- Ex: viga de 5.00m cotada como "5.00" mesmo em escala 1:50

---

## NBR 6492:2021 — Representação de Projetos de Arquitetura

### 1. Objetivo
Estabelece requisitos para documentação técnica de projetos arquitetônicos e urbanísticos.

### 2. Tipos de Linhas (Tabela A.1)

| Tipo | Espessura | Aparência | Aplicação |
|------|-----------|-----------|-----------|
| **Contínua extralarga** | 1.0-1.4mm | ———————— | Contorno de terreno natural, limites de área |
| **Contínua larga** | 0.5-0.7mm | ———————— | **Contornos visíveis de elementos em corte/seção** (paredes, vigas, pilares cortados). Arestas visíveis principais |
| **Contínua estreita** | 0.25-0.35mm | ———————— | Linhas de cota, linhas auxiliares, hachuras, contornos de elementos em vista (não cortados), detalhes secundários |
| **Tracejada larga** | 0.5-0.7mm | — — — — | Contornos não visíveis de elementos estruturais importantes |
| **Tracejada estreita** | 0.25-0.35mm | — — — — | **Arestas e contornos não visíveis** (elementos abaixo do plano de corte, fundações em planta de piso, vigas acima em planta) |
| **Traço-ponto estreita** | 0.25-0.35mm | —·—·—·— | **Eixos de simetria**, eixos de elementos estruturais, centro de pilares, linhas de centro |
| **Traço-ponto larga** | 0.5-0.7mm | —·—·—·— | Indicação de cortes e seções, linhas de projeção |
| **Traço-dois-pontos estreita** | 0.25-0.35mm | —··—··— | Projeções de pavimentos em balanço, beirais, marquises, contornos de elementos adjacentes |
| **Contínua à mão livre** | 0.25mm | ~~~~~~~ | Linhas de ruptura (interrupção de desenho), limites de vistas parciais |

### 3. Proporção de Espessuras

Em cada grupo de linhas, as larguras seguem a proporção:
- **Extralarga : Larga : Estreita = 1 : ½ : ¼**

Exemplo prático:
- Extralarga: 1.0mm
- Larga: 0.50mm
- Estreita: 0.25mm

### 4. Representação de Elementos Estruturais

#### 4.1 Pilares (Colunas)
- **Em planta**: retângulo com **contínua larga** (cortado pelo plano)
- Preenchimento com hachura em concreto (pontos/granulado) ou sólido
- **Eixos** marcados com **traço-ponto estreita**
- Nomenclatura: P1, P2, P3... ou PA, PB, PC...

#### 4.2 Vigas
- **Em planta (acima do corte)**: **tracejada estreita** (elemento não visível, acima do plano)
- **Em corte**: **contínua larga** (elemento cortado)
- **Em vista**: **contínua estreita**
- Nomenclatura: V1, V2, V3... ou VA, VB, VC...

#### 4.3 Lajes
- **Em planta**: representadas pela hachura ou identificação alfanumérica
- Contorno definido pelas vigas que a delimitam
- Nomenclatura: L1, L2, L3... ou LA, LB, LC...
- Espessura indicada junto ao nome: "L1 (h=12)"

#### 4.4 Fundações
- **Em planta**: **tracejada estreita** (abaixo do plano de corte)
- Sapatas e blocos representados em linhas tracejadas

### 5. Hachuras e Preenchimentos

| Material | Padrão de Hachura |
|----------|-------------------|
| Concreto armado | Granulado (pontos) ou hachura com linhas cruzadas a 45° |
| Alvenaria | Linhas diagonais simples a 45° |
| Terra/Solo | Pontos irregulares |
| Aço/Metal | Hachura densa a 45° |
| Madeira | Veios (linhas curvas paralelas) |
| Isolamento | Ondulado |
| Vidro | Linha fina na borda |

### 6. Escalas para Projetos

| Tipo de Desenho | Escala |
|-----------------|--------|
| Planta de situação | 1:500 ou 1:1000 |
| Planta de locação | 1:200 ou 1:500 |
| **Planta baixa** | **1:50** ou 1:100 |
| **Cortes e elevações** | **1:50** ou 1:100 |
| Fachadas | 1:50 ou 1:100 |
| **Detalhes construtivos** | **1:20** ou 1:25 |
| **Detalhes estruturais** | **1:10**, 1:20 ou 1:25 |
| Planta de cobertura | 1:100 ou 1:200 |
| Planta de fôrma | **1:50** |

### 7. Cotas (conforme NBR 6492)
- Sistema métrico de medidas
- **Em um único desenho, usar mesma unidade**
- Cotas compostas por: linha de cota, linha de chamada, limites, cifra
- Cifras com **2.5mm** ou **1.8mm** de altura
- Cotas preferencialmente fora do desenho
- Linhas de chamada a 2-3mm do objeto
- Não duplicar dimensões

### 8. Escrita
- Fonte sem serifas, espessura uniforme
- Preferencialmente em CAIXA ALTA
- Sem itálico (exceto palavras estrangeiras)
- Altura uniforme dentro do mesmo grupo (cotas, nomes, chamadas)

---

## NBR 8403:1984 — Aplicação de Linhas em Desenhos

### 1. Tabela Completa de Tipos de Linhas

| Linha | Tipo | Espessura | Aplicação Geral |
|-------|------|-----------|-----------------|
| A | Contínua larga | 0.5-0.7mm | **Contornos visíveis, arestas visíveis** |
| B | Contínua estreita | 0.25mm | Linhas de cota, hachuras, contornos de seções rebatidas, linhas de chamada |
| C | Contínua estreita à mão livre | 0.25mm | Limites de vistas ou cortes parciais |
| D | Contínua estreita em zigue-zague | 0.25mm | Limites de vistas ou cortes parciais (alternativa a C) |
| E | Tracejada larga | 0.5mm | **Contornos não visíveis**, arestas não visíveis |
| F | Tracejada estreita | 0.25mm | Contornos não visíveis, arestas não visíveis |
| G | Traço-ponto estreita | 0.25mm | **Eixos de simetria**, linhas de centro, trajetórias |
| H | Traço-ponto estreita, larga nas extremidades | — | Planos de corte |
| J | Traço-ponto larga | 0.5mm | Indicação de tratamento superficial, superfícies com requisitos especiais |
| K | Traço-dois-pontos estreita | 0.25mm | **Contornos de peças adjacentes**, posições extremas de peças móveis, linhas de centro de gravidade |

### 2. Prioridade de Linhas Coincidentes
Quando duas ou mais linhas coincidem na mesma posição:
1. **Contornos e arestas visíveis** (Tipo A) — prioridade máxima
2. **Contornos e arestas não visíveis** (Tipo E/F)
3. **Planos de corte** (Tipo H)
4. **Eixos e linhas de centro** (Tipo G)
5. **Linhas de centro de gravidade** (Tipo K)
6. **Linhas de cota** (Tipo B) — prioridade mínima

### 3. Grupos de Espessura

| Grupo | Larga | Estreita |
|-------|-------|----------|
| 1 | 0.50mm | 0.25mm |
| 2 | 0.70mm | 0.35mm |
| 3 | 1.00mm | 0.50mm |
| 4 | 1.40mm | 0.70mm |

---

## Aplicação para Parser DXF (Escora.AI)

### Mapeamento Tipo de Linha DXF → Significado Estrutural

| Propriedade DXF | Valor | Significado Provável |
|-----------------|-------|----------------------|
| `lineweight` | ≥50 (0.50mm+) | **Contorno de elemento cortado** (pilar, viga em seção) |
| `lineweight` | 25-35 (0.25-0.35mm) | Linhas de cota, hachura, elementos em vista |
| `linetype` | `CONTINUOUS` | Contornos visíveis ou linhas de cota |
| `linetype` | `DASHED` / `HIDDEN` | **Elementos não visíveis** (vigas acima, fundações abaixo) |
| `linetype` | `CENTER` / `DASHDOT` | **Eixos estruturais**, centros de pilares |
| `linetype` | `PHANTOM` | Elementos adjacentes, projeções |
| `color` | 1 (vermelho) | Frequentemente usado para cotas |
| `color` | 7 (branco/preto) | Contornos principais |
| `layer` contendo "COTA"/"DIM" | — | Layer de cotagem |
| `layer` contendo "EIXO"/"AXIS" | — | Layer de eixos estruturais |
| `layer` contendo "HACH" | — | Layer de hachuras |

### Regras para Filtragem de Ruído no Parser

1. **Linhas de cota** (estreitas, layer COTA/DIM) → **EXCLUIR** da detecção de vigas/pilares
2. **Eixos** (traço-ponto, layer EIXO) → **EXCLUIR** da detecção geométrica, mas USAR para identificar grid estrutural
3. **Hachuras** (estreitas, layer HACH) → **EXCLUIR** da detecção geométrica, mas USAR para identificar tipo de material
4. **Contornos largos** (≥0.50mm, CONTINUOUS) → **PRIORIZAR** como contornos de elementos estruturais
5. **Tracejadas** → Podem indicar vigas acima do plano de corte (importante para formas de cobertura)
6. **Traço-dois-pontos** → Projeções de balanço (lajes em balanço / marquises)

### Interpretação de Cotas para Seções de Vigas

Padrões de texto de cota associados a vigas:
- `bxh` ou `b/h` → seção da viga (largura x altura em cm)
- Exemplos: "14x50", "20/60", "14×40"
- O valor numérico da cota é **sempre a dimensão REAL**, independente da escala
- Em desenhos de forma: cotas geralmente em **centímetros**
- Em plantas: cotas geralmente em **metros**

### Detecção de Elementos por Características de Linha

```
PILAR em planta:
  → Retângulo fechado
  → Linhas contínuas largas (cortado pelo plano)
  → Possível hachura interna (concreto)
  → Eixo traço-ponto no centro
  → Nomenclatura "P1", "P2" próxima

VIGA em planta de forma:
  → Par de linhas paralelas
  → Linhas contínuas (largas se cortadas, estreitas se em vista)
  → Nomenclatura "V1", "V2" próxima
  → Cota de seção "bxh" associada
  → Tracejada se acima do plano de corte

LAJE:
  → Área delimitada por vigas
  → Possível hachura interna
  → Nomenclatura "L1", "L2" no centro
  → Indicação de espessura "h=12"
  → Setas de armadura (direção principal)
```
