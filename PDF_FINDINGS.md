# Orguel Training PDF — Rule Extraction Catalog

> Source: `Treinamento_Tecnico_Escoramento-20-11-2020.pdf`, Grupo Orguel, Nov 2020 (123 pages).
>
> Method: All 123 pages rasterized at 110 DPI and visually inspected. Text-extraction was used as a coarse content profile but every rule-bearing page was read from its image because much of the operational content (tables, capacity curves, dimension diagrams, decision matrices) is encoded as flattened images that text extraction misses entirely.
>
> Status of each rule: `[encoded]` already in AGENTS.md, `[corrected]` was wrong before, `[new]` newly extracted, `[open]` requires engineer confirmation.

---

## 1. Concept layer (pages 5–9)

- **p.8** Escoras telescópicas: range 2.00 m to 4.50 m. `[encoded]`
- **p.9** *Decision precondition (refined):* For level supports, slabs with vão entre vigas ≤ 4 m AND pé direito ≤ 3.50 m → escoras telescópicas are the recommended solution. The 4.50 m hard ceiling is the absolute upper bound of escoras; the 3.50 m threshold is the comfort zone. Between 3.50 m and 4.50 m, escoras are still mechanically possible but require verification of derated capacity. `[new]` `[open: Confirm with Orguel whether the system should default to towers above 3.50 m or only above 4.50 m]`
- **p.12** Torres: used as the only vertical element when pé direito > 4.50 m (matches Decision Chain Q1). Direct quote from the PDF. `[encoded]`

---

## 2. Equipment composition (pages 10–21)

### Telescópicas — capacity tables (p.11) `[corrected]`

The PDF gives **three full extension-to-capacity curves** I had previously marked as "open question." Now fully encoded:

**ESC Junior (Somente Venda) — abertura 2.00–3.10 m:**
| abertura (m) | 2.00 | 2.10 | 2.20 | 2.30 | 2.40 | 2.50 | 2.60 | 2.70 | 2.80 | 2.90 | 3.00 | 3.10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| carga (kgf) | 2000 | 1900 | 1800 | 1700 | 1550 | 1425 | 1300 | 1225 | 1150 | 1100 | 1050 | 1000 |

Tubes: flauta Ø 42.20 mm, capa Ø 50.80 mm.

**ESC 2000 a 3100 — abertura 2.00–3.10 m:**
| abertura (m) | 2.00 | 2.10 | 2.20 | 2.30 | 2.40 | 2.50 | 2.60 | 2.70 | 2.80 | 2.90 | 3.00 | 3.10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| carga (kgf) | 3200 | 2850 | 2650 | 2550 | 2400 | 2250 | 2100 | 1900 | 1800 | 1650 | 1550 | 1500 |

Tubes: flauta Ø 42.20 mm, capa Ø 50.80 mm.

**ESC 3000 a 4500 — abertura 3.00–4.50 m:**
| abertura (m) | 3.00 | 3.10 | 3.20 | 3.30 | 3.40 | 3.50 | 3.60 | 3.70 | 3.80 | 3.90 | 4.00 | 4.10 | 4.20 | 4.30 | 4.40 | 4.50 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| carga (kgf) | 2100 | 2000 | 1900 | 1800 | 1700 | 1650 | 1550 | 1500 | 1400 | 1350 | 1250 | 1150 | 1050 | 950 | 850 | 750 |

Tubes: flauta Ø 50.80 mm, capa Ø 60.30 mm.

These three tables fully replace the earlier single-point "ESC450 = 14 kN" approximation and unblock Decision Chain Q2.

### Torres — components (pages 13–17)

**Painéis (panel sizes):**
| Largura (mm) | Altura disponível (mm) |
|---|---|
| 1000 | 1000, 1250, 1500 |
| 1540 | 1000, 1250, 1500 |

**Diagonal Tubular (DT) — comprimentos:**
| Modelo | Comprimento (mm) |
|---|---|
| 1 | 1415 |
| 2 | 1840 |
| 3 | 2180 |
| 4 | 2280 |
| 5 | 2540 |

