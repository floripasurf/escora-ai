# Brazilian NBR Standards and Construction Shoring Methods - Comprehensive Research

**Date:** 2026-03-28
**Purpose:** Technical reference for Escora.AI development

---

## Table of Contents

1. [NBR 15696:2009 - Formas e Escoramentos](#1-nbr-156962009)
2. [NBR 15696:2023 - Updated Version](#2-nbr-156962023-revision)
3. [NBR 6118 - Concrete Structure Design](#3-nbr-6118)
4. [NBR 7187 - Bridge Design](#4-nbr-7187)
5. [Lajes Nervuradas (Ribbed Slabs)](#5-lajes-nervuradas-ribbed-slabs)
6. [Lajes Cogumelo / Flat Slabs](#6-lajes-cogumelo--flat-slabs)
7. [Torres de Escoramento (Shoring Towers)](#7-torres-de-escoramento-shoring-towers)
8. [Infrastructure Works (OAE)](#8-infrastructure-works-oae)
9. [DWG/DXF File Formats in Construction](#9-dwgdxf-file-formats-in-construction)
10. [Machine Learning in Construction/Shoring](#10-machine-learning-in-constructionshoring)

---

## 1. NBR 15696:2009

**Full Title:** ABNT NBR 15696:2009 - Formas e escoramentos para estruturas de concreto - Projeto, dimensionamento e procedimentos executivos

**Effective Date:** May 15, 2009

### Scope

The standard establishes procedures and conditions for the execution of temporary structures (formwork and shoring) used in cast-in-place concrete construction. It defines minimum requirements for design, assembly, and dismantling of formwork and shoring systems.

### Key Definitions

- **Formas (Formwork):** Temporary structures that mold fresh concrete, resisting all actions from variable loads resulting from concrete placement pressures, until the concrete becomes self-supporting.
- **Escoramentos (Shoring):** Temporary structures capable of resisting and transmitting to support bases all actions from permanent and variable loads resulting from fresh concrete placement on horizontal and vertical formwork, until the concrete becomes self-supporting.

### Load Requirements

| Load Type | Minimum Value | Notes |
|-----------|--------------|-------|
| Sobrecarga de trabalho (working live load) | 2.0 kN/m2 | Minimum on horizontal formwork surfaces |
| Carga estatica total minima | 4.0 kN/m2 | Total static load cannot be less than this |
| Acao do vento (wind action) | 0.6 kN/m2 | Minimum; must also comply with NBR 6123 |
| Concreto fresco (fresh concrete) | 24 kN/m3 (typical) | Specific weight of fresh concrete |

### Annex D - Vertical Formwork Pressure (Normative)

The annex provides criteria for calculating fresh concrete pressure on vertical formwork, based on DIN 18218 but adapted for Brazilian conditions (25 C reference temperature). Key factors:

- **Pressure distribution types:** Variable pressure and constant pressure models
- **Factors affecting pressure:**
  - Vibration method and intensity
  - Fresh concrete temperature
  - Ambient temperature
  - Concrete additives (plasticizers, retarders)
  - Concrete type (self-compacting, lightweight, heavy)
- **Retarder factors:** When using set-retarding admixtures, pressure multiplication factors range from 1.15 to 2.15 depending on consistency class and retardation time

### Calculation Methods

The standard supports two calculation approaches:
1. **Metodo dos estados limites (Limit States Method)** - preferred
2. **Metodo das tensoes admissiveis (Allowable Stress Method)**

### Safety Factors (Coeficientes de majoracao)

Load combination factors are applied according to the limit state method, with partial safety factors for:
- Permanent loads (dead weight of formwork, fresh concrete)
- Variable loads (construction loads, wind, concrete pressure)
- Material resistance reduction factors

### Key Normative References

- ABNT NBR 6123 - Wind forces on buildings
- ABNT NBR 8681 - Actions and safety of structures
- ABNT NBR 14931 - Execution of concrete structures
- ABNT NBR 6118 - Design of concrete structures

### Sources

- [ABRASFE - NBR 15696 Overview](https://abrasfe.org.br/wp-content/uploads/2015/11/norma-nbr-15696.pdf)
- [EngSette - NBR 15696 Complete Guide](https://engsette.com.br/nbr15696/)
- [Portatil Andaimes - NBR 15696:2009 Full Text](https://portatilandaimes.com.br/wp-content/uploads/2017/08/nbr-15696_2009.pdf)

---

## 2. NBR 15696:2023 Revision

**New Title:** "Sistemas de Formas e de Escoramentos para Estrutura de Concreto" (Systems of Formwork and Shoring for Concrete Structures)

The standard underwent a significant revision process coordinated through ABNT consultation.

### Key Changes from 2009 to Revised Version

#### Name Change
The title was updated from "Formas e escoramentos para estruturas de concreto" to "Sistemas de formas e de escoramentos para estruturas de concreto," emphasizing the systemic nature of formwork and shoring.

#### Structural Changes
- **NBR 9532 absorbed:** The separate standard NBR 9532 was extinguished, with its content incorporated into the revised NBR 15696
- **New definitions added:** Including subitem 3.8 "Forma Perdida" (stay-in-place formwork / permanent formwork)
- **Text clarity improvements:** Following the model of ABNT NBR 14931 (also under revision)

#### Technical Modifications

1. **Annex D - Vertical Formwork Pressure (revised):**
   - Updated calculation criteria for concrete pressure on vertical forms
   - Discussion of actions in ultimate limit states (estados limites ultimos)
   - **Self-compacting concrete (concreto autoadensavel)** now included in pressure abacuses
   - Pressure charts adapted for modern concrete technologies

2. **Concrete categories:** New categories of concrete recognized
3. **Concrete placement temperature:** Updated requirements for temperature at time of placement
4. **Company authorization:** New requirements for companies to be authorized to operate in formwork and shoring

#### Modernization Goals
- Accommodate new materials and construction methods
- Align with technological innovations in the formwork and shoring sector
- Improve clarity and objectivity of the normative text
- Better integration with related standards (NBR 14931, NBR 6118)

### Sources

- [Versatil Andaimes - NBR 15696 Revision](https://www.versatilandaimes.com.br/blog/saiba-o-que-e-a-nbr-15696-e-a-sua-recente-revisao)
- [ALG Andaimes - NBR 15696 Revision Updates](https://algandaimes.com.br/fique-ligado-nbr-15696-revisada-quais-as-novidades-para-a-construcao-civil/)
- [Cimento Itambe - NBR 15696 Public Consultation](https://www.cimentoitambe.com.br/nbr-15696-passa-por-revisao-e-consulta-publica/)
- [ABECE - Revision Project in National Consultation](https://site.abece.com.br/projeto-de-revisao-da-nbr-15696-em-consulta-nacional/)

---

## 3. NBR 6118

**Full Title:** ABNT NBR 6118 - Projeto de estruturas de concreto - Procedimento (Design of concrete structures - Procedure)

**Current Version:** 2023 (updated from 2014)

### Overview

NBR 6118 is the primary Brazilian standard for design of reinforced and prestressed concrete structures. It defines criteria and methods ensuring safety, quality, and durability.

### Sections Relevant to Shoring / Formwork

#### Load Considerations
- **Permanent loads (acoes permanentes):** Dead weight of structural elements, including concrete self-weight
- **Variable loads (acoes variaveis):** Construction loads, occupancy loads, wind
- **Concrete self-weight:** Typically 25 kN/m3 for reinforced concrete (24 kN/m3 for plain concrete)

#### Slab Design Parameters Affecting Shoring

| Parameter | Value | Relevance to Shoring |
|-----------|-------|---------------------|
| Minimum slab thickness (solid) | 7 cm (floors), 10 cm (roofs with vehicle access) | Determines minimum concrete load |
| Ribbed slab mesa minimum | 1/15 of rib spacing, never < 3 cm | Affects formwork configuration |
| Cover requirements | 2.0-5.0 cm depending on exposure class | Affects total slab thickness |

#### Concrete Curing and Strength Development
- Defines when concrete becomes self-supporting (relevant to shoring removal timing)
- Specifies minimum strength for formwork removal (desforma)
- Typically: fck >= 15 MPa for vertical forms, structural adequacy check for horizontal shoring removal
- Progressive shoring removal (reescoramento) procedures

#### Punching Shear (Puncao) - Relevant to Flat Slabs
- Verification required at three control perimeters around columns
- Affects shoring density near column zones
- Critical for lajes cogumelo design

#### 2023 Update Highlights
- New coefficients and formulas
- Updated guidelines for safety and efficiency
- Better alignment with international standards

### Sources

- [Mapa da Obra - NBR 6118 Commentary](https://www.mapadaobra.com.br/inovacao/norma-comentada-abnt-nbr-6118/)
- [Sienge - NBR 6118 Guide](https://sienge.com.br/blog/nbr-6118/)
- [Target Normas - NBR 6118](https://www.normas.com.br/visualizar/abnt-nbr-nm/5211/abnt-nbr6118-projeto-de-estruturas-de-concreto)

---

## 4. NBR 7187

**Full Title:** ABNT NBR 7187:2021 - Projeto de pontes, viadutos e passarelas de concreto (Design of concrete bridges, viaducts, and pedestrian walkways)

**Current Version:** 2021 (revised from 2003)

### Overview

Establishes requirements for design, execution, and control of reinforced and prestressed concrete bridges, viaducts, and pedestrian walkways, including recovery and reinforcement of existing structures.

### 2021 Revision Highlights
- Text expanded from 11 to 72 pages
- Coordinated by CEE-231 (Special Study Committee on Concrete Bridges)
- Incorporated topics previously only superficially covered in NBR 6118
- More detailed requirements for shoring design documentation

### Shoring Requirements for Bridges

The standard requires that basic project documents include:
- **Drawings of shoring (desenhos de escoramento):** Properly dimensioned according to the proposed concreting plan
- **Execution sequences:** Including concreting order and shoring removal schedule
- **Predicted deformations:** Camber and deflection calculations for the shoring system
- **Load path:** Clear definition of how loads transfer from deck to foundations through shoring

### Related Standards for Infrastructure Shoring
- **NBR 10839:1989** - Execution of special works of art in reinforced and prestressed concrete
- **NBR 7188** - Highway and pedestrian bridge loads (updated 2024)
- **NBR 6123** - Wind forces

### Key Differences from Building Shoring
- Much higher loads (bridge decks can be 20-40 cm thick with heavy reinforcement)
- Longer spans requiring engineered shoring solutions
- Environmental factors (water, terrain constraints)
- Strict deformation control requirements

### Sources

- [Mapa da Obra - NBR 7187 Commentary](https://www.mapadaobra.com.br/inovacao/abnt-nbr-7187-comentada/)
- [Master em Modelagem - Bridge Design Guide](https://www.masteremmodelagem.com.br/post/pontes-de-concreto-guia-de-projeto-segundo-as-normas-nbr-7187-2021-e-nbr-7188-2024)
- [DER/PR - Manual OAE Tomo V 2023](https://www.der.pr.gov.br/sites/der/arquivos_restritos/files/documento/2023-10/MESR_TOMO_V_OAE.pdf)

---

## 5. Lajes Nervuradas (Ribbed Slabs)

### Definition and Types

Ribbed slabs (lajes nervuradas) consist of a thin top slab (mesa/flange) supported by a grid of ribs (nervuras), creating voids between the ribs to reduce concrete consumption and self-weight. Types include:

- **Laje nervurada moldada in loco:** Cast with reusable plastic or foam molds
- **Laje trelicada (pre-fabricated ribbed):** Uses pre-fabricated joists with infill blocks
- **Laje nervurada bidirecional:** Ribs in two directions (waffle slab)
- **Laje nervurada unidirecional:** Ribs in one direction only

### Typical Dimensions

| Parameter | Typical Range | NBR 6118 Requirement |
|-----------|--------------|---------------------|
| Rib spacing (between axes) | 40-90 cm | Mesa thickness >= 1/15 of spacing |
| Rib width (base) | 6-16 cm | Minimum 5 cm per NBR 6118 |
| Mesa (flange) thickness | 3-7 cm | Minimum 3 cm, >= 1/15 rib spacing |
| Total slab height | 16-45 cm | Per structural design |
| Mold dimensions | 40x40, 50x50, 60x60, 80x80 cm | Varies by manufacturer |

### Shoring Differences from Solid Slabs

1. **Shore placement rules:**
   - Primary shores (longarinas) are placed along the rib lines, not between ribs
   - The formwork system sits on secondary beams (transversinas) which span between primary shoring lines
   - Plastic/foam molds are placed on guides that rest on the secondary beams
   - Re-shoring supports (suportes de reescoramento) are positioned under the rib intersections

2. **Three-stage assembly process:**
   - Stage 1: Conventional shoring (escoras + longarinas) is assembled
   - Stage 2: Plastic mold guides and re-shoring supports are placed on secondary profiles
   - Stage 3: Plastic molds are placed on their guides

3. **Shore removal:**
   - After concrete cures, shoring is removed but maintained approximately every 1.5 m2 (varying by project)
   - Re-shoring (reescoramento) is more critical in ribbed slabs due to concentrated loads on ribs

4. **Load considerations:**
   - Ribbed slabs are lighter than solid slabs (less concrete), so total fresh concrete load is lower
   - However, loads are concentrated on rib lines, not distributed uniformly
   - Shoring must account for the weight of molds/forms in addition to concrete

### Design Implications for Escora.AI

- Element detection must identify rib grid patterns (spacing, direction)
- Shore placement algorithm should align with rib positions
- Wider molds (60-90 cm rib spacing) are used for larger spans
- Rib width at base (6-16 cm) affects shore head placement

### Sources

- [Versatil - Shoring for Ribbed Slabs](https://www.versatilandaimes.com.br/blog/como-funciona-o-sistema-de-escoramento-para-lajes-nervuradas)
- [Mapa da Obra - Ribbed Slab Execution](https://www.mapadaobra.com.br/inovacao/laje-nervurada/)
- [UNICAMP - Ribbed Slabs Technical](https://www.fec.unicamp.br/~almeida/ec802/Laje%20Nervurada/Lajes_nervuradas.pdf)
- [CarLuc - Ribbed Slab Types](https://carluc.com.br/projeto-estrutural/laje-nervurada/)
- [Revista FT - Comparative Study Traditional vs Alternative Shoring](http://revistaft.com.br/estudo-comparativo-de-modelo-tradicional-e-alternativo-de-escoramento-para-lajes-macicas-e-nervuradas/)

---

## 6. Lajes Cogumelo / Flat Slabs

### Definition

Flat slabs (lajes cogumelo/lajes planas) are slabs supported directly on columns without beams. What characterizes a "laje cogumelo" specifically is the presence of a capital (capitel) -- a thickened region around the column where the slab is solid and enlarged.

- **Laje cogumelo:** Flat slab WITH capitals at column connections
- **Laje plana (lisa):** Flat slab WITHOUT capitals (uniform thickness)

### Punching Shear (Puncao)

Punching shear is the critical failure mode for flat slabs -- a localized shear failure at the slab-column connection where concentrated forces "punch" through the slab.

#### NBR 6118 Verification Requirements

Verification must be performed at three control perimeters:

| Perimeter | Location | Check |
|-----------|----------|-------|
| u0 | Around the column face | Compression resistance of the diagonal strut |
| u1 | At distance 2d from column face | Diagonal tension resistance (with/without shear reinforcement) |
| uout | Outside shear reinforcement zone | Diagonal tension resistance without reinforcement |

Where d = effective depth of the slab.

### Capital (Capitel) Zones

- Capitals extend the effective support area, reducing punching shear stresses
- They go beyond the normal column dimensions to improve load distribution
- Typical capital dimensions: extend 1.5h to 3h beyond column face (h = slab thickness)
- Capitals can be drop panels (engrossamento) or mushroom-shaped protrusions

### Shoring Specifics for Flat Slabs

1. **Higher loads near pillars:**
   - Flat slabs concentrate reactions at column points
   - Shoring density must increase near column zones
   - Capital zones require additional formwork support due to increased thickness

2. **Uniform slab shoring (away from capitals):**
   - Regular grid of shores with spacing determined by slab thickness and load
   - Simpler than beam-slab systems (no beam formwork needed)
   - Higher productivity in shoring assembly (only horizontal formwork)

3. **Advantages for shoring:**
   - No beam forms means faster setup
   - Regular, predictable shoring grid patterns
   - Easier to standardize shore spacing

4. **Challenges:**
   - Capital formwork requires special attention (variable thickness zones)
   - Punching shear reinforcement zones may affect shoring access
   - Post-tensioning tendons (common in flat slabs) add complexity

### Design Implications for Escora.AI

- Must detect column positions and capital extents from structural drawings
- Higher shore density zones around columns need automatic identification
- Uniform grid spacing calculation for flat slab regions
- Capital zones need separate shoring treatment with potentially heavier equipment

### Sources

- [Engenheiro Doutor Pro - Flat Slab Guide](https://engenheirodoutorpro.com.br/laje-cogumelo/)
- [SciELO - Experimental and Numerical Analysis](https://www.scielo.br/j/riem/a/rPSTjjfD8GcfD7X4TDpLqpf/)
- [Brazilian Journal of Development - Capital Efficiency Study](https://ojs.brazilianjournals.com.br/ojs/index.php/BRJD/article/view/69415)
- [AltoQi - Punching Shear Design](https://suporte.altoqi.com.br/hc/pt-br/articles/360038256053)

---

## 7. Torres de Escoramento (Shoring Towers)

### Individual Props vs. Shoring Towers

#### Individual Metal Props (Escoras Metalicas)

| Characteristic | Value |
|---------------|-------|
| Maximum load capacity | Up to 9 tf (individual prop) |
| Typical height range | 1.5 - 4.5 m |
| Maximum recommended height | ~3 m (standard), up to 4.5 m (reinforced) |
| Advantages | Light, fast assembly, adaptable |
| Limitations | Buckling risk at height, lower load capacity |
| Best for | Standard floor slabs, low-to-medium loads |

#### When to Use Towers vs. Individual Props

| Criterion | Individual Props | Shoring Towers |
|-----------|-----------------|----------------|
| Height | Up to ~3-4.5 m | Above 4.5 m, up to 20+ m |
| Load | Light to medium slabs/beams | Heavy beams, bridges, large spans |
| Stability | Requires cross-bracing | Inherently stable (rigid frame) |
| Assembly speed | Fast for low heights | Faster for high/heavy applications |
| Cost | Lower for simple jobs | More economical for heavy/tall work |

**Rule of thumb:** When pe-direito (clear height) exceeds 4.5 m, or when loads exceed individual prop capacity, towers should be used.

### Tower Types and Systems

#### 1. SH Systems (Brazilian Manufacturer)

**LTT Load Tower:**
- Modular system with 1.5 m sections
- Quick-lock connections (no bolts required)
- Capacity: up to 11 tf per tower (FLEX line)
- Compliant with NBR 15696 and NR-18

**LTT Extra Load Tower:**
- Heavy-duty version for higher loads
- Used for bridge decks and heavy structural elements
- Enhanced load capacity per leg

#### 2. ETEM System (ROHR)

- Panel-based tower system
- Used for heavy shoring of beams, slabs, and bridges
- Modular frame sections

#### 3. Cuplock System

- Originally British system, widely used globally
- Cup-and-blade connection at each node
- Very fast assembly (hammer-lock connections)
- Versatile for both shoring and scaffolding
- Common in industrial and infrastructure projects

#### 4. Ringer / Ring System

- Ring-lock rosette connection system
- 8 connection points per rosette node
- Very high load capacity
- Used for complex geometries and heavy loads

#### 5. PERI Systems

**PERI UP Flex:**
- Modular shoring tower
- Capacity: 40 kN per leg
- Adaptable to various geometries

**VARIOKIT VST (Heavy-Duty):**
- For bridge construction and infrastructure
- Very high load capacity
- Adjustable to complex cross-sections

#### 6. ULMA MK Tower

- Heavy-duty tower system
- High load capacity per vertical member
- Used for bridges, viaducts, and heavy structures

### General Tower Specifications

| Parameter | Typical Range |
|-----------|--------------|
| Module height | 1.0 - 2.0 m (typically 1.5 m) |
| Base dimensions | 1.0 x 1.0 m to 1.5 x 1.5 m |
| Load per leg (light duty) | 4-6 tf |
| Load per leg (medium duty) | 6-10 tf |
| Load per tower (heavy duty) | 10-40+ tf |
| Maximum height (standard) | 10-20 m (depends on system) |
| Heights above 5 m capacity | ~6.5 tf per vertical member |
| Wind bracing | Required per NBR 15696 |

### Configuration Rules

1. **Base plates/screw jacks:** Always required; must distribute load to foundation/ground
2. **Cross-bracing (diagonais):** Required on all faces for lateral stability
3. **Horizontal ledgers:** At each module level
4. **Base support:** Must be on firm, level ground or engineered foundations
5. **Height-to-base ratio:** Maximum unbraced H/B ratio per manufacturer specifications
6. **Adjacent tower connections:** Towers in groups must be interconnected for global stability
7. **Top adjustment:** U-heads or adjustable forkheads for beam support

### Sources

- [CTP Locacoes - Tower Overview](https://ctplocacoes.com.br/produto/torre-de-escoramento/)
- [ROHR - ETEM Tower System](https://rohr.com.br/produto/escoramento-sistema-de-torre-etem/)
- [SH - LTT Extra Load Tower](https://sh.com.br/en/equipamentos/ltt-extra-load-tower/)
- [American Andaimes - When to Choose Towers](https://www.americandaimes.com.br/quando-escolher-o-escoramento-com-torres/)
- [AECweb - Metal Towers for Tall Structures](https://www.aecweb.com.br/revista/materias/torres-metalicas-sao-opcao-para-o-escoramento-de-estruturas-altas/17679)
- [PERI - VST Heavy Duty Tower](https://www.peri.pt/produtos/vst-torre-escoramento-pesado.html)
- [ULMA - MK Heavy Duty Tower](https://www.ulmaconstruction.com/en-us/shoring/concrete-shoring/heavy-duty-towers-mk)

---

## 8. Infrastructure Works (OAE)

### What are OAE?

**Obras de Arte Especiais (OAE)** are special engineering structures including:
- **Pontes** (bridges) - over water
- **Viadutos** (viaducts) - over land/roads
- **Passarelas** (pedestrian walkways)
- **Pontilhoes** (small bridges/culverts)

### Bridge Structural Components Requiring Shoring

#### Tabuleiro (Bridge Deck)
- The deck slab that carries traffic loads
- Typically 20-40 cm thick for road bridges
- Requires continuous shoring over the full span
- Shoring must account for deck weight + formwork + construction loads

#### Longarina (Girder/Main Beam)
- Primary longitudinal beams supporting the deck
- Can be very deep (1-3 m height) and heavily reinforced
- Requires heavy shoring (towers or engineered falsework)
- Often post-tensioned, requiring special anchorage accommodations

#### Transversina (Cross-beam/Diaphragm)
- Transverse beams connecting longarinas
- Located at support points and intermediate positions
- Shoring hangs from or is supported by longarina formwork
- Smaller but still requires engineered support

#### Encontro / Abutment
- End supports where the bridge meets the approach embankment
- Complex 3D formwork with variable geometry
- Vertical formwork for walls, horizontal for seat/bearing shelf
- Backwall, wingwalls, and seat all require separate forms

### Construction Methods for Bridge Shoring

#### 1. Cimbramento Fixo (Fixed Falsework)
- Traditional method: shoring towers/props supported on ground
- **Continuous falsework:** Posts/props only
- **Mixed falsework:** Towers + beams/trusses spanning between towers
- Best for: Low bridges over accessible ground, moderate spans
- Height: Typically up to 10-15 m

#### 2. Cimbramento Movel (Movable Falsework / Travelling Forms)
- **Superior (overhead):** Operates on top of completed deck sections
- **Inferior (underslung):** Operates under the deck
- Self-launching system that advances span by span
- Best for: Long viaducts with many repetitive spans
- Spans: Typically 30-60 m

#### 3. Balanco Sucessivo (Cantilever Construction)
- Segmental construction extending outward from piers
- Form travellers attached to completed deck in cantilever
- No ground-supported shoring needed
- Best for: Long spans (30-450 m), over obstacles (rivers, valleys)
- Segments (aduelas): Typically 3-5 m long

#### 4. Lancamento por Incrementos (Incremental Launching)
- Bridge deck cast behind abutment and pushed forward
- Launching nose extends beyond pier to reduce cantilever moments
- Temporary shoring only at casting area

### How Bridge Shoring Differs from Building Shoring

| Aspect | Building Shoring | Bridge Shoring |
|--------|-----------------|----------------|
| Heights | 3-5 m typical | 5-30+ m common |
| Loads | 5-15 kN/m2 typical | 15-50+ kN/m2 |
| Spans | 5-10 m typical | 15-60+ m |
| Wind exposure | Partially sheltered | Fully exposed |
| Foundation | Existing structure/ground | May need engineered pads |
| Deformation control | Moderate | Very strict (camber) |
| Safety margins | Standard NBR 15696 | NBR 15696 + NBR 7187 |
| Design requirement | Often standardized | Always project-specific |
| Dismantling | Straightforward | Complex sequence |

### Normative Framework for OAE Shoring

- **NBR 7187:2021** - Bridge design (includes shoring documentation requirements)
- **NBR 15696** - Formwork and shoring (general standard)
- **NBR 10839:1989** - Execution of special works of art
- **NBR 7188:2024** - Bridge loads
- **DER/PR Manual OAE Tomo V** - State-level execution manual

### Sources

- [DER/PR - OAE Execution Manual Tomo V 2023](https://www.der.pr.gov.br/sites/der/arquivos_restritos/files/documento/2023-10/MESR_TOMO_V_OAE.pdf)
- [CTC Infra - OAE Overview](https://ctcinfra.com.br/obras-de-arte-especiais/)
- [ULMA - Bridge Construction Methods](https://www.ulmaconstruction.com.br/pt-br/ulma/blog/metodos-construtivos-pontes-e-viadutos)
- [ROHR - Cantilever Construction](https://rohr.com.br/produto/balanco-sucessivo/)
- [SH - Cantilever Method](https://sh.com.br/pt/blog/o-que-e-o-metodo-balanco-sucessivo/)
- [DNIT - OAE Project Instructions](https://www.gov.br/dnit/pt-br/ferrovias/instrucoes-e-procedimentos/instrucoes-de-servicos-ferroviarios/isf-216-projeto-de-oae.pdf)

---

## 9. DWG/DXF File Formats in Construction

### CAD Software Used in Brazil

#### Structural Design Software

| Software | Origin | Primary Use | Export Formats |
|----------|--------|-------------|----------------|
| **TQS** | Brazil | RC structural design, dimensioning, detailing | DWG, DXF, IFC, PDF |
| **Eberick** (AltoQi) | Brazil | RC structural design, masonry, mixed structures | DWG, DXF, IFC, STL, OBJ |
| **CYPECAD** | Spain | RC structural design (supports Brazilian NBR 6118) | DWG, DXF, IFC |
| **AutoCAD** | USA | General drafting, 2D/3D drawing | DWG (native), DXF |
| **Revit** | USA | BIM modeling (architectural + structural) | RVT (native), IFC, DWG |

#### How Each Software Exports Structural Forms (Formas)

**TQS:**
- Generates "planta de formas" (formwork plan) automatically from the structural model
- Exports to DWG/DXF with structured layers
- BIM export via IFC for Revit interoperability
- Layers typically follow TQS internal naming (e.g., TQS-FORMA, TQS-PILAR, TQS-VIGA)

**Eberick:**
- Full 3D structural visualization
- Exports DWG, DXF, IFC, STL, OBJ
- Generates detailing drawings with standardized layers
- Formwork plans (formas) auto-generated from the model

**CYPECAD:**
- Automatic job introduction from DXF/DWG/IFC input files
- Exports results to DWG/DXF
- Module for importing architectural floor plans as DXF background
- Generates structural drawings with element-based layers

### Layer Naming Conventions

#### Common Brazilian Structural Drawing Layers

While there is no single mandatory standard, common conventions include:

| Layer Pattern | Content |
|--------------|---------|
| FORMA / FORMAS | Formwork plan outlines |
| PILAR / PIL | Column outlines and dimensions |
| VIGA / VIG | Beam outlines and dimensions |
| LAJE / LAJ | Slab outlines and designations |
| COTA / DIM | Dimensions |
| TEXTO / TXT | Text annotations |
| EIXO / AXIS | Grid lines / axes |
| HATCH | Fill patterns |
| ARMADURA / ARM | Reinforcement |
| ESCADA | Stairs |
| FUNDACAO | Foundation elements |

#### AsBEA Convention (Brazilian reference)
The AsBEA (Associacao Brasileira dos Escritorios de Arquitetura) provides naming guidelines that some structural offices follow, using discipline prefixes:
- **EST-** for structural layers (e.g., EST-PILAR, EST-VIGA)
- **ARQ-** for architectural layers

### DXF Format Technical Details

- **DXF (Drawing Interchange Format):** ASCII or binary text format developed by Autodesk (1982)
- Contains: entities (LINE, ARC, CIRCLE, POLYLINE, TEXT, INSERT/BLOCK), layers, blocks, dimension styles
- Key sections: HEADER, TABLES, BLOCKS, ENTITIES
- **Structural drawings in DXF** typically contain:
  - LWPOLYLINE/POLYLINE for element outlines
  - TEXT/MTEXT for element names and dimensions
  - INSERT for block references (column symbols, etc.)
  - DIMENSION for measurements
  - HATCH for fill patterns

### IFC as Alternative Input Format

**IFC (Industry Foundation Classes):**
- Open standard developed by buildingSMART, standardized as ISO 16739
- Rich semantic model: elements are typed (IfcColumn, IfcBeam, IfcSlab, etc.)
- Contains geometry + properties + relationships
- Current versions: IFC 2x3 (most widely supported), IFC 4.0, IFC 4.3

**Advantages over DXF for Escora.AI:**
- Elements are already classified (no need for ML-based detection)
- Material properties included
- Load information can be embedded
- Spatial relationships defined

**Limitations:**
- Not all Brazilian firms use BIM/IFC workflows yet
- IFC export quality varies between software
- Interpretation can be complex due to the generic nature of the format
- TQS and Eberick IFC export may have limitations in some versions

### Design Implications for Escora.AI

- **Primary input:** DXF/DWG files (most common in Brazilian practice)
- **Secondary input:** IFC files (growing adoption, richer data)
- **Detection strategy:**
  - Layer-based: use layer names to identify element types
  - Geometry-based: use polyline patterns to detect columns, beams, slabs
  - Text-based: parse dimension text and element labels
  - Block-based: identify standard column/element symbols
- **Software-specific parsers:** May need separate logic for TQS vs. Eberick vs. CYPECAD exports

### Sources

- [Guia da Engenharia - Engineering Software Overview](https://www.guiadaengenharia.com/softwares-de-engenharia/)
- [CYPECAD - DXF/DWG/IFC Import](http://cypecad.en.cype.com/bim_ifc_dxf_dwg_cypecad.htm)
- [SourceCAD - Layer Naming Standards](https://sourcecad.com/layer-naming-standards-cad-drawing/)
- [Wikipedia - AutoCAD DXF](https://en.wikipedia.org/wiki/AutoCAD_DXF)
- [TQS - BIM Documentation](https://docs.tqs.com.br/Docs/Details?id=154107982&language=pt-BR)
- [ResearchGate - IFC Interoperability Study](https://www.researchgate.net/publication/315028083_Interoperabilidade_entre_Plataforma_BIM_e_Ferramentas_de_Analise_Estrutural_utilizando_Industry_Foundation_Classes_IFC)

---

## 10. Machine Learning in Construction/Shoring

### Current State of AI in Construction

AI adoption in construction has accelerated significantly:
- **2023:** 34% of general contractors using/evaluating AI tools
- **2025:** 67% of general contractors using/evaluating AI tools
- **Market size:** $3.99 billion (2024) projected to $11.85 billion by 2029
- **ROI:** 150-400% within first 18 months of implementation
- **Time savings:** 30-70% on repetitive tasks (quantity takeoffs, design iterations)

### Existing Tools and Platforms

#### Construction Drawing AI Tools

| Tool | Capability | Accuracy |
|------|-----------|----------|
| **Togal.AI** | Automated quantity takeoff from drawings | >97% element recognition |
| **Kreo** | Blueprint reading, MEP takeoff, AI-powered measurement | High accuracy on standard drawings |
| **Infrrd** | Document AI for construction drawings | Specialized in extraction |
| **Autodesk Construction Cloud** | AI-assisted design review and clash detection | Integrated with Revit/BIM |

#### Key Capabilities
- Automatic detection of walls, doors, windows, rooms, dimensions, materials
- Symbol detection and classification in technical drawings
- OCR for dimension text and annotations
- Quantity takeoff automation

### Computer Vision for Drawing Interpretation

#### Deep Learning Models Used

| Model | Application | Performance |
|-------|------------|-------------|
| **YOLO (You Only Look Once)** | Real-time symbol detection | mAP ~79% on construction drawings |
| **Faster R-CNN** | Object detection in engineering diagrams | mAP ~83% on construction drawings |
| **SSD (Single Shot Detector)** | Fast element detection | Good for simpler drawings |
| **R-FCN** | Region-based detection | Strong on structured drawings |

#### Approaches for DXF/Drawing Interpretation

1. **Vector-based analysis (DXF/SVG):**
   - Direct parsing of geometric entities
   - No OCR needed for vectorized formats
   - Extract text and line information programmatically
   - Layer-based classification
   - **Most relevant for Escora.AI**

2. **Raster-based analysis (PDF/scanned drawings):**
   - Computer vision + OCR pipeline
   - Symbol detection using object detection models
   - Text recognition using OCR (Tesseract, commercial APIs)
   - More complex but handles non-digital sources

3. **Hybrid approaches:**
   - Combine vector parsing with ML for ambiguous elements
   - Use trained models to classify detected geometric patterns
   - Context-aware interpretation using graph neural networks

### Research Areas Relevant to Shoring

#### Structural Element Detection
- **Column detection:** Identify rectangular/circular column outlines in formwork plans
- **Beam detection:** Identify linear elements with width annotations
- **Slab boundary detection:** Identify enclosed regions representing slab panels
- **Opening detection:** Identify holes, shafts, stairwells

#### Symbol Recognition
- Section markers, level indicators, grid lines
- Dimension annotations and element labels
- Reinforcement symbols and notation

#### How to Improve Element Detection for Escora.AI

1. **Training data:**
   - Collect annotated Brazilian structural drawings (TQS, Eberick output)
   - Create labeled datasets of columns, beams, slabs, openings
   - Include drawings from different software with varying layer conventions

2. **Feature engineering:**
   - Use layer names as strong features (when available)
   - Geometric heuristics: columns are small rectangles, beams are long narrow rectangles
   - Text proximity: element labels near geometric entities
   - Block/symbol matching for standard elements

3. **Model architecture:**
   - For DXF vector input: Graph Neural Networks (GNN) treating entities as graph nodes
   - For raster input: YOLO or Faster R-CNN with transfer learning
   - For hybrid: Ensemble of vector parser + CNN classifier

4. **Post-processing:**
   - Structural consistency checks (columns must connect to foundations, beams span between columns)
   - Dimensional validation against typical ranges
   - Cross-reference with text annotations

### Specific to Shoring Applications

No existing commercial tool specifically targets automated shoring design from structural drawings. This represents a significant market opportunity. The closest analogies are:

- **Quantity takeoff tools** (Togal.AI, Kreo) - detect elements but don't design shoring
- **Structural analysis software** (TQS, Eberick) - design structures but don't generate shoring plans
- **Shoring manufacturer tools** - calculate individual component capacities but don't do full layout design

**Escora.AI's unique value proposition:** Bridging the gap between structural drawing interpretation and automated shoring design, combining:
- DXF/IFC input parsing
- Structural element detection
- Shoring layout optimization per NBR 15696
- Equipment selection (props vs. towers)
- Output as DXF shoring plan

### Sources

- [Frontiers - OCR on Engineering Drawings](https://www.frontiersin.org/journals/manufacturing-technology/articles/10.3389/fmtec.2023.1154132/full)
- [MDPI - Computer Vision for Structural Analysis](https://www.mdpi.com/1424-8220/24/9/2923)
- [ScienceDirect - Deep Learning for Symbol Detection](https://www.sciencedirect.com/science/article/abs/pii/S0893608020301957)
- [Springer - AI-Powered Symbol Detection in Construction Diagrams](https://link.springer.com/article/10.1007/s10032-024-00492-9)
- [BusinessWareTech - AI for Construction Drawings](https://www.businesswaretech.com/blog/ai-for-construction-drawings-trends-capabilities-and-case-studies)
- [Civinnovate - Top AI Tools for Civil Engineering 2025](https://civinnovate.com/2025/04/08/ai-tools-civil-engineering-2025/)
- [Autodesk - AI Construction Trends 2025](https://www.autodesk.com/blogs/construction/top-2025-ai-construction-trends-according-to-the-experts/)
- [Articulate - 2026 Construction AI Report](https://usearticulate.com/press-release/2026-construction-ai-drawing-analysis-report)

---

## Summary of Key Findings for Escora.AI Development

### Standards Compliance Checklist

| Standard | Key Requirement for Escora.AI |
|----------|------------------------------|
| NBR 15696 | Minimum 2.0 kN/m2 working load, 0.6 kN/m2 wind, limit states design |
| NBR 6118 | Concrete self-weight 25 kN/m3, slab minimum thickness, punching shear |
| NBR 7187 | Bridge shoring documentation, deformation control |
| NR-18 | Construction safety requirements (items 18.12, 18.28) |

### Element Detection Priority Matrix

| Element Type | Detection Difficulty | Shoring Impact |
|-------------|---------------------|----------------|
| Columns (pilares) | Low (distinct rectangles) | High (shore-free zones, reference grid) |
| Beams (vigas) | Medium (linear, need width) | High (concentrated loads, shore lines) |
| Solid slabs | Low (enclosed regions) | Medium (uniform shoring) |
| Ribbed slabs | Medium (rib pattern detection) | High (shore alignment to ribs) |
| Flat slabs | Medium (identify capitel zones) | High (variable density near columns) |
| Openings | Medium (interior voids) | Medium (exclusion zones) |
| Stairs | High (complex geometry) | Low (usually separate) |

### Equipment Selection Logic

```
IF height <= 3.0 m AND load <= standard slab:
    USE individual props (escoras metalicas)
ELIF height <= 4.5 m AND load <= medium:
    USE reinforced props or light towers
ELIF height > 4.5 m OR load > medium:
    USE shoring towers (SH LTT, ETEM, Cuplock, etc.)
IF bridge/infrastructure:
    USE heavy-duty towers or specialized falsework
    CONSIDER cantilever/travelling form methods
```
