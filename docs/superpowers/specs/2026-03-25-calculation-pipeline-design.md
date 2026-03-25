# Calculation Pipeline Bridge — Design Spec

**Date**: 2026-03-25
**Status**: Approved (brainstorm)
**Author**: Raphael + Claude

---

## 1. Problem

The DXF interpretation pipeline (stages 1-4) produces classified structural elements (beams, pillars) with confidence scores, but stops there. The existing engine modules (`load_calculator`, `beam_calculator`, `grid_distributor`, `shore_selector`, `validator`) can calculate shoring, but expect manual inputs (Slab polygons, beam dimensions, support positions). There is no bridge connecting pipeline output to engine input.

## 2. Solution

A new pipeline stage (`stage_calculate.py`) that:
1. Builds a structural model — associates beams with pillars, derives slab panels from the beam grid, detects cantilevers
2. Runs load and shore calculations using the existing engine (no new math)
3. Packages results with validation and warnings

## 3. Structural Model Builder

### 3.1 Beam-Pillar Association

For each beam, determine which pillars provide support:
- **Proximity check**: a pillar supports a beam if the pillar center is within 0.30m of the beam's axis line
- **Endpoint classification**: for each beam endpoint, if a pillar is within 0.30m → supported; if no pillar → cantilever (free end)
- **Output**: populate `support_positions` (list of distances along beam axis where pillars sit) and `is_cantilever_start/end` flags on each beam

### 3.2 Slab Derivation from Beam Grid

Beams form a grid. The enclosed polygonal regions = slab panels.

Algorithm:
1. Convert each beam to a Shapely LineString along its axis (from start to end coordinates)
2. Union all beam lines into a single geometry network
3. Use `shapely.ops.polygonize()` to extract closed regions
4. Each resulting polygon is a slab panel

For each slab panel:
- `thickness_m`: from nearby text annotation (regex: `h=\d+`, `e=\d+`, `ESP \d+`), or default 0.12m flagged for review
- Classification: interior (bounded by beams on all sides) or edge (some sides open)

### 3.3 Cantilever Slab Detection

After deriving interior slabs:
1. Compute the pillar hull (convex hull of all pillar centers)
2. Beam segments extending beyond the last supporting pillar = cantilever beams
3. Slab regions outside the pillar hull but attached to a beam = laje em balanço
4. Tag with `is_cantilever = True` for denser shoring

## 4. Load Calculation

Reuses existing engine modules directly.

### 4.1 Beam Shoring

For each classified beam:
1. `calculate_beam_total_linear_load()` with:
   - Beam section (width x height) from `ClassifiedElement`
   - Slab influence zone: half the adjacent slab span on each side (NBR 6118)
   - Slab thickness from derived slab panel or default 0.12m
   - Live load: Q_SOBRECARGA_DEFAULT = 1.5 kN/m² (NBR 15696)
   - Magnification factor: GAMMA_F = 1.4 (NBR 15696)
2. `distribute_beam_shores()` with:
   - Beam length from `ClassifiedElement.length_m`
   - Support positions from beam-pillar association
   - Cantilever flags from endpoint classification
3. `select_shore()` from default catalog based on required height and capacity
   - Required height = pé-direito - beam_height (via `estimate_beam_shore_height()`)

### 4.2 Slab Shoring

For each derived slab panel:
1. `calculate_total_load()` with area, thickness, live load
2. `distribute_shores()` with:
   - Slab polygon (Shapely)
   - Pillar exclusion zones: all pillars within/near the slab (DISTANCIA_PILAR_MIN = 0.20m)
   - Beam exclusion zones: 0.40m influence zone along each beam edge (shores already covered by beam shoring)
3. Cantilever slabs: reduce `max_spacing` by 30% near the free edge (denser shoring per NBR 15696)
4. `select_shore()` based on slab load and height requirements

### 4.3 Pe-Direito (Floor Height)

- Extract from DXF text annotations via existing `stage_metadata.py`
- When not found: use default 2.80m (ALTURA_DEFAULT)
- Flag prominently: `pe_direito_is_default = True` in results
- Operator must see this in preview and correct if wrong before approving

### 4.4 Shore Catalog