**Diagonal em X (DX) — comprimentos:**
| Modelo | Comprimento (mm) |
|---|---|
| 1 | 1200 |
| 2 | 1410 |
| 3 | 1680 |
| 4 | 1840 |
| 5 | 2150 |
| 6 | 2280 |

**Diagonal em X de dois furos:**
| Modelo | Menor (A) (mm) | Maior (B) (mm) |
|---|---|---|
| 1 | 1200 | 1410 |
| 2 | 1680 | 1840 |
| 3 | 2150 | 2280 |

**Tabela para uso da DT (p.17):**
| Diagonal X | Painel | Tamanho da DT |
|---|---|---|
| 155 | 154 | 2180 |
| 155 | 100 | 1840 |
| 205 | 154 | 2540 |
| 205 | 100 | 2280 |
| 100 | 154 | 1840 |
| 100 | 100 | 1415 |

This is the lookup table for selecting the correct DT length given the X-diagonal × panel combination — needed for tower assembly BOM. `[new]`

### Acessórios (page 18) `[new]`

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

---

## 3. Project section (pages 22–27)

- **p.23** *Project requirements (NBR 15696):* "Cotas sempre em relação à estrutura concretada (ex: pilar ou parede)." All dimensions in shoring drawings must be measured from concreted structure (column or wall), never from arbitrary reference points. `[new]`
- **p.24** Project must include plans, sections, views, and details to remove ambiguity in installation. Documentation rule. `[new]`
- **p.25** *Reference block — every shoring project's Memória de Cálculo must include:* `[new]`
  - Espessura do compensado (mm) and panel size (cm × cm)
  - Espessura da laje (cm)
  - Peso específico do concreto (kgf/m³) — typically 2550
  - Sobrecarga considerada (kgf/m²) — minimum 204 (= 2.0 kN/m²)
  - Peso próprio da laje (kgf/m²)
  - Carga de escoramento (kgf/m²)
  - Pé direito do pavimento (m)
  - Carga máxima admissível por poste (kgf)
  - Momento máximo admissível por viga: VM80 = 0.212 tf·m, VM130 = 0.516 tf·m, H20 e Alumínio = 0.500 tf·m
- **p.25** *Tensões mínimas no apoio (kgf/cm²):*
  - Apoio da torre de escoramento: **16.53 kgf/cm²**
  - Apoio das ESC2000–3100: **26.45 kgf/cm²**
  - Apoio das ESC3000–4500: **17.35 kgf/cm²**
  
  These are the minimum compressive stresses each base must transfer to the substrate. The substrate (slab below, soil + footing, etc.) must be capable of resisting these. `[new]`
- **p.26** *Cargas atuantes (NBR 15696):*
  1. Peso próprio do escoramento e fôrmas — used in escoramentos > 10 m.
  2. Peso próprio dos elementos de concreto: 25 kN/m³ = 2550 kgf/m³.
  3. Sobrecarga de trabalho (concretagem): mínimo 2.0 kN/m² = 204 kgf/m². `[corrected]`
  4. Plataformas de trabalho: 1.5 kN/m² = 153 kgf/m². `[corrected]`
  5. Carga total estática mínima: 4.0 kN/m² = 408 kgf/m².
  6. Vento (NBR 6123): mínimo 0.6 kN/m² = 61.2 kgf/m². Used in escoramentos > 10 m or open sites.
- **p.27** *Critical clarification — load diagram (image-only page):* All six loads above are applied **simultaneously** to different parts of the structure. Sobrecarga de trabalho (item 3, 2.0 kN/m²) covers the entire concreting area. Plataforma de trabalho (item 4, 1.5 kN/m²) is local at perimeter walkways. They are NOT alternatives. Wind (item 6) is applied laterally with a 5% V additional component. `[corrected]`

---

## 4. Slab typology (pages 28–49)

### Lajes maciças (pages 29–32) `[encoded]`

