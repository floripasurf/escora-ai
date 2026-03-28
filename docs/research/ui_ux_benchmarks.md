# Escora.AI - UI/UX Benchmarks & Competitive Research

**Date:** 2026-03-28
**Purpose:** Research existing shoring/formwork software tools and best practices to inform the Escora.AI interface design.

---

## 1. Existing Software Tools Analysis

### 1.1 Doka - Tipos 9

| Attribute | Details |
|-----------|---------|
| **Type** | Desktop Windows application |
| **Target** | Foremen, operations scheduling, formwork engineers |
| **Pricing** | Licensed (paid, for Doka customers) |
| **Website** | [tipos.doka.com](https://www.doka.com/us/solutions/services/dfds/dfds-planning-software/tipos-software-formwork-planning) |

**Inputs:**
- Ground plans (imported from other programs)
- Structure geometry via 'Schal-Igel' wizard
- Equipment inventory/stock levels
- Photos, sections, and texts from other programs

**Outputs:**
- Formwork plans (2D layouts)
- Material quantity lists (BOM)
- Equipment logistics planning
- Solutions constrained by available stock

**Interface/Workflow:**
- Windows-native UI using construction/formwork terminology
- Interactive planning with ability to modify at any stage
- Wizard-based input for structure definition
- Multi-document interface (several plans open simultaneously)
- Continuous undo functionality
- Auto-planning with manual override capability

**Key Insight for Escora.AI:** Tipos constrains solutions to available equipment -- a critical feature for locadoras. The wizard-based input flow is user-friendly for non-CAD engineers.

---

### 1.2 Doka - Easy Formwork Planner (EFP) 2.0

| Attribute | Details |
|-----------|---------|
| **Type** | Web app + Mobile app (iOS/Android) |
| **Target** | Site foremen, small contractors |
| **Pricing** | Free (drives Doka equipment sales) |
| **Website** | [efp.doka.com](https://efp.doka.com/) |

**Inputs:**
- Building data (dimensions, geometry)
- Floor plan drawing (drawn in-app)
- Custom stock lists

**Outputs:**
- Automatically generated formwork solution
- Material calculation / piece list
- 3D visualization
- CSV export for purchasing
- Direct ordering via Doka Online Shop

**Interface/Workflow:**
1. Enter planning data (building dimensions)
2. Draw floor plan in simplified editor
3. Algorithm calculates optimal formwork solution
4. Review 3D visualization
5. Match piece list against existing stock
6. Order missing materials directly

**Key Insight for Escora.AI:** This is the closest model to what Escora.AI should aspire to -- simple input, intelligent calculation, visual output, and direct connection to equipment ordering. The stock-matching feature is essential for locadoras.

---

### 1.3 PERI CAD 24

| Attribute | Details |
|-----------|---------|
| **Type** | Desktop (AutoCAD Architecture plugin) |
| **Target** | Professional CAD engineers, design departments |
| **Pricing** | Licensed (paid, requires AutoCAD) |
| **Website** | [peri.com](https://www.peri-usa.com/products/peri-cad-software.html) |

**Inputs:**
- AutoCAD Architecture models
- Scaffmax JSON imports
- Structure geometry (walls, slabs, columns)

**Outputs:**
- Detailed 3D formwork plans
- Professional plan drawings
- Quantity calculations
- Construction sequence planning
- Cost optimization data

**Supported Systems:** TRIO 270/330, DOMINO, MAXIMO, PERI UP scaffolding, SKYDECK slab formwork

**Key Insight for Escora.AI:** PERI CAD targets experienced engineers. Too complex for Escora.AI's audience but demonstrates the importance of supporting multiple formwork systems in one tool.

---

### 1.4 PERI Formwork Load Calculator

| Attribute | Details |
|-----------|---------|
| **Type** | Web app + Mobile app (Android) |
| **Target** | Site engineers, concrete specialists |
| **Pricing** | Free |
| **Website** | [apps.peri.com/SLR](https://apps.peri.com/SLR/index.php?lang=en) |

**Inputs:**
- Wall formwork system selection (MAXIMO, TRIO, DOMINO)
- Anchor system (DW15, DW20, MX15, MX18)
- Pouring height
- Concrete type and temperature
- Deformation requirements

**Outputs:**
- Maximum lateral pressure (CCP max)
- Maximum pouring rate
- Graphical representation of results
- PDF report for documentation/printing/email

**Standards:** DIN 18218:2010-01, CIRIA Report 108:1985, ACI 347R-14

**Key Insight for Escora.AI:** Simple, focused calculator with PDF output. Good model for individual calculation modules within a larger platform. Standards-based calculations build engineer trust.

---

### 1.5 PASCHAL-Plan light (PPL) 12.0

| Attribute | Details |
|-----------|---------|
| **Type** | Desktop application |
| **Target** | Building contractors, planning engineers |
| **Pricing** | Licensed (paid) |
| **Website** | [paschal.de](https://www.paschal.de/english/products/software/index_software.php) |

**Inputs:**
- BIM data via IFC interface
- DXF/DWG floor plans
- Warehouse inventory data

**Outputs:**
- Formwork plans in 2D and 3D (multiple LODs)
- Material lists (up to 50,000 elements)
- IFC4 export for BIM workflow
- DXF/DWG export
- AR visualization (via companion app)

**Key Features:**
- Fully automatic formwork planning from BIM data
- Warehouse management integration
- Smart plausibility controls (accessories snap to valid attachment points)
- Augmented Reality companion app for field visualization

**Key Insight for Escora.AI:** The warehouse management + planning integration is exactly what locadoras need. AR visualization is a future differentiator. Smart plausibility controls prevent engineering errors.

---

### 1.6 ULMA Studio for Revit

| Attribute | Details |
|-----------|---------|
| **Type** | Revit Add-in |
| **Target** | BIM engineers, architects |
| **Pricing** | Free |
| **Website** | [ulmaconstruction.com](https://www.ulmaconstruction.com/en/ulma/news/ulma-studio-for-revit-available) |

**Inputs:**
- Revit 3D models
- ULMA component libraries (ORMA, LGW, LGR, CC-4, ENKOFLEX, MEGALITE, MEGAFORM)

**Outputs:**
- Virtual formwork models in BIM
- Material lists
- Plans, 3D images, animations
- IFC information flows

**Key Insight for Escora.AI:** Free tool that drives equipment sales. Library-based approach allows quick selection of manufacturer-specific components.

---

### 1.7 SH Digital (Brazil)

| Attribute | Details |
|-----------|---------|
| **Type** | Web platform + Labor calculator |
| **Target** | Brazilian construction companies, locadoras |
| **Pricing** | Free (for SH customers) |
| **Website** | [sh.com.br/digital-tools](https://sh.com.br/en/digital-tools/) |

**Inputs (Labor Calculator):**
- Area (m2)
- Assembly cycle
- Assembly rate
- Assembly team size
- Tax rates

**Outputs:**
- Labor cost estimates for assembly/disassembly
- Comparison: conventional vs metal formwork systems
- Comparison: conventional vs self-aligning panels
- Equipment balance reports
- Movement tracking reports

**Key Insight for Escora.AI:** SH is a direct competitor in the Brazilian market. Their labor calculator addresses a real pain point. Escora.AI should incorporate labor/cost estimation alongside structural calculations. SH's digital platform provides transparency to rental customers.

---

### 1.8 Trimble Tekla - USA Formwork Tools

| Attribute | Details |
|-----------|---------|
| **Type** | Tekla Structures extension (TSEP) |
| **Target** | Structural engineers, BIM modelers |
| **Pricing** | Included with Tekla Structures license |
| **Website** | [support.tekla.com](https://support.tekla.com/article/usa-formwork-tools) |

**Shoring Tools Available:**
- **Shoring Props:** Creates prop arrays with beams to support slabs
- **Prop Shoring Tower:** Builds towers from props, frames, heads, base plates
- **Drophead Shoring:** Drophead slab formwork with primary/secondary beams
- **Shoring Tower:** Frame-based towers with deck tables

**Workflow:**
1. Model slab/beam structure
2. Select shoring tool and system
3. Auto-place or manually position shoring elements
4. Modify spacing, heights, and configurations
5. Generate material lists and drawings

**Key Insight for Escora.AI:** Tekla demonstrates the importance of supporting multiple shoring topologies (props, towers, drophead). The auto-place with manual override pattern is ideal.

---

### 1.9 ALLPLAN - Formwork Planning

| Attribute | Details |
|-----------|---------|
| **Type** | BIM software module |
| **Target** | Structural engineers, BIM professionals |
| **Pricing** | Licensed (part of ALLPLAN suite) |
| **Website** | [allplan.com](https://www.allplan.com/us_en/industry-solutions/site-planning/) |

**Key Features:**
- Automated formwork assignment from concrete element geometry
- Manual override for individual areas
- BIM2form add-on with PERI MAXIMO integration
- 2025 version: New graphical interface for formwork management
- Element selection/deselection for constrained planning
- Supports, bracing, and accessories as separate elements

**Key Insight for Escora.AI:** ALLPLAN's dual auto/manual workflow is the gold standard. The 2025 UI refresh shows the industry is actively modernizing interfaces.

---

### 1.10 Revit Formwork Ecosystem

| Attribute | Details |
|-----------|---------|
| **Type** | Revit plugins/add-ins |
| **Pricing** | Varies (free to paid) |

**Notable Plugins:**
- **DokaCAD for Revit:** 40,000+ model solutions, 3D planning, positioning guides, BIM collaboration
- **PERI for Revit:** MAXIMO and SKYDECK system libraries
- **Formwork Area Add-in:** Calculates formwork area for foundations, columns, framing, floors, walls
- **Academic families** (UNICAMP, Brazil): Research-grade formwork components

**Key Insight for Escora.AI:** The Revit ecosystem shows strong demand for formwork tools. The Brazilian academic connection (UNICAMP) suggests local expertise exists for collaboration.

---

## 2. Interface Best Practices for Construction Software

### 2.1 Critical UI/UX Findings

Based on industry analysis, construction software suffers from:
- 80% less IT spending than other industries
- Overloaded forms with too many fields
- Hard-to-navigate deep menu structures
- Poor readability (tiny text, low contrast)
- Desktop-only interfaces in a mobile-first field

**Recommended Best Practices for Escora.AI:**

| Practice | Implementation |
|----------|---------------|
| **Simplified navigation** | Reduce menu layers, add search, clear visual hierarchy |
| **Visual clarity** | Consistent colors, readable fonts, ample whitespace |
| **Smart defaults** | Pre-fill common values (e.g., NBR 15696 loads, typical spans) |
| **Progressive disclosure** | Show basic inputs first, advanced options on demand |
| **Mobile-first** | Touch-friendly buttons, responsive layouts, offline capability |
| **Role-based views** | Different dashboards for engineer vs locadora vs construtora |

### 2.2 Visualization Priorities

| Priority | Format | Use Case |
|----------|--------|----------|
| **1 (Essential)** | 2D Plan View | Beam/tower layout on floor plan -- primary working view |
| **2 (Essential)** | Tables/BOM | Equipment lists, quantities, costs |
| **3 (High)** | Cross-section views | Verify heights, tower configurations |
| **4 (Medium)** | 3D Interactive | Client presentations, spatial understanding |
| **5 (Future)** | AR Overlay | Field verification, assembly guidance |

### 2.3 Export Formats (Priority Order)

| Format | Purpose | Priority |
|--------|---------|----------|
| **DXF/DWG** | AutoCAD compatibility, projeto executivo | Essential |
| **PDF** | Reports, BOM, client deliverables | Essential |
| **Excel/CSV** | Material lists, cost spreadsheets, purchasing | Essential |
| **IFC** | BIM interoperability, large projects | Medium |
| **PNG/SVG** | Web visualization, quick sharing | Medium |

### 2.4 Mobile vs Desktop Usage

- **Desktop:** Full planning, detailed editing, report generation, DXF import/processing
- **Tablet (field):** Review plans, verify positions, mark changes, photo overlay
- **Mobile (phone):** Quick BOM lookup, status checks, approvals, notifications

**Recommendation:** Start desktop-first (web app), with responsive views for tablet review. Native mobile app is a phase 2 feature.

### 2.5 Language and Localization

- **Primary:** PT-BR (Brazilian Portuguese)
- **Technical terms:** Use Brazilian construction industry terminology (escoramento, escoras, longarinas, transversinas, torres, etc.)
- **Standards:** Reference NBR 15696 throughout
- **Units:** Metric only (cm, m, kN, kgf/m2, kg/m3)
- **Future:** EN/ES for export to Latin American markets

---

## 3. Dashboard Design Recommendations for Escora.AI

### 3.1 Upload Flow

```
Current:  DXF file --> CLI processing --> text output
Proposed: DXF file --> drag-and-drop upload --> progress indicator -->
          auto-detection results --> interactive review --> approve/edit
```

**Improvements:**
- Drag-and-drop DXF upload with preview thumbnail
- Auto-detect slab outlines, beam positions, column grid
- Show detection confidence scores ("Found 3 slabs, 12 beams -- 94% confidence")
- Allow manual correction before calculation
- Support paste from clipboard (screenshot of plant for AI interpretation)
- Upload history with version comparison

### 3.2 Results Visualization

**Primary View: Interactive 2D Plan**
- Color-coded elements: slabs (light blue), beams (orange), towers (red dots), shores (green lines)
- Hover for details (load, utilization %, equipment spec)
- Click to select and edit individual elements
- Pan/zoom with standard controls
- Layer toggles (structure, shoring, dimensions, loads)
- Utilization heat map overlay (green < 60%, yellow 60-80%, red > 80%)

**Secondary View: Equipment Table**
- Sortable/filterable BOM
- Grouped by equipment type (escoras, longarinas, transversinas, forcados)
- Quantity, unit weight, total weight
- Stock availability indicator (if integrated with locadora inventory)
- Cost column (if pricing data available)

**Tertiary View: Cross Sections**
- Auto-generated typical sections
- Shows tower height, beam arrangement, slab thickness
- Dimension annotations
- Load diagram overlay

### 3.3 Interactive Editing

- **Drag shores:** Move tower positions, system recalculates
- **Change spacing:** Slider or input for grid spacing, live update
- **Swap equipment:** Drop-down to change beam type (e.g., VM100 to VM130)
- **Add/remove towers:** Click to add, right-click to remove
- **Undo/redo:** Full history stack
- **Snap to grid:** Configurable grid spacing
- **Constraint warnings:** Real-time alerts when limits exceeded

### 3.4 Equipment Catalog Integration

- Built-in catalog of Brazilian shoring equipment (SH, Mills, Locguel systems)
- Filter by: manufacturer, type, capacity, length, availability
- Drag from catalog to plan
- Custom catalogs for locadoras (their own stock)
- Equipment specs with load tables and images

### 3.5 Cost Estimation Display

- **Summary card:** Total estimated cost (rental + labor)
- **Breakdown chart:** Pie/bar chart by equipment category
- **Taxa kg/m3:** Key industry metric displayed prominently
- **Comparison bar:** Show cost vs previous revision or alternative solution
- **What-if slider:** "If we add 2 more towers, cost changes by +R$X but utilization drops to Y%"

### 3.6 Comparison Views

- Side-by-side plan comparison (revision A vs B)
- Diff highlighting (added = green, removed = red, changed = yellow)
- BOM delta table (what changed in quantities)
- Cost delta summary
- Engineer revision tracking with comments

### 3.7 Project History & Analytics

- Project timeline with milestones (upload, calculation, revision, approval, execution)
- Dashboard metrics: projects completed, average taxa kg/m3, equipment utilization
- Search/filter projects by client, date, building type, size
- Duplicate project as template for similar buildings
- Analytics: most-used equipment, common revision patterns

### 3.8 Team Collaboration

- Role-based access: Admin, Engineer, Reviewer, Viewer
- Comments on specific plan elements (pin to location)
- Approval workflow (submit for review, approve/reject with notes)
- Activity log per project
- Share via link (read-only view without account)

### 3.9 PDF Report Generation

**Report sections:**
1. Cover page (project info, client, date, engineer stamp)
2. Executive summary (area, taxa kg/m3, total cost)
3. Floor plan with shoring layout
4. Typical cross sections
5. Equipment list (BOM) with quantities
6. Load calculations summary (per NBR 15696)
7. Assembly notes and safety warnings
8. Revision history

### 3.10 Locadora Integration

- API for locadoras to push real-time stock availability
- Price list integration (per-day rental rates)
- Automatic delivery scheduling suggestions
- Return date calculation based on curing schedule
- Multi-locadora price comparison
- Direct order placement from calculated BOM

---

## 4. AI-Powered Features

### 4.1 Auto-Detection from DXF

| Feature | Description | Difficulty |
|---------|-------------|------------|
| Slab outline detection | Identify slab boundaries from closed polylines | Implemented |
| Beam detection | Find beam lines and dimensions | Implemented |
| Column grid recognition | Detect column positions and grid pattern | Medium |
| Construction method inference | Determine if conventional, flying table, etc. | Hard |
| Floor height extraction | Read elevation data from DXF layers | Medium |
| Opening detection | Find stair openings, elevator shafts, voids | Medium |

### 4.2 Intelligent Equipment Selection

- **Load-based:** Select minimum equipment that satisfies structural requirements
- **Stock-based:** Optimize using available inventory (avoid ordering new equipment)
- **Cost-based:** Minimize rental cost while maintaining safety factors
- **Reuse-based:** Maximize equipment reuse across floors/phases
- **Hybrid:** Multi-objective optimization balancing all factors

### 4.3 Learning from Engineer Revisions

This is Escora.AI's strongest differentiator:

```
Cycle:
  1. AI generates initial shoring layout
  2. Engineer reviews and modifies (moves towers, changes beams)
  3. System captures delta between AI proposal and engineer final
  4. ML model trains on: "given this geometry + loads, engineer preferred this layout"
  5. Next similar project: AI proposal is closer to what engineer would do
```

**Data to capture per revision:**
- Tower position changes (dx, dy)
- Equipment substitutions (what was swapped and why)
- Spacing adjustments
- Added/removed elements
- Engineer's notes/comments
- Project context (building type, client preferences)

### 4.4 Predictive Cost Optimization

- Historical cost database per project type and region
- Predict total shoring cost before detailed calculation
- Suggest cost-saving alternatives ("Using VM130 instead of VM100 saves 8 towers and R$2,400")
- Seasonal pricing awareness (peak construction months)
- Multi-floor optimization (plan equipment rotation across floors)

### 4.5 Risk and Safety Alerts

- **Overload warning:** Highlight elements exceeding 90% utilization in red
- **Missing bracing:** Detect towers without adequate lateral bracing
- **Height limits:** Flag when tower height exceeds manufacturer limits
- **NBR 15696 compliance:** Automatic checklist verification
- **Weather alerts:** Wind load warnings based on tower height and location
- **Proximity warnings:** Detect conflicts with building edges, openings

### 4.6 Natural Language Queries

Example queries an engineer could type or speak:

| Query | System Response |
|-------|-----------------|
| "Mostre todas as escoras com taxa > 80%" | Highlights overloaded elements on plan |
| "Qual a taxa kg/m3 do pavimento tipo?" | Displays metric with breakdown |
| "Troque todas VM100 por VM130" | Batch substitution with recalculation |
| "Adicione uma torre na posicao 4.5, 7.2" | Places tower at coordinates |
| "Compare com a versao anterior" | Opens side-by-side comparison |
| "Gere o relatorio PDF" | Creates and downloads PDF report |
| "Quanto custa se eu alugar da Mills?" | Shows cost estimate with Mills pricing |

---

## 5. Competitive Positioning Matrix

| Feature | Doka EFP | PERI Calc | PASCHAL PPL | SH Digital | Tekla FW | **Escora.AI** |
|---------|----------|-----------|-------------|------------|----------|---------------|
| Free tier | Yes | Yes | No | Partial | No | **Yes** |
| Web-based | Yes | Yes | No | Yes | No | **Yes** |
| Mobile | Yes | Yes | No | Yes | No | **Phase 2** |
| DXF import | No | No | Yes | No | Yes | **Yes** |
| Auto-calculation | Yes | Partial | Yes | No | Yes | **Yes** |
| Stock matching | No | No | Yes | Partial | No | **Yes** |
| AI-powered | No | No | No | No | No | **Yes** |
| NBR 15696 | No | No | No | No | No | **Yes** |
| PT-BR native | No | No | No | Yes | No | **Yes** |
| Multi-manufacturer | No | No | No | No | Partial | **Yes** |
| Cost estimation | No | No | No | Yes | No | **Yes** |
| Engineer learning | No | No | No | No | No | **Yes** |
| PDF reports | No | Yes | Yes | No | Yes | **Yes** |

---

## 6. Key Takeaways for Escora.AI Development

### Immediate Priorities (MVP)
1. **Web-based interface** with drag-and-drop DXF upload (like Doka EFP simplicity)
2. **Interactive 2D plan viewer** with color-coded shoring layout
3. **Equipment BOM table** with export to PDF/Excel
4. **Utilization heat map** to quickly identify overloaded elements
5. **PDF report generation** following Brazilian engineering standards

### Short-term (3-6 months)
6. **Stock matching** against locadora inventory (like PASCHAL PPL)
7. **Cost estimation** with taxa kg/m3 display (like SH calculator)
8. **Comparison views** for revision tracking
9. **Role-based access** for team collaboration
10. **Natural language queries** for power users

### Medium-term (6-12 months)
11. **AI learning from engineer revisions** (unique differentiator)
12. **Multi-manufacturer catalog** (SH, Mills, Locguel equipment)
13. **Mobile/tablet view** for field verification
14. **API for locadora integration** (real-time stock/pricing)
15. **IFC export** for BIM workflows

### Long-term (12+ months)
16. **AR visualization** for field assembly guidance
17. **Predictive cost optimization** across project portfolio
18. **Multi-floor optimization** with equipment rotation planning
19. **Marketplace** connecting construtoras with locadoras
20. **AI-powered DXF interpretation** from screenshots/photos

---

## Sources

### Software Tools
- [Doka Tipos 9](https://www.doka.com/us/solutions/services/dfds/dfds-planning-software/tipos-software-formwork-planning)
- [Doka Easy Formwork Planner](https://www.doka.com/en/solutions/services/easy-formwork-planner)
- [Doka Digital Solutions](https://www.doka.com/en/solutions/digital-solutions)
- [DokaCAD for Revit](https://www.doka.com/en/solutions/services/dfds/dfds-planning-software/dokacad-for-revit-formwork-planning-software)
- [PERI CAD 24](https://www.peri-usa.com/products/peri-cad-software.html)
- [PERI Formwork Load Calculator](https://apps.peri.com/SLR/index.php?lang=en)
- [PERI Software & Apps](https://www.perihk.com/en/products/product-overview/digital-products/software-apps.html)
- [ULMA Studio for Revit](https://www.ulmaconstruction.com/en/ulma/news/ulma-studio-for-revit-available)
- [SH Digital Tools](https://sh.com.br/en/digital-tools/)
- [SH Labor Calculator](https://materiais.sh.com.br/calculadora-custo-mao-de-obra-montagem)
- [PASCHAL-Plan light](https://www.paschal.de/english/products/software/index_software.php)
- [Tekla USA Formwork Tools](https://support.tekla.com/article/usa-formwork-tools)
- [ALLPLAN Formwork Planning](https://www.allplan.com/us_en/industry-solutions/site-planning/)
- [Mills Escoramentos](https://www.mills.com.br/formas-e-escoramentos/escoramentos-ts-mills)

### UI/UX and Industry
- [Why Construction Software Feels Stuck in the 90s](https://altersquare.medium.com/why-construction-software-feels-stuck-in-the-90s-ui-ux-challenges-in-industrial-applications-52842619b776)
- [Construction Dashboard Best Practices 2025](https://www.linkedin.com/pulse/what-good-construction-dashboard-looks-like-2025-mastt-6iwkc)
- [Trimble: Formwork Planning in 3D](https://www.trimble.com/blog/construction/en-US/article/speaking-concretely-detailed-formwork-planning-in-3d)
- [Construction Technology Trends 2025](https://gobridgit.com/blog/construction-technology-trends/)

### AI in Construction
- [Togal.AI - AI Takeoff](https://www.togal.ai/)
- [Civils.ai - Quantity Takeoffs](https://civils.ai/)
- [Kreo - AI Estimating](https://www.kreo.net/)
- [AI Construction Tools 2026](https://www.mastt.com/software/ai-construction-tools)
- [Formwork Automation Research (ResearchGate)](https://www.researchgate.net/publication/350340291_Development_of_formwork_automation_design_software_for_improving_construction_productivity)

### Standards
- [NBR 15696 Guide (EngSette)](https://engsette.com.br/nbr15696/)
- [ABRASFE - NBR 15696](https://abrasfe.org.br/wp-content/uploads/2022/07/abrasfe-academy_escoramento-r03.pdf)
- [IFC Format Overview](https://cadexchanger.com/ifc/)
- [BIM File Formats](https://www.designingbuildings.co.uk/wiki/File_formats_for_BIM)
