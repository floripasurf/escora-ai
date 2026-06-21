# Escora.AI — Engineering Context

> **For Claude Code and other coding agents working on this repository.**
> This file encodes the engineering rules, norm references, and validated calibrations that govern the Escora.AI shoring layout system. Read this before doing anything else. Read it again at the start of every session.
>
> **Document version:** 2026-05-04 (v3) — comprehensive update after visual inspection of all 123 pages of Orguel training PDF.
> **Companion:** `PDF_FINDINGS.md` — page-by-page rule extraction catalog with citations.

---

## Product

Automated shoring (escoramento) design system for Brazilian civil construction.

- **Input:** structural plan DXF (TQS, AutoCAD, Eberick).
- **Output:** shoring layout DXF with Orguel symbology, BOM CSV, Memória de Cálculo PDF, IFC for BIM integration.
- **Equipment partner:** Grupo Orguel.
- **Calibration baseline:** 12 executive Orguel projects, calibrated 2026-04-07.
- **Legal framing:** the system produces an **auditable draft**, sent to the engineer as a **suggestion** (per Orguel training p.60). Final responsibility stays with the obra's engineer or estrutural calculista. Every output PDF must include the unfilled ART block at the end.

---

## Domain Authority (priority order)

When sources conflict, higher-priority sources win. NBR norms are the legal foundation; Orguel materials provide operational specifics; engineer Q&A reflects calibrated practice.

1. **ABNT NBR 15696:2009** — Fôrmas e escoramentos para estruturas de concreto.
2. **ABNT NBR 6118:2023** — Projeto de estruturas de concreto.
3. **ABNT NBR 6120:2019** — Cargas para o cálculo de estruturas.
4. **ABNT NBR 14931** — Execução de estruturas de concreto.
5. **ABNT NBR 6123** — Forças devidas ao vento.
6. **ABNT NBR 7190** — Projeto de estruturas de madeira.
7. **ABNT NBR 8800** — Projeto de estruturas de aço.
8. **Orguel internal training** — *Treinamento Técnico Escoramento*, Nov 2020, 123 pp. Visually inspected page-by-page; full extraction in `PDF_FINDINGS.md`.
9. **Orguel engineer Q&A** — Calibration session 2026-04-07, n=12 projects.

---

## Hard Constraints from Norms

| Constraint | Value | Source |
|---|---|---|
| Sobrecarga de trabalho (área distribuída, concretagem) | **2.0 kN/m² = 204 kgf/m²** | NBR 15696 §4.2 + Orguel p.26 |
| Plataforma de trabalho (carga local em passarelas) | 1.5 kN/m² = 153 kgf/m² | NBR 15696 §4.2 + Orguel p.27 |
| Carga estática total mínima | 4.0 kN/m² = 408 kgf/m² | NBR 15696 §4.2 + Orguel p.26 |
| Vento mínimo (escoramento >10 m ou aberto) | 0.6 kN/m² = 61.2 kgf/m² | NBR 15696 §4.2 + NBR 6123 + Orguel p.26 |
| Vento adicional lateral | +5% V | Orguel p.27 (load diagram) |
| γc (concreto) | 25 kN/m³ = 2550 kgf/m³ | NBR 6120 + Orguel p.26 |
| γf (majoração de cargas) | 1.4 | NBR 15696 |
| Acréscimo em apoio central de viga contínua 3+ apoios | +25% (10/8 q·L) | Orguel p.109 (regra 14) |
| Reação em extremidades de viga contínua | 3/8 q·L | Orguel p.109 (regra 14) |

### Two simultaneous load systems — critical clarification

The Orguel training **page 27 load diagram** (image-only) shows both loads applied simultaneously to different parts of the structure:

- **Sobrecarga de trabalho (2.0 kN/m²)** is distributed across the **entire** concreting area during placement, vibration, and finishing.
- **Plataforma de trabalho (1.5 kN/m²)** is a **local** load applied only where work platforms (perimeter walkways) exist.