- Moldadas in-loco, also called "planas." Cargas to vigas → pilares.
- Escoramento with guides and travessas distributed over vertical shoring (escoras+torres OR torres alone when pé direito doesn't allow escoras). Forrada por compensado.
- pp.31–32 show a real Orguel project drawing: layout-out de torres e vigas metálicas with VM130-410, VM130-310, VM80-255 etc. labels — direct evidence of how the BOM annotates the layout. `[reference for output format]`

### Lajes pré-moldadas (pages 33–36) `[new]`

- **Não necessitam de fôrma**, only escoramento dimensioned by **vão máximo das vigotas**.
- Required: escoramento with **guias only** (no barroteamento), placed perpendicular to vigotas.
- *Rule (p.36):* Guias deve ser posicionada perpendicularmente às vigotas, with vão máximo per fabricante/contratante.
- **Mandatory line of shoring at the contraflecha point** (typically at center span; exception: alveolares).
- If using only escoras (no guias), they must be tied together with tubos de amarração or sarrafo (responsibility: client).

### Lajes alveolares (page 39) `[new]`

- Concreto protendido panels. Most cases **dispensam o escoramento**.

### Lajes nervuradas (pages 40–49) `[new]`

- Conjunto de vigas cruzadas + mesa.
- Standard option: cubas de polipropileno (temporary) or blocos cerâmicos/EPS (permanent).
- **Mecaner system** (Orguel proprietary) for nervuradas:
  - Réguas metálicas replace sarrafo de madeira.
  - Régua widths: **75 mm or 30 mm**.
  - Encaixe macho/fêmea between réguas; cabeçal with pin.
  - Allows desforma rápida — fôrmas can be released without removing escoras.
  - **Cubeta dimensioning rule (p.44):** Cubeta width must be (nominal − 7.5 cm) on the régua side. Example: a "80 cm" cubeta must be 80 × 72.5 cm (réguas Orguel are 7.5 cm wide).
  - Faixa de reescoramento uses **Cabeçal de Espera** intercalated with régua.
  - After cura: shoring removed, guias and cubetas removed, **only the Cabeçal stays on the reescoras**.

---

## 5. Reescoramento (pages 50–60) `[new — full subsystem]`

### Concept (p.51–53)

- Concreto needs ~28 days to fully cure. Until then, it cannot receive its full design load.
- **Reescoramento** = provisional structure under a concrete slab that doesn't yet have full capacity, transmitting loads to rigid/flexible supports.
- **Sequence (p.53):** (a) escoras are removed/released, (b) full desforma occurs, (c) slab deforms slightly and is now **"ativada"** — ready to transfer loads from the upper levels.

### Reescoramento types (p.55) — `[critical]`

- **Sem desforma ou liberação:** carga total (200%) transferred to foundation since the level was never activated. Bad practice, must be avoided.
- **Liberação total da 1ª laje:** laje is activated and carries its own weight (100%).

### Reescoramento remanescente (pages 54, 58–59)

- Method: a 15-cm wide strip of plywood is left during initial assembly. Intermediate escoras are placed on this strip. After desforma, the strip + remanescentes are kept while the rest is removed and reused.
- **Hard rule (p.59):** **Vão livre máximo no reescoramento = 2.0 m.** Even if calculated loads would allow more, do not exceed 2.0 m without explicit approval from the obra's calculista.
- **Load fractions for design:**
  - Reescoramento 50% → consider 1/2 of the escoramento load on each remanescente.
  - Reescoramento 25% → consider 1/4 of the load.
  - Reescoramento remanescente (kept during concretagem of the upper level) → consider full load + upper levels' loads.
- **p.60 (legal):** All reescoramento projects produced by Orguel's Engenharia de Aplicação are sent **as suggestion only**. Responsibility for use stays with the obra's engineer or estrutural calculista. **This is the critical legal framing for our auditable-draft model.**

---

## 6. Travamento (pages 61–67) `[new — partial encoding existed]`

### Pillar bracing (pages 62–64)

- General principle: travamento de pilares uses tirantes, tensores, cantoneiras de fixação, aprumadores, sapatas articuladas, and vigas metálicas (VM50 or VM80).
- **Rule by face dimension (size threshold):**
  - **Face up to ~25 cm:** travamento with VM80 + tirantes only, ~10 sets of each, vertical spacing 80 cm. Detail "DETALHE PARA TRAVAMENTO DE PILARES (25/75)" on p.62.
  - **Face > 40 cm:** travamento with metal beams **on all four sides** of the column. Possible to alternate travessas on two sides for material economy. Spacing per vão máximo da forma. (p.63)
  - **Face > 90 cm:** in addition to the four-side cage, **add vertical VM** to reduce the span between tirantes. Detail "DETALHE PARA TRAVAMENTO DE PILARES (25x100)" on p.64.

### Lateral bracing of beams (pages 65–66)

- Beams with painéis laterais > 60 cm (or per client request) → require lateral bracing (no madeira, only tirantes + VM).
- **Tirante count by VM length (p.65 table):**
| Tamanho da VM (mm) | Quantidade de tirantes |
|---|---|
| 1000 | 2 |
| 1550 | 2 |
| 2050 | 3 |
| 2550 | 3 |
| 3100 | 4 |
| 3600 | 5 |
| 4100 | 5 |
- **Tirante length formula (p.66):** `Tirante = 2 × 5.5 + 2 × 8.0 + 2 × e + L` where e = espessura da forma, L = largura da viga. The 2 × 5.5 reserves 5.5 cm minimum thread on each end so the porcas can be threaded. The 2 × 8.0 are the VM80 widths.
- **Spacing constraint:** lateral bracing must respect either VM length or **vão máximo de 1.00 m** (whichever is smaller).

### Beam bottom bracing (page 67)

- Tirantes + cantoneiras de fixação must be positioned **between cruzetas** (when escoras under beam) or **between barrotes** (when towers under beam).
- **Quantity rule:** number of tirantes = number of cruzetas (or barrotes) on the beam bottom.

---

## 7. Calculation methodology (pages 68–95)

### Theoretical foundation (pages 69–76, 80–86)

- **VM properties (p.69):** as already encoded, plus added confirmation:
  - VM-80: E·I = 14965 kgf·m², M_adm = 212 kgf·m, peso = 6.41 kg/m (metálica)
  - VM-130: E·I = 47094 kgf·m², M_adm = 516 kgf·m, peso = 9.70 kg/m (metálica)
  - ALU-14: E·I = 20309 kgf·m², M_adm = 409 kgf·m, peso = 4.00 kg/m (alumínio)
  - ALU-20: M_adm = 800 kgf·m, peso = 6.35 kg/m
  - HT-20: E·I = 51758 kgf·m², M_adm = 500 kgf·m, peso = 5.17 kg/m (madeira)

- **Compensado (plywood) properties (p.78):** as already encoded, with hard limits σ_adm = 110 kgf/cm² and E_m = 68200 kgf/cm². `[encoded]`

- **Worked example: viga 30×80 cm with laje 10 cm slab on each side (pages 70–76):**
  - q = 856.7 kgf/m before majoration `[verified]`
  - For central support of continuous beam with 3 supports: +25% acréscimo (10/8 q·L), validating LOAD-003. `[encoded]`

### Plywood span table (page 89) `[NEW — major finding]`

This is the full **Espaçamentos máximos entre vigas secundárias para diversos compensados em cm — segundo NBR 15696 — para 2 / 4 apoios** that was the major "open question" in the previous AGENTS.md. Each cell has two values: the upper-left is the **2-apoios** (bi-apoiada) span, the lower-right is the **3+-apoios** (multi-apoiada) span:

| Espessura laje (cm) | Carga (kgf/m²) | 12 mm | 14 mm | 15 mm | 17 mm | 18 mm | 20 mm | 21 mm |
|---|---|---|---|---|---|---|---|---|
| 8 | 408 | 42 / 50 | 48 / 61 | 50 / 61 | 58 / 69 | 61 / 71 | 68 / 84 | 71 / 84 |
| 9 | 434 | 41 / 49 | 48 / 49 | 50 / 60 | 57 / 68 | 60 / 70 | 66 / 79 | 70 / 82 |
| 10 | 459 | 40 / 49 | 47 / 49 | 50 / 60 | 55 / 67 | 59 / 69 | 65 / 77 | 68 / 80 |
| 11 | 485 | 39 / 48 | 46 / 48 | 49 / 59 | 54 / 66 | 58 / 68 | 64 / 76 | 67 / 79 |
| 12 | 510 | 38 / 47 | 45 / 47 | 48 / 59 | 53 / 64 | 57 / 67 | 63 / 75 | 66 / 78 |
| 13 | 536 | 38 / 46 | 44 / 46 | 47 / 58 | 53 / 64 | 56 / 66 | 62 / 74 | 65 / 77 |
| 14 | 561 | 37 / 45 | 44 / 46 | 47 / 57 | 52 / 63 | 55 / 64 | 61 / 73 | 64 / 76 |
| 15 | 587 | 37 / 45 | 43 / 45 | 46 / 56 | 51 / 62 | 54 / 63 | 60 / 72 | 63 / 75 |
| 16 | 612 | 36 / 44 | 42 / 44 | 45 / 55 | 50 / 61 | 53 / 62 | 60 / 71 | 62 / 74 |
| 18 | 663 | 35 / 43 | 41 / 43 | 44 / 54 | 50 / 60 | 52 / 62 | 58 / 70 | 61 / 72 |
| 20 | 714 | 34 / 42 | 40 / 42 | 43 / 52 | 49 / 59 | 51 / 61 | 56 / 69 | 59 / 70 |
| 22 | 765 | 33 / 41 | 39 / 41 | 42 / 51 | 48 / 58 | 51 / 60 | 55 / 66 | 58 / 69 |
| 25 | 842 | 33 / 40 | 38 / 40 | 41 / 50 | 46 / 56 | 49 / 60 | 53 / 65 | 56 / 67 |
| 28 | 918 | 32 / 39 | 37 / 39 | 40 / 48 | 45 / 55 | 48 / 58 | 52 / 63 | 54 / 64 |
| 30 | 969 | 31 / 38 | 36 / 38 | 39 / 47 | 44 / 54 | 47 / 57 | 51 / 62 | 53 / 64 |
| 35 | 1097 | 30 / 36 | 35 / 36 | 37 / 46 | 42 / 51 | 45 / 54 | 50 / 60 | 51 / 62 |
| 40 | 1224 | 29 / 35 | 33 / 35 | 36 / 44 | 41 / 50 | 43 / 53 | 48 / 58 | 50 / 60 |
| 50 | 1479 | 27 / 33 | 31 / 33 | 34 / 41 | 38 / 47 | 41 / 49 | 45 / 55 | 47 / 57 |
| 60 | 1734 | 25 / 31 | 30 / 31 | 32 / 39 | 36 / 44 | 38 / 47 | 43 / 52 | 45 / 54 |
| 80 | 2244 | 23 / 29 | 27 / 29 | 29 / 36 | 34 / 40 | 35 / 43 | 39 / 48 | 41 / 50 |
| 100 | 2754 | 22 / 27 | 25 / 27 | 27 / 33 | 31 / 38 | 33 / 40 | 37 / 44 | 38 / 47 |

This table fully replaces the earlier "open question" placeholder. `[corrected — was open question]`

### Worked Example 2 (pages 87–95) — multi-beam dimensioning `[reference]`

A complete dimensioning of an irregular structure with multiple beam sections (V1=20×50, V3=20×70, V4=30×90), demonstrating:

- Per-area load calculation using influence areas (1 through 10).
- Adoption of L/400 to L/429 deflection limits depending on span.
- Tower height calculation: `H_torre = pé direito − espessura laje − ajuste topo/base`.
  - Example: pé direito 3.30 m, laje 10 cm, ajuste 0.224 m → H_torre = 2.99 m → 2 painéis (150 + 100) + 0.49 m de ajuste total (sapata + forcado).
- Crucially: **escora abertura = pé direito − espessura − 0.224 m (ajuste)**. The 0.224 m is the combined sapata + forcado adjustment value.
- BOM components for the example: VM130-310, VM130-410, VM80-255, etc., showing the modular nature of the BOM.

The example confirms the **height-based equipment sizing rule:** select panel combinations to reach within ±0.49 m of target height, with the residual taken up by sapata + forcado adjustment. `[new — calibration insight]`

---

## 8. Operational rules (pages 96–115) — completeness check

### Rule 1 (p.97) `[new]`
Escoramento must rest on firm base. Base preparation responsibility is the client's. *Project output rule:* mark "preparação da base sob responsabilidade do cliente" in the report.

### Rule 2 (p.98) `[new]`
Vertical shoring must be **aprumado** (plumb). Out-of-plumb significantly reduces equipment capacity. The Orguel diagrams show that even small deviations alter resistance "de forma significativa."

### Rule 3 (p.99) `[new]`
**Adjust top and base** of shoring equipment so no folgas (gaps) remain. Folgas alter load distribution.

### Rule 4 (p.100) `[new]`
**Apoiar guias nos suportes corretamente, cunhá-las** (wedge) to prevent lateral displacement and eccentric loads. Output rule: project specifies cunha placement.

### Rule 5 (p.101) `[new]`
**Madeiramento do fundo da forma das vigas** must be dimensioned per the project's espaçamentos between escoras/travessas. Direct dependency on the spacing decision.

### Rule 6 (p.102) `[new]`
**Cura mínima do concreto** (minimum cure time) for shoring removal is the **client's responsibility**. The system suggests but does not decide on desforma timing.

### Rule 7 (p.103) `[new]`
**Inspecionar equipamentos** before use. Damaged equipment must not be used.

### Rule 8 (p.104) `[new]`
**Não alterar o projeto sem comunicação prévia à Orguel.**

### Rule 9 (p.104) `[new]`
For montagem problems, consult Orguel for joint review of the layout.

### Rule 10 (p.104) `[new]`
**Travamento e amarração das fôrmas** is the client's responsibility (not Orguel's scope).

