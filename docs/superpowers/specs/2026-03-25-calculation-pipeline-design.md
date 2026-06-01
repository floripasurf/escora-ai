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

## 3. Prerequisites

### 3.0 Populate ClassifiedElement Geometry

Currently `ClassifiedElement.geometry` is always `[]` in `stage_classify.py`. This must be populated before the calculation pipeline can work:

- **Beams**: store axis endpoints as `geometry = [(start_x, start_y), (end_x, end_y)]`. The axis is the midline between the parallel segment pair (already computed as `axis_coord` + `start`/`end` in `BeamCandidate`).
- **Pillars**: store center as `geometry = [(cx, cy)]`. For rectangular pillars, center = `PillarCandidate.cx, cy`. For circular pillars, center = `CircleEntity.cx, cy`.

This is a prerequisite task that modifies `stage_classify.py` to pass coordinates through from the detection stage.

**Coordinate system**: beam axis for an x-direction beam is `[(start, axis_coord), (end, axis_coord)]`; for y-direction: `[(axis_coord, start), (axis_coord, end)]`.

## 4. Structural Model Builder

### 4.1 Beam-Pillar Association

For each beam, determine which pillars provide support:
- **Beam axis**: LineString from `geometry[0]` to `geometry[1]` (two endpoints stored in ClassifiedElement)
- **Pillar center**: centroid from `geometry[0]` (single point stored in ClassifiedElement)
- **Proximity check**: a pillar supports a beam if the pillar center is within 0.30m of the beam's axis line
- **Endpoint classification**: for each beam endpoint, if a pillar is within 0.30m → supported; if no pillar → cantilever (free end)
- **Output**: populate `support_positions` (list of distances along beam axis where pillars sit) and `is_cantilever_start/end` flags on each beam

### 4.2 Slab Derivation from Beam Grid

Beams form a grid. The enclosed polygonal regions = slab panels.

Algorithm:
1. Convert each beam to a Shapely LineString along its axis (from start to end coordinates)
2. Union all beam lines into a single geometry network
3. Use `shapely.ops.polygonize()` to extract closed regions
4. Each resulting polygon is a slab panel

For each slab panel:
- `thickness_m`: from nearby text annotation (regex: `h=\d+`, `e=\d+`, `ESP \d+`), or default 0.12m flagged for review
- Classification: interior (bounded by beams on all sides) or edge (some sides open)

### 4.3 Cantilever Slab Detection

After deriving interior slabs:
1. Compute the pillar hull (convex hull of all pillar centers)
2. Beam segments extending beyond the last supporting pillar = cantilever beams
3. Slab regions outside the pillar hull but attached to a beam = laje em balanço
4. Tag with `is_cantilever = True` for denser shoring

## 5. Load Calculation

Reuses existing engine modules directly.

### 5.1 Beam Shoring

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

### 5.2 Slab Shoring

For each derived slab panel:
1. Construct `Slab.from_polygon(polygon, layer_name='derived', thickness_m=...)` to create the `Slab` object required by the engine
2. `calculate_total_load(slab, q_sobrecarga, gamma_f)` — takes the `Slab` object, not raw values
3. `distribute_shores(slab, shore, total_load_kn, ...)` with:
   - `Slab` object (wraps the Shapely polygon)
   - Pillar exclusion zones: all pillars within/near the slab as `PillarExclusion` objects (DISTANCIA_PILAR_MIN = 0.20m)
   - Beam exclusion zones: model as a series of rectangular `PillarExclusion` objects along the beam axis (0.40m wide, beam length long). This reuses the existing exclusion mechanism without modifying engine code.
4. Cantilever slabs: apply reduced `max_spacing * 0.7` uniformly to the entire cantilever slab panel (simpler, conservative approach)
5. `select_shore()` based on slab load and height requirements

### 5.3 Pe-Direito (Floor Height)

- Extract from DXF text annotations via existing `stage_metadata.py`
- When not found: use default 2.80m (ALTURA_DEFAULT)
- Flag prominently: `pe_direito_is_default = True` in results
- Operator must see this in preview and correct if wrong before approving

### 5.4 Shore Catalog

- Use the existing catalog file `data/catalogs/telescopic_shores.json` (already loaded by `shore_selector.load_catalog()`)
- If the file doesn't exist, create it as a generic catalog covering height ranges 1.80-5.50m, capacities 10-50 kN
- No specific manufacturer branding — generic spec-based entries
- Known limitation: no entries below 1.80m for very low ceilings
- Future: per-tenant catalog upload via API (not in this scope)

### 5.5 Error Handling

- If `select_shore()` returns `None` (no compatible shore): skip the element, add a warning to `CalculationResult.warnings` with the element name and required specs. Do not fail the entire calculation.
- Low-confidence elements (`score_final < 0.70`): include in calculations but add to `warnings` list. Elements with `score_final < 0.50`: skip and warn.
- Missing beam section (no width or height): skip beam, warn. Use slab default thickness (0.12m) when not found, flag with `thickness_is_default`.

## 6. Result Models

### Integration with PipelineResult

`CalculationResult` is nested inside `PipelineResult` as an optional field: `calculation: Optional[CalculationResult] = None`. This keeps the existing API contract — `runner.py` returns `PipelineResult` with calculation populated when the engine stage runs successfully.

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

## 7. Data Flow

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

## 8. File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/pipeline/stage_classify.py` | Modify | Populate `geometry` field with beam axis endpoints and pillar centers |
| `src/pipeline/stage_calculate.py` | Create | Bridge: structural model + orchestrates engine calls |
| `src/engine/slab_builder.py` | Create | Derive slab polygons from beam grid via Shapely |
| `src/models/calculation_models.py` | Create | BeamShoringResult, SlabShoringResult, CalculationResult |
| `src/models/pipeline_models.py` | Modify | Add `calculation: Optional[CalculationResult]` to PipelineResult |
| `src/pipeline/stage_metadata.py` | Modify | Add slab thickness extraction function |
| `src/pipeline/runner.py` | Modify | Wire stage_calculate after stage_classify |
| `data/catalogs/telescopic_shores.json` | Create (if missing) | Generic telescopic shore catalog |
| `tests/engine/test_slab_builder.py` | Create | Slab derivation from beam grid |
| `tests/pipeline/test_stage_calculate.py` | Create | Integration tests with synthetic + real DXFs |

No changes to existing engine files (`load_calculator`, `beam_calculator`, `grid_distributor`, `shore_selector`, `validator`) — they are used as-is.

## 9. Out of Scope

- Frontend preview rendering
- PDF/BOM output generation (consumes CalculationResult but is a separate stage)
- Multi-tenant catalog management API
- Operator corrections / learning persistence (stage 6 in the SaaS spec)
- Slab thickness extraction from section cuts (future enhancement)

## 10. NBR References

| Standard | Usage |
|----------|-------|
| NBR 15696:2009 | Formwork/shoring: load magnification (gamma_f=1.4), live load (1.5 kN/m²), spacing limits, edge/pillar distances |
| NBR 6118 | Structural design: beam support conditions, cantilever rules, slab influence zones |
| NBR 6120:2019 | Structural loads: concrete specific weight (25 kN/m³) |

## 11. Testing Strategy

- **Unit tests**: slab_builder (polygonize beam grids of varying complexity)
- **Unit tests**: beam-pillar association (various configurations: corner, edge, interior pillars)
- **Integration tests**: stage_calculate with synthetic DXF (known geometry → expected shore count)
- **Regression tests**: CVS-COB and CFL-SUB DXFs (smoke test — pipeline completes without errors, produces non-zero results)