For typical projects without explicitly modeled work platforms, applying 2.0 kN/m² uniformly across the slab area is the correct simplification (NBR-compliant and conservative). For projects with defined perimeter walkways, add 1.5 kN/m² locally on those walkway zones.

Rule **LOAD-001** flags any project where the area-distributed sobrecarga is below 2.0 kN/m². This is the NBR minimum and is non-negotiable.

---

## Minimum Substrate Stress (NBR 15696 reference block, Orguel p.25)

Every Memória de Cálculo must include these and verify the substrate (slab below, soil + footing) can resist them:

| Equipment | Minimum stress at base |
|---|---|
| Apoio da torre de escoramento | **16.53 kgf/cm²** |
| Apoio das ESC2000–3100 (telescópica padrão) | **26.45 kgf/cm²** |
| Apoio das ESC3000–4500 (telescópica grande) | **17.35 kgf/cm²** |

If the substrate cannot resist these, the shoring base must be redistributed (sapatas larger than the standard 110 × 110 mm).

---

## Geometric Setbacks

| Setback | Value | Source |
|---|---|---|
| Distância da face do pilar (zona de punção) | 0.70 m mínimo | NBR 6118:2023 §19.5 |
| Distância da borda da laje (geral) | 0.15 m | Orguel practice (validated 2026-04-07) |
| Espaçamento mínimo entre escoras adjacentes | 0.30 m | Orguel practice (validated 2026-04-07) |
| Distância de alvenaria estrutural (laje encostada) | ≤ 5 cm | Orguel p.107 (regra 12) |

### Edge offset of barrotes (Orguel p.105–106, regra 11) — corrected

This rule depends on whether a lateral wall form is present:

- **With lateral wall form:** distance "x" from form edge to first barrote = **20 to 40 cm**.
- **Without lateral wall form (laje encostada na parede):** distance from concrete edge to first barrote = **5 cm**.

These are *not* about cantilever ends — they are about edge offset rules for the standard slab boundary case.

### Cotas reference rule (Orguel p.23)

All dimensions in shoring drawings must be measured **from concreted structure** (column or wall), never from arbitrary reference points. The output DXF must use columns/walls as dimension origins.

---

## Spacing — Slab Thickness × Plywood Combination Table (Orguel p.89)

This is the **canonical max-barrote-spacing lookup** in cm. Each cell has two values: **upper-left** = bi-apoiada (2 apoios), **lower-right** = continuous (3+ apoios).

| Espessura laje (cm) | Carga (kgf/m²) | 12 mm | 14 mm | 15 mm | 17 mm | 18 mm | 20 mm | 21 mm |
|---|---|---|---|---|---|---|---|---|
| 8 | 408 | 42/50 | 48/61 | 50/61 | 58/69 | 61/71 | 68/84 | 71/84 |
| 9 | 434 | 41/49 | 48/49 | 50/60 | 57/68 | 60/70 | 66/79 | 70/82 |
| 10 | 459 | 40/49 | 47/49 | 50/60 | 55/67 | 59/69 | 65/77 | 68/80 |
| 11 | 485 | 39/48 | 46/48 | 49/59 | 54/66 | 58/68 | 64/76 | 67/79 |
| 12 | 510 | 38/47 | 45/47 | 48/59 | 53/64 | 57/67 | 63/75 | 66/78 |
| 13 | 536 | 38/46 | 44/46 | 47/58 | 53/64 | 56/66 | 62/74 | 65/77 |
| 14 | 561 | 37/45 | 44/46 | 47/57 | 52/63 | 55/64 | 61/73 | 64/76 |
| 15 | 587 | 37/45 | 43/45 | 46/56 | 51/62 | 54/63 | 60/72 | 63/75 |
| 16 | 612 | 36/44 | 42/44 | 45/55 | 50/61 | 53/62 | 60/71 | 62/74 |
| 18 | 663 | 35/43 | 41/43 | 44/54 | 50/60 | 52/62 | 58/70 | 61/72 |
| 20 | 714 | 34/42 | 40/42 | 43/52 | 49/59 | 51/61 | 56/69 | 59/70 |
| 22 | 765 | 33/41 | 39/41 | 42/51 | 48/58 | 51/60 | 55/66 | 58/69 |
| 25 | 842 | 33/40 | 38/40 | 41/50 | 46/56 | 49/60 | 53/65 | 56/67 |
| 28 | 918 | 32/39 | 37/39 | 40/48 | 45/55 | 48/58 | 52/63 | 54/64 |
| 30 | 969 | 31/38 | 36/38 | 39/47 | 44/54 | 47/57 | 51/62 | 53/64 |
| 35 | 1097 | 30/36 | 35/36 | 37/46 | 42/51 | 45/54 | 50/60 | 51/62 |
| 40 | 1224 | 29/35 | 33/35 | 36/44 | 41/50 | 43/53 | 48/58 | 50/60 |
| 50 | 1479 | 27/33 | 31/33 | 34/41 | 38/47 | 41/49 | 45/55 | 47/57 |
| 60 | 1734 | 25/31 | 30/31 | 32/39 | 36/44 | 38/47 | 43/52 | 45/54 |
| 80 | 2244 | 23/29 | 27/29 | 29/36 | 34/40 | 35/43 | 39/48 | 41/50 |
| 100 | 2754 | 22/27 | 25/27 | 27/33 | 31/38 | 33/40 | 37/44 | 38/47 |