### Rule 11 (pages 105–106) `[corrected — major correction from earlier AGENTS.md]`

The previous AGENTS.md had this as "cantilever tip support 20-40 cm." That was wrong. The actual rule is about edge offset of barrotes from the slab boundary:

- **With lateral wall form ("forma lateral da parede"):** distance "x" from form edge to first barrote = **20 to 40 cm**.
- **Without lateral wall form (laje encostada na parede de concreto):** distance from concrete edge to first barrote = **5 cm**.

### Rule 12 (p.107) `[encoded]`
**Distância dos barrotes para alvenaria estrutural ≤ 5 cm.** Both guias and barrotes must be placed almost touching the masonry, so plywood doesn't end up in cantilever (pois não existe apoio, o compensado apenas encosta na alvenaria).

### Rule 13 (p.108) `[new]`
**Escoramento de lajes com suporte de forcado.** The forcado must be placed inside the slab area, supporting from below. Image-based illustration of correct placement.

### Rule 14 (p.109) `[encoded — already in AGENTS.md as the +25% rule]`
For continuous beams with 3 supports, the central reaction is `10/8 · q · L` (i.e., +25%) and the extremities are `3/8 · q · L`. **Forcados must NOT be placed on cantilever ends.** This is a separate rule from Rule 11 — Rule 11 is about edge offset of barrotes, Rule 14 is about forcado placement.

