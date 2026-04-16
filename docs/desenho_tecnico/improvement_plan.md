# Technical Drawing Engine — Improvement Plan

## Priority Ranking

| # | Improvement | Status | Impact |
|---|-------------|--------|--------|
| 1 | Unified BuildingModel (real materials) | DONE | Enables everything else |
| 2 | Wall intersection resolution | DONE | Visual quality jump |
| 3 | Openings cut through walls | DONE | Essential for planta baixa |
| 4 | Auto-dimensioning | DONE | Huge time saver |
| 5 | Roof geometry | DONE | Completes sections + elevations |
| 6 | Paper space viewports | DONE | Professional DXF output |
| 7 | Sketch/image input | DONE | The differentiator feature |

---

## #1 — Unified BuildingModel (Real Materials)

**Problem**: Walls are disconnected (p1, p2, thickness) tuples. No single source of truth. No material properties.

**Solution**: `BuildingModel` class with:
- Walls referencing real construction materials (bloco ceramico 14cm, bloco concreto 19cm, drywall 10cm, etc.)
- Openings (doors/windows) linked to their parent wall
- Slabs with type (laje pre-moldada, macica, steel deck) and thickness
- Foundation type (sapata corrida, radier, estaca)
- Roof with slope, overhang, material (ceramica, fibrocimento, metalica)
- Each view generator reads from the model — no data duplication

**Material correlation**: Every element stores its material, which determines:
- Wall thickness (bloco 9cm, 14cm, 19cm + revestimento)
- Hatch pattern in sections (tijolo, concreto, drywall)
- Structural properties (carga admissivel, peso proprio)
- Cost estimation data

---

## #2 — Wall Intersection Resolution

**Problem**: Walls overlap at corners. No T-junctions or L-junctions.

**Solution**: Computational geometry to detect wall intersections:
- Extend/trim wall segments at junctions
- Merge overlapping outlines into clean polygons
- Differentiate L-corner, T-junction, X-crossing
- Use Shapely for polygon operations

---

## #3 — Openings Cut Through Walls

**Problem**: Doors/windows draw symbols but don't create gaps in wall fill.

**Solution**: Wall geometry split around openings:
- Each opening defines a void in its parent wall
- Wall polyline and hatch are generated with the void subtracted
- Door arc and window lines drawn inside the void

---

## #4 — Auto-Dimensioning

**Problem**: Dimensions are manually placed.

**Solution**: Auto-detect from BuildingModel:
- External chain dimensions (total + segments)
- Internal room dimensions
- Opening positions and sizes
- NBR ordering: smaller dims closer to object
- No duplicate dimensions
- Level marks on sections

---

## #5 — Roof Geometry

**Problem**: No roof in sections or elevations.

**Solution**: Roof primitives:
- Gable (duas aguas), hip (quatro aguas), shed (uma agua)
- Configurable slope (%), overhang (beiral), ridge height
- Material: ceramica, fibrocimento, metalica, concreto
- Draws in section (tesoura profile) and elevation (outline + tiles)

---

## #6 — Paper Space / Viewports

**Problem**: Everything in model space. Can't mix scales on same sheet.

**Solution**: Use ezdxf Layout/Viewport:
- Plan at 1:50, detail at 1:20, title block at 1:1 on same sheet
- Each viewport has its own scale and layer visibility
- Title block always in paper space

---

## #7 — Sketch/Image Input

**Problem**: No input from hand-drawn sketches.

**Solution**: Image processing pipeline:
- OpenCV line detection (Hough transform)
- ML classification (wall vs dimension vs annotation)
- Vectorization to BuildingModel
- Human review/correction step

---

## Material Database

Real Brazilian construction materials that BuildingModel must support:

### Walls
| Material | Thickness (cm) | Peso (kN/m²) | Hatch |
|----------|----------------|---------------|-------|
| Bloco cerâmico 9cm | 9 + 2×1.5 = 12 | 1.30 | BRICK |
| Bloco cerâmico 14cm | 14 + 2×1.5 = 17 | 1.80 | BRICK |
| Bloco cerâmico 19cm | 19 + 2×1.5 = 22 | 2.30 | BRICK |
| Bloco concreto 14cm | 14 + 2×1.5 = 17 | 2.20 | CONCRETE |
| Bloco concreto 19cm | 19 + 2×1.5 = 22 | 2.80 | CONCRETE |
| Drywall simples | 10 | 0.25 | GENERIC |
| Drywall duplo | 12.5 | 0.50 | GENERIC |
| Concreto armado | 10-25 | varies | CONCRETE |

### Slabs
| Type | Thickness (cm) | Peso (kN/m²) |
|------|----------------|---------------|
| Laje pré-moldada h=8+4 | 12 | 1.65 |
| Laje pré-moldada h=12+4 | 16 | 2.10 |
| Laje maciça e=10 | 10 | 2.50 |
| Laje maciça e=12 | 12 | 3.00 |
| Steel deck | 12-15 | 2.00-2.50 |

### Foundations
| Type | Use |
|------|-----|
| Sapata corrida | Alvenaria estrutural, solo bom |
| Radier | Solo fraco, distribuição uniforme |
| Sapata isolada | Pilares, cargas pontuais |
| Estaca | Solo muito fraco, aterro |
| Baldrame + bloco | Sistema misto pilar-viga |

### Roof
| Material | Peso (kN/m²) | Slope min (%) |
|----------|---------------|---------------|
| Telha cerâmica | 0.50-0.80 | 30-35 |
| Fibrocimento 6mm | 0.20-0.30 | 10-15 |
| Metálica (galvalume) | 0.05-0.10 | 5-10 |
| Concreto (laje impermeabilizada) | 2.50+ | 1-3 |