**Implementation:** encode this as `catalog/plywood_spans.yaml`. The system selects the row by slab thickness, the column by plywood thickness, and chooses 2-apoios or 3+-apoios based on the structural condition.

### Plywood Seam Alignment Constraint (Orguel p.114–115, regra 17)

Barrote spacing must be a **multiple of the plywood sheet length (220 mm or 244 mm)**. Plywood seams must fall **on the axis of a barrote**, never in mid-span. This makes barrote spacing a **discrete decision**.

### Spacing — Beams

- Telescópicas under beams: max **1.00 m** spacing.
- Towers under beams: max **1.50 m** spacing.
- Cruzetas (crossbars) under beams: every **0.80 m** (Engineer Q&A #5).

---

## Compensado (Plywood) Properties — Orguel p.78

| e (mm) | M_adm (kgf·m/m) | E·I (kgf·m²/m) | Self-weight P (kg/m²) |
|---|---|---|---|
| 12 | 26 | 98 | 7.0 |
| 14 | 36 | 156 | 8.0 |
| 15 | 41 | 192 | 9.0 |
| 17 | 53 | 279 | 10.0 |
| 18 | 60 | 331 | 10.5 |
| 20 | 73 | 455 | 12.0 |
| 21 | 81 | 526 | 12.5 |

σ_admissível à flexão = **110 kgf/cm²**
E_m (módulo de elasticidade médio) = **68 200 kgf/cm²**

Encoded in `catalog/plywood.yaml`. Standard plywood format: 1220 × 2440 mm (so length-multiples are 220 and 244 mm). Some projects use 220 mm format for older standards or specific suppliers — confirm per project.

---

## Slab Typology — Routing per Type (Orguel pages 28–49)

The system must classify each slab and route to the appropriate calculation pathway:

| Tipo | Detection cues from DXF | Strategy |
|---|---|---|
| **Maciça** (in-loco, "plana") | Solid hatch, single thickness, "Lh=" or "h=" annotation | Standard escoramento with guias + travessas + barrotes; vertical = escoras alone OR escoras+torres OR torres alone (depending on pé direito) |
| **Pré-moldada / treliçada** | Vigotas + lajotas pattern; thickness usually > 12 cm; visible vigota lines | **No fôrma needed.** Escoramento with guias only, no barrotes. Guias **perpendicular** to vigotas. **Mandatory line at contraflecha point** (typically center span) |
| **Alveolar** | Pré-moldado painel pattern, alveolar marks | **Most cases dispense escoramento.** Flag for engineer review |
| **Nervurada** | Cubeta grid pattern (square or rectangular cubetas) | **Mecaner system preferred** when polipropileno cubetas. Réguas Orguel are 75 mm or 30 mm wide. Cubeta width must be (nominal − 7.5 cm) on régua side |

### Vão máximo das vigotas

For pré-moldadas: comum até 5 m entre apoios (Orguel p.33). The vão máximo is set by the vigota fabricante; system must accept this as input parameter, not compute it.

---

## Decision Chain v3 (engineer-validated, expanded)

The system selects support type by walking these questions in order. **The first matching question wins.** Do not reorder. Calibrated against 12 Orguel projects (2026-04-07).

| # | Criterion | Result |
|---|---|---|
| 1 | Pé direito > 4.50 m? | 100% torre (limite físico ESC450) |
| 2 | Carga × 1.4 > capacidade derateada (Euler) de TODAS as telescópicas? | 100% torre |
| 3 | Sem torres em estoque (modo inventário)? | 100% telescópica |
| 4 | Vão > 15 m? | 100% torre (cimbramento pesado) |
| 5a | **Viga externa**: largura > 30 cm OR altura > 60 cm OR comprimento > 3.0 m? | Inclusão de torres OU estaiamento (regra 16, parte A) |
| 5b | **Viga interna**: comprimento > 10 m OR largura > 40 cm OR altura > 70 cm? | 100% torres |
| 5c | **Viga interna**: comprimento entre 6 e 10 m? | MISTO (escoras + torre central) — regra 16, parte B |
| 5d | **Viga interna**: comprimento ≤ 6 m, largura ≤ 40 cm, altura ≤ 70 cm? | 100% escoras + cruzetas |
| 6 | Viga com (laje ≥ 15 cm OR vão > 6 m)? | MISTO — 35% torres em extremidades e interseções |
| 7 | Laje com espessura ≥ 20 cm? | MISTO — 18% torres em grid |
| 8 | Painel de laje ≥ 40 m²? | MISTO — 15% torres em grid largo |
| 9 | Laje nervurada ≥ 25 cm? | MISTO — 20% torres |
| 10 | Default (nenhuma das anteriores) | 100% telescópica (ESC310 ou ESC450 conforme altura) |

**Note on Q1 vs. Q9 from p.9:** for level supports with vão entre vigas ≤ 4 m AND pé direito ≤ 3.50 m, telescópicas alone are the recommended solution (Orguel comfort zone). Between 3.50 and 4.50 m, telescópicas are still possible but require explicit verification of derated capacity. **Open question:** confirm with engineers whether to add a separate Q1.5 for the 3.50–4.50 m intermediate band.

---

## Tower Capacity Curve — Orguel p.86

Tower capacity decreases with the number of 1.5 m modules (Euler buckling). Each module = 1.5 m of height.

| Modules | Height | Capacity (kN) | | Modules | Height | Capacity (kN) |
|---|---|---|---|---|---|---|
| 1 | 1.5 m | 2000 | | 11 | 16.5 m | 1650 |
| 2 | 3.0 m | 1900 | | 12 | 18.0 m | 1630 |
| 3 | 4.5 m | 1850 | | 13 | 19.5 m | 1610 |
| 4 | 6.0 m | 1800 | | 14 | 21.0 m | 1590 † |
| 5 | 7.5 m | 1770 | | 15 | 22.5 m | 1570 |
| 6 | 9.0 m | 1750 | | 16 | 24.0 m | 1550 |
| 7 | 10.5 m | 1730 | | 17 | 25.5 m | 1530 |
| 8 | 12.0 m | 1710 | | 18 | 27.0 m | 1510 |
| 9 | 13.5 m | 1690 | | 19 | 28.5 m | 1490 |
| 10 | 15.0 m | 1670 | | 20 | 30.0 m | 1470 |

† PDF chart shows "14 = 1500" but this breaks the monotonic curve and is almost certainly a typo for 1590. **Confirm with Orguel before encoding.** Until confirmed, the system flags any 14-module placement for engineer review.

---

## Telescópica Capacity Curves — Orguel p.11

Three full curves (previously "open question," now resolved).

### ESC Junior (Somente Venda) — abertura 2.00–3.10 m
Tubes: flauta Ø 42.20 mm, capa Ø 50.80 mm.

| abertura (m) | 2.00 | 2.10 | 2.20 | 2.30 | 2.40 | 2.50 | 2.60 | 2.70 | 2.80 | 2.90 | 3.00 | 3.10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| carga (kgf) | 2000 | 1900 | 1800 | 1700 | 1550 | 1425 | 1300 | 1225 | 1150 | 1100 | 1050 | 1000 |

### ESC 2000 a 3100 — abertura 2.00–3.10 m
Tubes: flauta Ø 42.20 mm, capa Ø 50.80 mm.

| abertura (m) | 2.00 | 2.10 | 2.20 | 2.30 | 2.40 | 2.50 | 2.60 | 2.70 | 2.80 | 2.90 | 3.00 | 3.10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| carga (kgf) | 3200 | 2850 | 2650 | 2550 | 2400 | 2250 | 2100 | 1900 | 1800 | 1650 | 1550 | 1500 |

### ESC 3000 a 4500 — abertura 3.00–4.50 m
Tubes: flauta Ø 50.80 mm, capa Ø 60.30 mm.

| abertura (m) | 3.00 | 3.10 | 3.20 | 3.30 | 3.40 | 3.50 | 3.60 | 3.70 | 3.80 | 3.90 | 4.00 | 4.10 | 4.20 | 4.30 | 4.40 | 4.50 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| carga (kgf) | 2100 | 2000 | 1900 | 1800 | 1700 | 1650 | 1550 | 1500 | 1400 | 1350 | 1250 | 1150 | 1050 | 950 | 850 | 750 |

These three curves fully resolve the previous "open question" about telescópica derating.

---

## Equipment Catalog (Orguel — comprehensive)

**Single source of truth: `catalog/equipment.yaml`.**

### VM Properties (Orguel p.69)

| Tipo | Material | E·I (kgf·m²) | M_adm (kgf·m) | Peso (kg/m) |
|---|---|---|---|---|
| VM-80 | metálica | 14 965 | 212 | 6.41 |
| VM-130 | metálica | 47 094 | 516 | 9.70 |
| ALU-14 | alumínio | 20 309 | 409 | 4.00 |
| ALU-20 | alumínio | (n/a) | 800 | 6.35 |
| HT-20 | madeira | 51 758 | 500 | 5.17 |

### Painéis de torre (Orguel p.13–16)

| Largura (mm) | Alturas disponíveis (mm) |
|---|---|
| 1000 | 1000, 1250, 1500 |
| 1540 | 1000, 1250, 1500 |

### Diagonais (Orguel p.13–17)

**Diagonal Tubular (DT):** modelos 1–5 com comprimentos 1415, 1840, 2180, 2280, 2540 mm.

**Diagonal em X (DX):** modelos 1–6 com comprimentos 1200, 1410, 1680, 1840, 2150, 2280 mm.

**Tabela de uso DT (p.17):**
| Diagonal X | Painel | Tamanho da DT |
|---|---|---|
| 155 | 154 | 2180 |
| 155 | 100 | 1840 |
| 205 | 154 | 2540 |
| 205 | 100 | 2280 |
| 100 | 154 | 1840 |
| 100 | 100 | 1415 |

### Acessórios (Orguel p.18)

| Componente | Dimensão principal |
|---|---|
| Sapata Simples | 110 × 110 mm |
| Sapata Ajustável | regulagem 300 mm |
| Forcado Fixo Simples | altura 65 mm, abertura 85 mm |
| Forcado Fixo Duplo | altura 70 mm, abertura 205 mm |
| Forcado Fixo H20 | altura 180 mm, abertura 170 mm |
| Forcado Ajustável Duplo H20 | regulagem haste 300 mm, altura forcado 180 mm |
| Forcado Ajuste Simples | altura 65 mm, abertura 85 mm |
| Forcado p/ Vigas Metálicas | altura 65 mm, abertura 85 mm |
| Console (Mão Francesa) | base 540 mm, comprimento 710 mm, altura 250 mm |
| Barra de Ligação | 300 mm or 500 mm |

### Tower height calculation rule (Orguel p.89, Example 2)

`H_torre = pé_direito − espessura_laje − ajuste_topo_base`

where `ajuste_topo_base` is typically **0.224 m** (sapata + forcado combined). Tower module heights (1500 + 1000 = 2500 mm = 2.5 m) plus the ajuste must reach within 0.49 m of the target H_torre, with the remainder taken by sapata + forcado regulagem.

For escoras: `escora_abertura = pé_direito − espessura_laje − 0.224 m`.

---

## Travamento Rules

### Pillar bracing (Orguel pages 62–64)

Materials: tirantes, tensores, cantoneiras de fixação, aprumadores, sapatas articuladas, vigas metálicas (VM50 or VM80).

By column face dimension:

| Face | Estratégia | Materiais (per Orguel example) |
|---|---|---|
| Até 25 cm | Travamento simples com tirantes + VM80 | ~10× VM80-1550, ~10× tirantes 650, vertical spacing 80 cm |
| 25–40 cm | Idem, ajustar quantidade | Per vão máximo da forma |
| > 40 cm | **Vigas metálicas em todos os 4 lados** (alternar travessas em 2 lados é possível) | VM50-1000 + tirantes 1000/1500 |
| > 90 cm | Idem + **VM vertical adicional** | VM80-1550, VM80-2550, tirantes 650/1000, aprumadores |

### Lateral bracing of beams (Orguel pages 65–66)

Required when painéis laterais > 60 cm (or per client instruction).

**Tirante count by VM length:**

| Tamanho VM (mm) | Quantidade tirantes |
|---|---|
| 1000 | 2 |
| 1550 | 2 |
| 2050 | 3 |
| 2550 | 3 |
| 3100 | 4 |
| 3600 | 5 |
| 4100 | 5 |

**Tirante length formula (p.66):**
`tirante = 2 × 5.5 + 2 × 8.0 + 2 × e + L`
where: 5.5 cm = minimum thread for porcas, 8.0 cm = VM80 width, e = espessura da forma, L = largura da viga.

Spacing constraint: respect VM length OR vão máximo de 1.00 m (whichever is smaller).

### Beam bottom bracing (Orguel p.67)

- Tirantes + cantoneiras de fixação between cruzetas (when escoras under beam) or between barrotes (when towers under beam).
- **Quantity rule:** number of tirantes = number of cruzetas (or barrotes) on the beam bottom.

---

## Reescoramento Rules

This is a separate subsystem with its own constraints and outputs.

### Concept

- Concreto needs ~28 days to fully cure. Reescoramento bridges that gap.
- Sequence: (a) escoras released, (b) full desforma, (c) slab deforms slightly and is **"ativada"** — only then can it transfer loads from upper levels.

### Hard rules (Orguel p.55, p.59)

| Rule | Value | Source |
|---|---|---|
| Vão livre máximo no reescoramento | **2.0 m** | Orguel p.59 |
| Reescoramento 50% (load fraction) | 50% × carga_escoramento | Orguel p.59 |
| Reescoramento 25% (load fraction) | 25% × carga_escoramento | Orguel p.59 |
| Reescoramento remanescente (during upper concretagem) | full load + upper levels' loads | Orguel p.59 |
| Sem desforma + sem liberação | 200% carga (bad practice — reject) | Orguel p.55 |

### Project notes rule (p.59)

The reescoramento project **must include explicit notes** stating:
- The reescoramento type (50%, 25%, remanescente)
- The carga considerada
- The validation by the contratante (obra's calculista)

### Output rule (p.60)

All reescoramento projects from Orguel's Engenharia de Aplicação are **suggestions only**. Responsibility for use stays with the obra's engineer or estrutural calculista.

This is the **canonical legal framing** for our entire output paradigm: every Memória de Cálculo PDF must carry this disclaimer prominently.

---

## Validated Calibration Envelope (Orguel 2026-04-07, n=12)

| Metric | Range | Default |
|---|---|---|
| Tower fraction in beams (mixed mode) | 29–44% | 35% |
| Tower fraction in slabs (mixed mode) | 13–22% | 15–18% |
| kg/m³ envelope (base a reconciliar — ver nota) | 12–16 kg/m³ | — |
| Tower utilization (light structures) | 60–80% | — |

> **⚠️ kg/m³ envelope — base inconsistente, atualmente DIAGNÓSTICO (não gate).**
> A faixa [12,16] foi calibrada numa base que NÃO é a que o motor computa hoje.
> O motor mede **peso vertical das escoras ÷ volume escorado (área×pé-direito)**;
> nessa base até projetos normais ficam ~3–7 kg/m³ (CFL=6.7, CVS=5.1, e os reais
> 105475=6.1, 35412=3.5, 59428=6.7 no BOM parcial). Logo, qualquer corte em
> [12,16]/[8,20] falso-positiva. Por isso o kg/m³ foi **removido como gate** de
> `requires_review` (runner), dos avisos do relatório (report_data) e da regra
> ENV-001 (desabilitada) — virou diagnóstico (`runner.consumption_diagnostics`).
> **Follow-up:** reconciliar a referência Orguel — a faixa [12,16] veio de qual
> peso (só escoras? BOM total alugado incl. madeira/compensado?) e qual volume
> (escorado ou de concreto)? Só re-ligar como gate após confirmar a base.
> O que continua gate de revisão: BLOCKED/SPECIAL_REVIEW e resultado vazio.

---

## Mandatory Output Header (per Orguel p.25)

Every Memória de Cálculo PDF must include this reference block at the front, with project-specific values filled in:

```
─── REFERÊNCIAS TÉCNICAS ───────────────────────────
• Espessura do Compensado: ___ mm (___ × ___ cm)
• Espessura da Laje: ___ cm
• Peso Específico do Concreto: ____ kgf/m³
• Sobrecarga Considerada: ____ kgf/m²
• Peso Próprio da Laje: ____ kgf/m²
• Carga de Escoramento: ____ kgf/m²
• Pé Direito do Pavimento: ____ m
• Carga Máx. Adm. p/ Poste: ____ kgf
• Momento Máximo Admissível das Vigas:
   - VM80:  0.212 tf·m
   - VM130: 0.516 tf·m
   - H20 e Alumínio: 0.500 tf·m
─── TENSÕES NO APOIO ───────────────────────────────
• Apoio da torre de escoramento: 16.53 kgf/cm²
• Apoio das ESC2000-3100: 26.45 kgf/cm²
• Apoio das ESC3000-4500: 17.35 kgf/cm²
─── DISCLAIMER (Orguel p.60) ────────────────────────
Este projeto é uma SUGESTÃO da Engenharia de
Aplicação. A responsabilidade quanto à sua
utilização fica a cargo do engenheiro responsável
pela obra ou engenheiro calculista da estrutura.
─────────────────────────────────────────────────────
```

---

## Operational Rules (must be enforced or noted in output)

These are non-negotiable engineering practices from Orguel pages 97–115.

| ID | Rule | Source |
|---|---|---|
| OP-001 | Escoramento sobre base firme; preparação responsabilidade do cliente | p.97 (rule 1) |
| OP-002 | Escoramento vertical aprumado | p.98 (rule 2) |
| OP-003 | Ajuste de topo e base sem folgas | p.99 (rule 3) |
| OP-004 | Apoio correto de guias com cunhas | p.100 (rule 4) |
| OP-005 | Madeiramento dimensionado conforme projeto | p.101 (rule 5) |
| OP-006 | Tempo de cura: responsabilidade do cliente | p.102 (rule 6) |
| OP-007 | Inspeção de equipamentos antes do uso | p.103 (rule 7) |
| OP-008 | Não alterar projeto sem comunicação à Orguel | p.104 (rule 8) |
| OP-009 | Travamento e amarração das fôrmas: responsabilidade do cliente | p.104 (rule 10) |

These appear as a **standard notes section** in every output Memória de Cálculo, not as automatic verifiers.

---

## Open Engineering Questions

These items still require confirmation from Orguel engineers.

1. **Tower curve at module 14.** Chart shows 1500 kN, breaking the monotonic decrease. Almost certainly a typo for 1590. Confirm before encoding.

2. **3.50–4.50 m intermediate band (p.9 vs. p.12).** Page 9 says vão ≤ 4 m AND pé direito ≤ 3.50 m → escoras recommended. Page 12 says > 4.50 m → torres mandatory. What is the recommendation for 3.50–4.50 m? Add a Q1.5 to the decision chain or treat as engineer-review-only?

3. **Decision Chain Q5 split.** Q5 was split into Q5a/b/c/d to capture both external (p.111) and internal (p.112–113) beam rules from regra 16. Validate this expansion before promoting to production.

4. **Plywood format.** Standard 1220 × 2440 mm assumed (length-multiples 220 and 244 mm). Confirm whether projects use other formats.

5. **Special-case routing.** Orguel pp.116–121 describe special cases (Alu-14, grandes alturas, escoramento aéreo, H20 rampas, projetos especiais). Should the system route to "fora do automático" with engineer notification when these characteristics are detected, or attempt automated handling?

> Add new questions as they arise. Do not invent answers. Do not silently choose between alternatives — flag and stop.

---

## Output Traceability Rule (CRITICAL)

Every numeric output **MUST** carry a `Source` citation. The `LoadValue` type and `Project.violations` enforce this at the type level. Any code path producing a numeric value without a `Source` is a bug.

Source schema:

```python
class Source(BaseModel):
    type: Literal["norm", "manual", "dxf_pattern", "engineer_qa"]
    ref: str          # "NBR 15696:2009 §4.2.1" or "Orguel p.86"
    calibration: str | None = None  # "Orguel 2026-04-07 (n=12)"
```

Cite at this granularity:
- "Orguel p.86" — for the tower derating curve
- "Orguel p.89" — for the plywood span table
- "Orguel p.111" — for external beam rules
- "Orguel p.112" — for internal beam rules
- "Orguel p.59" — for reescoramento vão limit
- "Orguel 2026-04-07 (n=12)" — for engineer-validated heuristics (35%, 18%, 15%, 12-16 kg/m³)

---

## Hard Rules for Coding Agents

1. **Do not weaken any test to make it pass.**
2. **Do not invent norm references or numeric values.**
3. **Every numeric output carries a `Source` citation.**
4. **Do not modify `tests/regression/`** without explicit operator approval.
5. **No silent fallbacks** — raise typed exceptions instead.

---

## Validation Gates

A change ships only if:

1. All unit tests pass: `pytest tests/unit/ -v`
2. Regression suite has ≥ baseline pass count and ≤ baseline fail count
3. No new error-severity violations on calibration set
4. kg/m³ envelope holds for ≥ 10 of 12 calibration projects
5. No code path produces a numeric output without a `Source`

---

## Engineering Sign-off

This system produces **auditable drafts**, not final designs. Final approval requires a CREA-registered engineer's ART.

The system MUST NOT remove or hide the ART block, suppress active violations, or mark a project "approved."

Output PDF includes:
- "Pendências para revisão do engenheiro responsável" listing error-severity violations
- Separate appendix with warning-severity violations
- Reference block (above)
- Disclaimer per Orguel p.60
- Unfilled ART block at the end

---

## Standing Prompt

```
You are working on Escora.AI. Read AGENTS.md and MIGRATION_PLAN.md
before doing anything else. Cross-reference PDF_FINDINGS.md when
encoding rules from the Orguel training material.

Hard rules (non-negotiable):
1. Do not weaken any test to make it pass.
2. Do not invent norm references or numeric values.
3. Every numeric output carries a Source citation.
4. Do not modify tests/regression/ without operator approval.
5. No silent fallbacks — raise typed exceptions instead.

Before declaring task complete:
  pytest tests/unit/ tests/regression/ -v
Report diff in pass/fail/xfail counts vs the previous run. If
regression worsens, stop, revert, reframe.

Current task: <paste task block from MIGRATION_PLAN.md>
```