### Rule 15 (p.110) `[encoded]`
The correct allocation for a 3-support beam is **tower at the center** (because it absorbs the +25% naturally) **and telescópicas at the extremities** (which carry only 3/8 q·L). Reversing this is wrong because the +25% can exceed telescópica capacity.

### Rule 16 — Beam shoring strategy by location and size

This rule has **two distinct parts** that I had previously merged into one:

**Part A — External beams (vigas externas) (p.111):** `[encoded]`

External beams shored only with telescópicas + cruzetas must satisfy ALL of:
- largura ≤ 30 cm
- altura ≤ 60 cm
- comprimento ≤ 3.00 m

External beams with cantilever console: altura ≥ 70 cm.

Beyond these limits → towers or estaiamento required, OR external beams must be **estaiados** during montagem to prevent tipping.

**Part B — Internal beams (vigas internas) (pages 112–113):** `[new — major omission]`

Internal beams have a **different size envelope**:

| Comprimento | Largura | Altura | Strategy |
|---|---|---|---|
| ≤ 6.00 m | ≤ 40 cm | ≤ 70 cm | Escoras + cruzetas only |
| 6.00–10.00 m | ≤ 40 cm | ≤ 70 cm | Mixed (escoras + center tower) |
| > 10.00 m | > 40 cm | > 70 cm | Towers only |

