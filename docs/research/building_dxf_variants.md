# Análise de Variantes DXF de Edifícios

## Resumo dos Arquivos Analisados

| Arquivo | Software | Layers | Entities | HATCHes | DIMENSIONs | INSERTs |
|---------|----------|--------|----------|---------|------------|---------|
| CFL-SUB (subsolo) | TQS | 88 (numéricos) | 24.698 | 0 | 0 | 0 |
| RMM-1P | TQS | 88 (numéricos) | 3.195 | 0 | 0 | 0 |
| RUH-1P | TQS | 88 (numéricos) | 15.865 | 0 | 0 | 0 |
| E E-1O (1º pav.) | TQS | 88 (numéricos) | 4.893 | 0 | 0 | 0 |
| ALG-1OP (Cesar) | TQS | 88 (numéricos) | 26.094 | 0 | 0 | 0 |
| CVS-COB (ref.) | TQS | 88 (numéricos) | ~5.000 | 0 | 0 | 0 |

**Todos os edifícios usam TQS** com layers numéricos e zero HATCHes/DIMENSIONs/INSERTs.

## Padrão TQS de Layers

| Layer | Conteúdo | Entidades |
|-------|----------|-----------|
| **1** | Contorno de forma principal (vigas, lajes) | LINE, POLYLINE, CIRCLE, ARC |
| **2** | Contornos complementares, detalhes | LINE, TEXT, SOLID, POLYLINE |
| **3** | Linhas auxiliares, pilares desenhados | LINE, CIRCLE, POLYLINE |
| **4** | Armaduras, detalhes | LINE, POLYLINE, ARC, CIRCLE |
| **7** | Polylines (contornos de laje nervurada?) | POLYLINE |
| **11** | Textos de dimensão, cotas em polyline | POLYLINE, TEXT |
| **12/13** | Linhas auxiliares | POLYLINE, LINE |
| **21/22/23/24** | SOLIDs (pilares preenchidos) | SOLID |
| **27** | Textos de anotação (nomes, dims) | LINE, TEXT, POLYLINE |
| **34** | SOLIDs auxiliares | SOLID, LINE |
| **42** | Linhas de eixo | LINE |
| **123** | Textos de cota/dimensão | TEXT |
| **124** | Textos complementares | LINE, TEXT, CIRCLE |

## Labels Estruturais Encontrados

### Vigas
- Padrão TQS: `V1a`, `V2a`, `V10a`, `V101a` (sufixo 'a' = TQS)
- ALG (Cesar): `V1`, `V2`, `V3` (sem sufixo)

### Pilares
- Padrão: `P1`, `P10`, `P100`
- Cesar: `p70`, `p80`, `p160` (minúsculo!)

### Lajes
- Padrão: `L1`, `L2`, `L10`, `L101`
- Nervurada detectada em texto: "AS LAJES NERVURADAS SÃO MOLDADAS" (RUH-1P)
- Treliçada detectada: "DETALHE DA LAJE TRELIÇADA" (E E-1O)

## Descobertas Importantes

### 1. Lajes Nervuradas (RUH-1P)
Texto encontrado: *"AS LAJES NERVURADAS SÃO MOLDADAS"*
- Este arquivo tem lajes nervuradas mas o padrão de layers é idêntico
- Layer 7 no ALG tem 847 POLYLINEs → possivelmente contornos de nervuras
- Detecção precisa ser por padrão geométrico (linhas paralelas uniformes dentro do painel de laje)

### 2. Lajes Treliçadas (E E-1O)
Texto encontrado: *"DETALHE DA LAJE TRELIÇADA"*
- Laje pré-moldada com treliça → diferente de nervurada moldada in-loco
- Escoramento mais simples (apoio linear, sem cubetas)

### 3. Reescoras
Múltiplos arquivos mencionam:
- *"UTILIZAR REESCORAS FIXAS EM FUNDOS DE VIGAS"*
- *"FAIXA DE REESCORA EM LAJES"*
- *"LAJE COM 100% DA CAPACIDADE"*
- Reescoras são um conceito importante que o script ainda não implementa

### 4. Layer 7 = Nervuras?
No ALG-1OP (Cesar), layer 7 tem **847 POLYLINEs** e zero texto. Nos outros arquivos, layer 7 não tem entidades. Isso sugere que layer 7 é usado pelo TQS para desenhar nervuras quando existem lajes nervuradas.

### 5. Pilares em minúsculo
O Cesar usa `p70`, `p80` — o parser precisa ser case-insensitive na detecção de pilares.

## Lacunas do Parser Atual

| Gap | Impacto | Arquivos Afetados |
|-----|---------|-------------------|
| Não detecta laje nervurada | Escoramento incorreto | RUH-1P, possivelmente ALG |
| Não detecta laje treliçada | Tipo de apoio errado | E E-1O |
| Case-sensitive em labels | Perde pilares minúsculos | ALG (Cesar) |
| Polylines multi-segmento não decompostas | Perde vigas curvas/complexas | ALG (847 polylines) |
| Não entende reescoras | Não planeja reescoramento | Todos |
| Não filtra detalhe vs planta | Mistura escalas | Todos (vigas de detalhe) |

## Recomendações de Prioridade

1. **Case-insensitive** na detecção de labels (P1 = p1)
2. **Decomposição de polylines** multi-segmento em segmentos H/V
3. **Detecção de laje nervurada** por padrão geométrico (layer 7) + texto
4. **Detecção de laje treliçada** por texto
5. **Filtragem de regiões** (planta principal vs detalhes/cortes)
6. **Conceito de reescoramento** no cálculo
