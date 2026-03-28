# Análise DXF Infraestrutura (OAE - Obras de Arte Especiais)

**Arquivos:** DE-BAQ-TR06-EST-OAE (ponte/viaduto - Bahia)

## Diferenças Fundamentais vs Edifícios

| Aspecto | Edifícios (TQS) | Infraestrutura (OAE) |
|---------|-----------------|---------------------|
| Layers | Numéricos (1, 2, 22, 27) | Prefixo `FOR-`, `ARM-`, `DIM-` |
| Elementos | Vigas V1, Pilares P1, Lajes L1 | Encontros E1/E2, Longarinas, Tabuleiro |
| HATCHes | 0 (nenhum) | 23-142 por arquivo |
| DIMENSIONs | 0 (nenhum) | 4-177 por arquivo |
| INSERTs | 0 (nenhum) | 14-423 por arquivo |
| Escala | Texto "ESC 1:50" | Texto "Esc.1:25" e "Esc.1:50" |
| Coordenadas | Cartesianas simples | Estaqueamento (EST. 110+14,37) |

## Layers de Infraestrutura

### Layers de Forma (FOR-)
- `FOR-VIG` — Vigas/longarinas
- `FOR-251/252/253/254` — Contornos de forma por espessura
- `FOR-L01 a L08` — Linhas de forma por nível
- `FOR-SSC/SSH/SSL/SSS/SST/SSX` — Seções e cortes
- `FOR-NVL/NVT` — Níveis longitudinal/transversal
- `FOR-EIX` — Eixos
- `FOR-ZIG` — Zigzag (nervuras/dentes)
- `FOR-HAT` — Hachuras de forma
- `FOR-080/100/140` — Textos por tamanho
- `FOR-BLD/BLE/BLH/BLL/BLN/BLO/BLT/BLZ` — Blocos de forma

### Layers de Armadura (ARM-)
- `ARM-FER` — Ferragem
- `ARM-PNG` — Posições (348 INSERTs no OAE-12!)
- `ARM-POS` — Posições de aço
- `ARM-COT` — Cotas de armadura

### Layers de Dimensão (DIM-)
- `DIM-FOR` — Cotas de forma
- `DIM-ARM` — Cotas de armadura
- `DIM-LIN/TEX/TIC` — Linhas/textos/ticks de cota

## Elementos Estruturais Encontrados

### Encontros (E1, E2)
- "ENCONTRO E1 - FORMAS", "ENCONTRO E2 - FORMAS"
- "SEÇÃO TRANSVERSAL NO ENCONTRO E1/E2"
- Pilares de encontro: P1.1, P1.2, P2.1, P2.2

### Tabuleiro
- "CORTE A - A (SEÇÃO TRANSVERSAL NO TABULEIRO)"
- Seção transversal com guarda-rodas (GR.1, GR.2)

### Outros
- "LAJE DE APROXIMAÇÃO"
- "MURO DE CONTENÇÃO"
- "APARELHO DE APOIO"
- "JUNTA DE [DILATAÇÃO]"
- "DEFENSA METÁLICA"
- "LASTRO DE CONCRETO MAGRO = 5cm"
- Estaqueamento: "EST. 10+14,353", "EST. 11+11,450"
- Medidas em mm (não metros como edifícios)

## Blocos (INSERT) Significativos

| Bloco | Qtd | Descrição |
|-------|-----|-----------|
| BLK-PNG | 348x | Posição de armadura (barra) |
| BLK-POS | 36x | Etiqueta de posição |
| blk-sae | 28x | Seta de armadura |
| Gr-Conc-Dim | 4x | Dimensão de concreto (Gracad) |
| A$C* | Variável | Blocos anônimos do AutoCAD |

## Impacto no Parser

### O que precisa mudar para suportar OAE:

1. **Novo classificador de elementos OAE:**
   - Encontros (E1, E2) → como pilares grandes
   - Tabuleiro → como laje contínua
   - Longarinas → como vigas longas
   - Transversinas → como vigas curtas perpendiculares

2. **Suporte a layers FOR-:**
   - Mapear `FOR-251` → contorno de forma (como layer 1/2 dos edifícios)
   - Mapear `FOR-VIG` → vigas
   - Mapear `FOR-NVL/NVT` → níveis

3. **Leitura de HATCH:**
   - 142 hatches no OAE-05 → áreas de concreto, seções
   - Extrair polígonos de boundary para detectar áreas

4. **Leitura de DIMENSION:**
   - 177 dimensões no OAE-05 → medidas reais dos elementos
   - Usar para validar escala e dimensões de seção

5. **Resolução de INSERT/blocks:**
   - 423 blocos no OAE-12 → principalmente armaduras
   - `virtual_entities()` para extrair geometria

6. **Sistema de coordenadas:**
   - Estaqueamento (KM+m) → converter para coordenadas lineares
   - Unidade em mm → detecção automática de unidade

7. **Multi-escala:**
   - Mesmo arquivo tem 1:25 e 1:50
   - Precisamos separar regiões (planta vs corte vs detalhe)