- Ship with a default generic catalog (`data/catalogs/default_shores.json`)
- Covers common telescopic shore specs: height ranges 1.80-5.00m, capacities 10-50 kN
- No specific manufacturer branding — generic spec-based entries
- Future: per-tenant catalog upload via API (not in this scope)

## 5. Result Models

### BeamShoringResult
- `beam: ClassifiedElement` — the classified beam
- `support_positions: List[float]` — pillar distances along axis
- `is_cantilever_start: bool`, `is_cantilever_end: bool`
- `total_linear_load_kn_m: float` — majorized load per meter
- `shores: List[PositionedShore]` — positioned shores along beam
- `shore_count: int`, `spacing_m: float`
- `selected_shore: ShoreCatalogEntry`
- `shore_height_m: float` — actual shore height used

### SlabShoringResult
- `polygon: Polygon` — Shapely polygon of slab panel
- `thickness_m: float`, `thickness_is_default: bool`
- `area_m2: float`
- `is_cantilever: bool`
- `total_load_kn: float` — majorized total load
- `shores: List[PositionedShore]` — grid-distributed shores
- `grid_nx: int`, `grid_ny: int`, `spacing_x_m: float`, `spacing_y_m: float`
- `selected_shore: ShoreCatalogEntry`
- `exclusions: List[PillarExclusion]` — pillar and beam exclusion zones applied

### CalculationResult
- `beam_results: List[BeamShoringResult]`
- `slab_results: List[SlabShoringResult]`
- `shore_catalog_used: List[ShoreCatalogEntry]` — distinct models selected
- `total_shores: int` — sum across all beams and slabs
- `total_load_kn: float`
- `pe_direito_m: float`, `pe_direito_is_default: bool`
- `warnings: List[str]` — defaults used, missing data, low-confidence elements
- `validation_errors: List[str]` — from validator.py checks
- `is_valid: bool`

## 6. Data Flow

```
ClassifiedElements (beams, pillars) + metadata (pe_direito, thickness)
        |
        v
   Associate beams <-> pillars (proximity 0.30m + endpoint check)
        |
        v
   Derive slab panels (polygonize beam grid with Shapely)
   Detect cantilever slabs (outside pillar convex hull)
        |
        v
   For each beam: load calc -> shore distribution (with supports + cantilevers)
   For each slab: load calc -> grid distribution (with pillar + beam exclusions)
        |
        v
   Shore selection from default catalog (per element)
        |
        v
   Validation (capacity, spacing per NBR 15696)
        |
        v
   CalculationResult (beams + slabs + shores + warnings)
```

## 7. File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/pipeline/stage_calculate.py` | Create | Bridge: structural model + orchestrates engine calls |
| `src/engine/slab_builder.py` | Create | Derive slab polygons from beam grid via Shapely |
| `src/models/calculation_models.py` | Create | BeamShoringResult, SlabShoringResult, CalculationResult |
| `src/pipeline/runner.py` | Modify | Wire stage_calculate after stage_classify |
| `data/catalogs/default_shores.json` | Create | Generic telescopic shore catalog |
| `tests/engine/test_slab_builder.py` | Create | Slab derivation from beam grid |
| `tests/pipeline/test_stage_calculate.py` | Create | Integration tests with synthetic + real DXFs |

No changes to existing engine files — they are used as-is.

## 8. Out of Scope

- Frontend preview rendering
- PDF/BOM output generation (consumes CalculationResult but is a separate stage)
- Multi-tenant catalog management API
- Operator corrections / learning persistence (stage 6 in the SaaS spec)
- Slab thickness extraction from section cuts (future enhancement)

## 9. NBR References

| Standard | Usage |
|----------|-------|
| NBR 15696:2009 | Formwork/shoring: load magnification (gamma_f=1.4), live load (1.5 kN/m²), spacing limits, edge/pillar distances |
| NBR 6118 | Structural design: beam support conditions, cantilever rules, slab influence zones |
| NBR 6120:2019 | Structural loads: concrete specific weight (25 kN/m³) |

## 10. Testing Strategy

- **Unit tests**: slab_builder (polygonize beam grids of varying complexity)
- **Unit tests**: beam-pillar association (various configurations: corner, edge, interior pillars)
- **Integration tests**: stage_calculate with synthetic DXF (known geometry → expected shore count)
- **Regression tests**: CVS-COB and CFL-SUB DXFs (smoke test — pipeline completes without errors, produces non-zero results)