Notes from p.113: when using mixed mode, "podemos mesclar torres com escoras apoiando as guias deste escoramento" — towers + escoras with guias supporting both.

This was a significant gap in the prior decision chain. New Decision Chain Question 5 should split into **5a (external beam)** and **5b (internal beam)** to capture both.

### Rule 17 (pages 114–115) `[encoded]`

**Cuidado nas emendas das chapas dos compensados.**
- Espaçamento dos barrotes deve ser múltiplo do comprimento da chapa (220 ou 244 mm).
- Emenda do compensado deve cair no **eixo do barrote**, never in mid-span.
- Transpasse (overlap) of barrotes shown as illustrative case for non-aligned plywood seams.

---

## 9. Special cases (pages 116–121) — informational `[reference]`

- p.116 — Escoramento para lajes nervuradas (overview)
- p.117 — Escoramento com Alu-14 (lighter aluminum option, when weight matters)
- p.118 — Escoramento para grandes alturas (>10 m, requires special design)
- p.119 — Escoramento aéreo para passagens (over openings/streets)
- p.120 — Escoramento com H20 para rampas (slopes)
- p.121 — Projetos especiais (custom solutions)

These pages are mostly reference photos but indicate to the system that **special-case routing** exists outside the standard decision chain. Projects with these characteristics should be flagged as "fora da decisão automática — requer revisão de Engenharia de Aplicação."

---

## 10. References & Engenharia de Aplicação (pages 122–123)

- p.122 — Fontes de consulta (NBRs cited)
- p.123 — Engenharia de Aplicação contact (the Orguel team that produces final projects)

---

## Master rule classification — tally

After full PDF review, the rules to encode in the system fall into these counts:

| Category | Encoded | New | Corrected | Open | Total |
|---|---|---|---|---|---|
| Geometric (GEOM) | 6 | 2 | 1 | 0 | 9 |
| Spacing (SPACE) | 3 | 2 | 1 | 0 | 6 |
| Structural (STRUCT) | 2 | 3 | 0 | 0 | 5 |
| Load (LOAD) | 4 | 2 | 1 | 0 | 7 |
| Equipment (EQUIP) | 3 | 4 | 1 | 1 | 9 |
| Decision (DECIDE) | 9 | 2 | 0 | 1 | 12 |
| Reescoramento (REESC) | 0 | 6 | 0 | 0 | 6 |
| Bracing (TRAV) | 1 | 5 | 0 | 0 | 6 |
| Project output (OUTPUT) | 0 | 4 | 0 | 0 | 4 |
| Output traceability (OUTPUT) | 1 | 0 | 0 | 0 | 1 |
| **Total** | **29** | **30** | **4** | **2** | **65** |

This is the new rule baseline for AGENTS.md and the migration plan.
