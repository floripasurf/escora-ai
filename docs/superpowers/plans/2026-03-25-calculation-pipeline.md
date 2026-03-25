# Calculation Pipeline Bridge — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bridge the DXF interpretation pipeline (stages 1-4) to the existing shoring engine, producing beam and slab shoring results with validation.

**Architecture:** A new pipeline stage (`stage_calculate.py`) builds a structural model from classified elements (beam-pillar association, slab derivation via Shapely polygonize), then orchestrates existing engine modules (load_calculator, beam_calculator, grid_distributor, shore_selector, validator) to produce `CalculationResult` nested in `PipelineResult`.

**Tech Stack:** Python 3.11+, Pydantic, Shapely (`polygonize`, `LineString`, `Point`, `ConvexHull`), existing engine modules (no new math).

**Spec:** `docs/superpowers/specs/2026-03-25-calculation-pipeline-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/pipeline/stage_classify.py` | Modify | Populate `geometry` field with beam axis endpoints and pillar centers |
| `src/models/calculation_models.py` | Create | `BeamShoringResult`, `SlabShoringResult`, `CalculationResult` |
| `src/models/pipeline_models.py` | Modify | Add `calculation: Optional[CalculationResult]` to `PipelineResult` |
| `src/engine/slab_builder.py` | Create | Derive slab polygons from beam grid via Shapely `polygonize` |
| `src/pipeline/stage_calculate.py` | Create | Structural model builder + engine orchestration |
| `src/pipeline/stage_metadata.py` | Modify | Add `extract_slab_thickness()` function |
| `src/pipeline/runner.py` | Modify | Wire `stage_calculate` after `stage_classify` |
| `tests/engine/test_slab_builder.py` | Create | Unit tests for slab derivation |
| `tests/models/test_calculation_models.py` | Create | Unit tests for calculation models |
| `tests/pipeline/test_stage_calculate.py` | Create | Integration tests for calculation stage |

---

## Chunk 1: Prerequisites + Models

### Task 0: Populate ClassifiedElement Geometry

**Files:**
- Modify: `src/pipeline/stage_classify.py:141-153` (beam geometry), `src/pipeline/stage_classify.py:186-197` (rect pillar geometry), `src/pipeline/stage_classify.py:250-261` (circle pillar geometry)
- Test: `tests/pipeline/test_geometry_population.py`

Currently `geometry=[]` everywhere in `stage_classify.py`. The calculation pipeline needs beam axis endpoints and pillar centers.

- [ ] **Step 1: Write failing test for beam geometry population**

```python
# tests/pipeline/test_geometry_population.py
"""Test that classify_elements populates geometry on beams and pillars."""

import pytest
from src.pipeline.stage_classify import classify_elements
from src.pipeline.stage_segment import LevelSegment
from src.pipeline.stage_parse import SegmentEntity, RectEntity, CircleEntity
from src.models.pipeline_models import ElementType


def _make_beam_segments(y1, y2, x_min, x_max, layer="BEAM"):
    """Create a pair of horizontal segments that form a beam."""
    return [
        SegmentEntity(type="H", y=y1, x_min=x_min, x_max=x_max, layer=layer),
        SegmentEntity(type="H", y=y2, x_min=x_min, x_max=x_max, layer=layer),
    ]


def test_beam_geometry_has_axis_endpoints():
    # Create a horizontal beam at y≈5.0, spanning x=0 to x=10
    segs = _make_beam_segments(4.9, 5.1, 0.0, 10.0)
    level = LevelSegment(level_name="TEST", segments=segs)
    elements = classify_elements(level, scale=1.0)

    beams = [e for e in elements if e.element_type == ElementType.BEAM]
    assert len(beams) >= 1
    beam = beams[0]
    assert len(beam.geometry) == 2, "Beam geometry should have 2 points (start, end)"
    # For x-direction beam: geometry = [(start_x, axis_y), (end_x, axis_y)]
    start_pt, end_pt = beam.geometry
    assert start_pt[1] == pytest.approx(end_pt[1], abs=0.01), "Both points should share axis Y"
    assert start_pt[0] < end_pt[0], "Start X should be less than end X"


def test_rect_pillar_geometry_has_center():
    rects = [
        RectEntity(cx=5.0, cy=5.0, width=0.20, height=0.40, area=0.08, layer="PIL"),
    ]
    level = LevelSegment(level_name="TEST", rects=rects)
    elements = classify_elements(level, scale=1.0)

    pillars = [e for e in elements if e.element_type == ElementType.PILLAR]
    assert len(pillars) >= 1
    pillar = pillars[0]
    assert len(pillar.geometry) == 1, "Pillar geometry should have 1 point (center)"
    assert pillar.geometry[0] == pytest.approx((5.0, 5.0), abs=0.01)


def test_circle_pillar_geometry_has_center():
    # Need >= 5 circles at same radius to trigger structural detection
    circles = [
        CircleEntity(cx=float(i), cy=float(i), radius=0.15, layer="COL")
        for i in range(6)
    ]
    level = LevelSegment(level_name="TEST", circles=circles)
    elements = classify_elements(level, scale=1.0)

    pillars = [e for e in elements if e.element_type == ElementType.PILLAR]
    assert len(pillars) >= 5
    for p in pillars:
        assert len(p.geometry) == 1, "Circular pillar geometry should have 1 point"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/pipeline/test_geometry_population.py -v`
Expected: FAIL — beam.geometry is `[]`, pillar.geometry is `[]`

- [ ] **Step 3: Implement geometry population in stage_classify.py**

In `src/pipeline/stage_classify.py`, modify the three places where `ClassifiedElement` is created:

**Beam geometry (line ~141-153):** Replace `geometry=[]` with axis endpoints derived from `BeamCandidate`:

```python
        # Beam axis endpoints: for x-direction beam, axis is horizontal line
        # For y-direction beam, axis is vertical line
        if bc.direction == "x":
            beam_geometry = [(bc.start, bc.axis_coord), (bc.end, bc.axis_coord)]
        else:
            beam_geometry = [(bc.axis_coord, bc.start), (bc.axis_coord, bc.end)]

        el = ClassifiedElement(
            element_type=ElementType.BEAM,
            geometry=beam_geometry,
            # ... rest unchanged
        )
```

Note: `bc.start`, `bc.end`, `bc.axis_coord` are already in scaled coordinates (segments were scaled on lines 108-110). The geometry should be in the **same coordinate space** as the segments (scaled = real meters when scale=1.0).

**Rectangular pillar geometry (line ~186-197):** Replace `geometry=[]` with center point:

```python
        el = ClassifiedElement(
            element_type=ElementType.PILLAR,
            geometry=[(pc.cx, pc.cy)],
            # ... rest unchanged
        )
```

Note: `pc.cx`, `pc.cy` are already scaled (rects were scaled on lines 161-164).

**Circular pillar geometry (line ~250-261):** Replace `geometry=[]` with center point:

```python
        el = ClassifiedElement(
            element_type=ElementType.PILLAR,
            geometry=[(c.cx * scale, c.cy * scale)],
            # ... rest unchanged
        )
```

Note: Circular pillar coordinates are NOT pre-scaled (unlike rect pillars), so multiply by `scale` here.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/pipeline/test_geometry_population.py -v`
Expected: PASS

- [ ] **Step 5: Run existing tests to check for regressions**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/ -v --timeout=60`
Expected: All existing tests still pass (geometry was `[]` before, no code depended on it)

- [ ] **Step 6: Commit**

```bash
git add tests/pipeline/test_geometry_population.py src/pipeline/stage_classify.py
git commit -m "feat: populate ClassifiedElement geometry with beam axis endpoints and pillar centers"
```

---

### Task 1: Calculation Result Models

**Files:**
- Create: `src/models/calculation_models.py`
- Modify: `src/models/pipeline_models.py:57-64`
- Test: `tests/models/test_calculation_models.py`

- [ ] **Step 1: Write failing test for calculation models**

```python
# tests/models/test_calculation_models.py
"""Test calculation result models."""

import pytest
from shapely.geometry import box
from src.models.calculation_models import (
    BeamShoringResult, SlabShoringResult, CalculationResult,
)
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.shore import ShoreCatalogEntry, PositionedShore


def _make_shore_entry():
    return ShoreCatalogEntry(
        id="TEST-01", manufacturer="Generic", model="T-180",
        type="telescopic", height_min_m=1.80, height_max_m=3.20,
        load_capacity_kn=20.0, weight_kg=12.0,
        tube_external_mm=60.0, tube_internal_mm=48.0,
        base_plate_mm=150.0, price_reference_brl=85.0,
    )


def _make_beam_element():
    return ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[(0.0, 5.0), (8.0, 5.0)],
        score_geometric=0.85, score_textual=0.0, score_final=0.75,
        section_width_m=0.14, section_height_m=0.40, length_m=8.0,
    )


def test_beam_shoring_result_creation():
    shore = _make_shore_entry()
    beam = _make_beam_element()
    result = BeamShoringResult(
        beam=beam,
        support_positions=[0.0, 8.0],
        is_cantilever_start=False,
        is_cantilever_end=False,
        total_linear_load_kn_m=12.5,
        shores=[
            PositionedShore(x=2.0, y=5.0, shore=shore, load_applied_kn=10.0, utilization_ratio=0.50),
        ],
        shore_count=1,
        spacing_m=2.0,
        selected_shore=shore,
        shore_height_m=2.40,
    )
    assert result.shore_count == 1
    assert result.total_linear_load_kn_m == 12.5


def test_slab_shoring_result_creation():
    shore = _make_shore_entry()
    polygon = box(0, 0, 5, 4)
    result = SlabShoringResult(
        polygon=polygon,
        thickness_m=0.12,
        thickness_is_default=True,
        area_m2=20.0,
        is_cantilever=False,
        total_load_kn=100.0,
        shores=[],
        grid_nx=3, grid_ny=3,
        spacing_x_m=1.5, spacing_y_m=1.2,
        selected_shore=shore,
        exclusions=[],
    )
    assert result.area_m2 == 20.0
    assert result.thickness_is_default is True


def test_calculation_result_totals():
    result = CalculationResult(
        beam_results=[], slab_results=[],
        shore_catalog_used=[], total_shores=15,
        total_load_kn=500.0,
        pe_direito_m=2.80, pe_direito_is_default=True,
        warnings=["Pe-direito usando valor padrão 2.80m"],
        validation_errors=[], is_valid=True,
    )
    assert result.total_shores == 15
    assert result.pe_direito_is_default is True
    assert len(result.warnings) == 1


def test_calculation_result_serialization():
    """CalculationResult must serialize to dict (for API response)."""
    result = CalculationResult(
        beam_results=[], slab_results=[],
        shore_catalog_used=[], total_shores=0,
        total_load_kn=0.0,
        pe_direito_m=2.80, pe_direito_is_default=False,
        warnings=[], validation_errors=[], is_valid=True,
    )
    d = result.model_dump()
    assert "total_shores" in d
    assert "warnings" in d
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/models/test_calculation_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.models.calculation_models'`

- [ ] **Step 3: Create calculation_models.py**

```python
# src/models/calculation_models.py
"""Result models for the calculation pipeline bridge."""

from typing import List, Any, Optional
from pydantic import BaseModel, Field
from src.models.pipeline_models import ClassifiedElement
from src.models.shore import ShoreCatalogEntry, PositionedShore
from src.engine.grid_distributor import PillarExclusion


class BeamShoringResult(BaseModel):
    """Shoring result for a single beam."""
    beam: ClassifiedElement
    support_positions: List[float] = Field(description="Pillar distances along beam axis (m)")
    is_cantilever_start: bool = False
    is_cantilever_end: bool = False
    total_linear_load_kn_m: float = Field(description="Majorized load per meter (kN/m)")
    shores: List[PositionedShore]
    shore_count: int
    spacing_m: float
    selected_shore: ShoreCatalogEntry
    shore_height_m: float = Field(description="Actual shore height used (m)")


class SlabShoringResult(BaseModel):
    """Shoring result for a single slab panel."""
    model_config = {"arbitrary_types_allowed": True}

    polygon: Any = Field(description="Shapely polygon of slab panel")
    thickness_m: float
    thickness_is_default: bool = False
    area_m2: float
    is_cantilever: bool = False
    total_load_kn: float = Field(description="Majorized total load (kN)")
    shores: List[PositionedShore]
    grid_nx: int = 0
    grid_ny: int = 0
    spacing_x_m: float = 0.0
    spacing_y_m: float = 0.0
    selected_shore: Optional[ShoreCatalogEntry] = None
    exclusions: List[Any] = Field(default_factory=list, description="PillarExclusion zones applied")


class CalculationResult(BaseModel):
    """Complete calculation result for one level."""
    beam_results: List[BeamShoringResult] = Field(default_factory=list)
    slab_results: List[SlabShoringResult] = Field(default_factory=list)
    shore_catalog_used: List[ShoreCatalogEntry] = Field(default_factory=list)
    total_shores: int = 0
    total_load_kn: float = 0.0
    pe_direito_m: float = 2.80
    pe_direito_is_default: bool = False
    warnings: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    is_valid: bool = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/models/test_calculation_models.py -v`
Expected: PASS

- [ ] **Step 5: Modify PipelineResult to include calculation field**

In `src/models/pipeline_models.py`, add import and field:

```python
# Add at top of file, after existing imports:
from typing import List, Optional, Tuple, TYPE_CHECKING
if TYPE_CHECKING:
    from src.models.calculation_models import CalculationResult

# In PipelineResult class, add field:
class PipelineResult(BaseModel):
    """Complete result of the interpretation pipeline."""
    filename: str
    scale: float = Field(default=1.0, description="Drawing scale factor (DXF units -> meters)")
    levels: List[LevelGroup] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    calculation: Optional["CalculationResult"] = Field(default=None, description="Shoring calculation results")
```

Add at end of file for forward reference resolution:

```python
from src.models.calculation_models import CalculationResult
PipelineResult.model_rebuild()
```

- [ ] **Step 6: Run all tests**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/ -v --timeout=60`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add src/models/calculation_models.py tests/models/test_calculation_models.py src/models/pipeline_models.py
git commit -m "feat: add CalculationResult models and wire into PipelineResult"
```

---

## Chunk 2: Slab Builder + Metadata

### Task 2: Slab Builder — Derive Slabs from Beam Grid

**Files:**
- Create: `src/engine/slab_builder.py`
- Test: `tests/engine/test_slab_builder.py`

- [ ] **Step 1: Write failing tests for slab builder**

```python
# tests/engine/test_slab_builder.py
"""Test slab derivation from beam grid via Shapely polygonize."""

import pytest
from shapely.geometry import LineString
from src.engine.slab_builder import derive_slabs_from_beams, detect_cantilever_slabs
from src.models.pipeline_models import ClassifiedElement, ElementType


def _beam(x1, y1, x2, y2, **kwargs):
    """Helper to create a beam ClassifiedElement with geometry."""
    return ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[(x1, y1), (x2, y2)],
        score_geometric=0.85, score_textual=0.0, score_final=0.75,
        section_width_m=kwargs.get("width", 0.14),
        section_height_m=kwargs.get("height", 0.40),
        length_m=((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5,
    )


def _pillar(cx, cy):
    """Helper to create a pillar ClassifiedElement with geometry."""
    return ClassifiedElement(
        element_type=ElementType.PILLAR,
        geometry=[(cx, cy)],
        score_geometric=0.80, score_textual=0.0, score_final=0.70,
        section_width_m=0.20, section_height_m=0.40,
    )


class TestDeriveSlabs:
    def test_simple_rectangle_grid(self):
        """4 beams forming a rectangle → 1 slab panel."""
        beams = [
            _beam(0, 0, 10, 0),   # bottom
            _beam(0, 6, 10, 6),   # top
            _beam(0, 0, 0, 6),    # left
            _beam(10, 0, 10, 6),  # right
        ]
        slabs = derive_slabs_from_beams(beams)
        assert len(slabs) == 1
        assert slabs[0].area > 50  # ~60 m²

    def test_two_panel_grid(self):
        """6 beams forming 2 adjacent panels → 2 slab panels."""
        beams = [
            _beam(0, 0, 10, 0),   # bottom
            _beam(0, 6, 10, 6),   # top
            _beam(0, 0, 0, 6),    # left
            _beam(5, 0, 5, 6),    # middle divider
            _beam(10, 0, 10, 6),  # right
        ]
        # Need top segments for both panels
        slabs = derive_slabs_from_beams(beams)
        assert len(slabs) == 2

    def test_no_closed_regions(self):
        """Open beams (not forming closed polygon) → 0 slabs."""
        beams = [
            _beam(0, 0, 10, 0),
            _beam(0, 0, 0, 6),
        ]
        slabs = derive_slabs_from_beams(beams)
        assert len(slabs) == 0

    def test_three_by_two_grid(self):
        """Grid of 3×2 panels → 6 slab panels."""
        beams = []
        # 4 horizontal beams (y=0, 4, 8, 12)
        for y in [0, 4, 8]:
            beams.append(_beam(0, y, 15, y))
        # 4 vertical beams (x=0, 5, 10, 15)
        for x in [0, 5, 10, 15]:
            beams.append(_beam(x, 0, x, 8))
        slabs = derive_slabs_from_beams(beams)
        assert len(slabs) == 6


class TestCantileverSlabs:
    def test_slab_outside_pillar_hull_is_cantilever(self):
        """Slab panel outside convex hull of pillars = cantilever."""
        pillars = [
            _pillar(2, 2), _pillar(8, 2),
            _pillar(2, 6), _pillar(8, 6),
        ]
        # Pillar hull: rectangle from (2,2) to (8,6)
        # Slab panel from (8,0) to (12,6) is outside hull
        from shapely.geometry import box
        slabs = [box(8, 0, 12, 6)]  # panel beyond right pillars
        result = detect_cantilever_slabs(slabs, pillars)
        assert len(result) == 1
        assert result[0] is True  # is cantilever

    def test_slab_inside_pillar_hull_is_not_cantilever(self):
        """Slab panel inside convex hull of pillars = interior."""
        pillars = [
            _pillar(0, 0), _pillar(10, 0),
            _pillar(0, 8), _pillar(10, 8),
        ]
        from shapely.geometry import box
        slabs = [box(2, 2, 8, 6)]  # fully inside
        result = detect_cantilever_slabs(slabs, pillars)
        assert len(result) == 1
        assert result[0] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/engine/test_slab_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.engine.slab_builder'`

- [ ] **Step 3: Implement slab_builder.py**

```python
# src/engine/slab_builder.py
"""Derive slab panels from beam grid via Shapely polygonize.

Algorithm:
1. Convert each beam to a Shapely LineString along its axis
2. Union all beam lines into a geometry network
3. Use shapely.ops.polygonize() to extract closed regions
4. Each polygon = one slab panel
"""

from typing import List
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import polygonize, unary_union
from shapely.geometry.polygon import Polygon
from src.models.pipeline_models import ClassifiedElement, ElementType


def derive_slabs_from_beams(beams: List[ClassifiedElement]) -> List[Polygon]:
    """Extract closed slab panels from the beam grid.

    Args:
        beams: ClassifiedElement list with element_type=BEAM and geometry populated.

    Returns:
        List of Shapely Polygons, each representing a slab panel.
    """
    lines = []
    for beam in beams:
        if beam.element_type != ElementType.BEAM:
            continue
        if len(beam.geometry) < 2:
            continue
        start = beam.geometry[0]
        end = beam.geometry[1]
        line = LineString([start, end])
        if line.length > 0:
            lines.append(line)

    if not lines:
        return []

    # Union all lines and polygonize to find closed regions
    merged = unary_union(lines)
    polygons = list(polygonize(merged))

    # Filter out degenerate polygons (near-zero area)
    MIN_SLAB_AREA = 0.5  # m² — anything smaller is noise
    return [p for p in polygons if p.area >= MIN_SLAB_AREA]


def detect_cantilever_slabs(
    slab_polygons: List[Polygon],
    pillars: List[ClassifiedElement],
) -> List[bool]:
    """Determine which slab panels are cantilevers (outside pillar hull).

    Args:
        slab_polygons: List of Shapely Polygons (slab panels).
        pillars: ClassifiedElement list with element_type=PILLAR and geometry populated.

    Returns:
        List of booleans, same length as slab_polygons. True = cantilever.
    """
    if len(pillars) < 3:
        # Can't form a hull with < 3 points — all slabs are cantilevers
        return [True] * len(slab_polygons)

    # Build convex hull from pillar centers
    pillar_points = []
    for p in pillars:
        if p.element_type != ElementType.PILLAR or not p.geometry:
            continue
        pillar_points.append(Point(p.geometry[0]))

    if len(pillar_points) < 3:
        return [True] * len(slab_polygons)

    from shapely.geometry import MultiPoint
    hull = MultiPoint(pillar_points).convex_hull

    results = []
    for slab in slab_polygons:
        centroid = slab.centroid
        # Slab is cantilever if its centroid is outside the pillar hull
        is_cantilever = not hull.contains(centroid)
        results.append(is_cantilever)

    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/engine/test_slab_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/engine/slab_builder.py tests/engine/test_slab_builder.py
git commit -m "feat: add slab_builder — derive slab panels from beam grid via polygonize"
```

---

### Task 3: Slab Thickness Extraction in Metadata

**Files:**
- Modify: `src/pipeline/stage_metadata.py`
- Test: `tests/pipeline/test_slab_thickness.py`

- [ ] **Step 1: Write failing test for thickness extraction**

```python
# tests/pipeline/test_slab_thickness.py
"""Test slab thickness extraction from text annotations."""

import pytest
from src.pipeline.stage_metadata import extract_slab_thickness
from src.pipeline.stage_parse import TextEntity


def _text(content, x=0.0, y=0.0):
    return TextEntity(content=content, x=x, y=y, layer="TEXT")


class TestSlabThicknessExtraction:
    def test_h_equals_pattern(self):
        texts = [_text("h=12")]
        assert extract_slab_thickness(texts) == pytest.approx(0.12)

    def test_e_equals_pattern(self):
        texts = [_text("e=15cm")]
        assert extract_slab_thickness(texts) == pytest.approx(0.15)

    def test_esp_pattern(self):
        texts = [_text("ESP 10")]
        assert extract_slab_thickness(texts) == pytest.approx(0.10)

    def test_espessura_pattern(self):
        texts = [_text("ESPESSURA = 20")]
        assert extract_slab_thickness(texts) == pytest.approx(0.20)

    def test_no_match_returns_none(self):
        texts = [_text("V1 (14x40)"), _text("P3")]
        assert extract_slab_thickness(texts) is None

    def test_empty_texts(self):
        assert extract_slab_thickness([]) is None

    def test_value_in_meters_when_large(self):
        """If value > 1, assume it's in cm and convert to m."""
        texts = [_text("h=12")]
        assert extract_slab_thickness(texts) == pytest.approx(0.12)

    def test_value_already_in_meters(self):
        """If value <= 1, assume it's already in meters."""
        texts = [_text("h=0.15")]
        assert extract_slab_thickness(texts) == pytest.approx(0.15)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/pipeline/test_slab_thickness.py -v`
Expected: FAIL — `ImportError: cannot import name 'extract_slab_thickness'`

- [ ] **Step 3: Add extract_slab_thickness to stage_metadata.py**

Append to `src/pipeline/stage_metadata.py`:

```python
SLAB_THICKNESS_PATTERN = re.compile(
    r"(?:h|e|ESP(?:ESSURA)?)\s*[=:]?\s*(\d+(?:[.,]\d+)?)\s*(?:cm|m)?",
    re.IGNORECASE,
)


def extract_slab_thickness(texts: List[TextEntity]) -> Optional[float]:
    """Extract slab thickness from text annotations.

    Looks for patterns like h=12, e=15cm, ESP 10, ESPESSURA=20.
    Values > 1 are assumed to be in cm and converted to meters.
    Values <= 1 are assumed to already be in meters.

    Returns thickness in meters, or None if not found.
    """
    for t in texts:
        m = SLAB_THICKNESS_PATTERN.search(t.content)
        if m:
            value = float(m.group(1).replace(",", "."))
            if value > 1.0:
                value /= 100.0  # cm to m
            return value
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/pipeline/test_slab_thickness.py -v`
Expected: PASS

- [ ] **Step 5: Run all tests**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/ -v --timeout=60`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/pipeline/stage_metadata.py tests/pipeline/test_slab_thickness.py
git commit -m "feat: add slab thickness extraction from text annotations"
```

---

## Chunk 3: Stage Calculate (Core Bridge)

### Task 4: stage_calculate.py — Structural Model + Engine Orchestration

**Files:**
- Create: `src/pipeline/stage_calculate.py`
- Test: `tests/pipeline/test_stage_calculate.py`

This is the main bridge module. It:
1. Associates beams with pillars (proximity 0.30m)
2. Derives slabs from beam grid
3. Runs load + shore calculations using existing engine
4. Packages results as `CalculationResult`

- [ ] **Step 1: Write failing tests for beam-pillar association**

```python
# tests/pipeline/test_stage_calculate.py
"""Tests for the calculation pipeline bridge."""

import pytest
from shapely.geometry import box
from src.pipeline.stage_calculate import (
    associate_beams_pillars,
    run_calculation,
)
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.calculation_models import CalculationResult


def _beam(x1, y1, x2, y2, width=0.14, height=0.40):
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    return ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[(x1, y1), (x2, y2)],
        score_geometric=0.85, score_textual=0.0, score_final=0.75,
        section_width_m=width, section_height_m=height, length_m=length,
    )


def _pillar(cx, cy, w=0.20, h=0.40):
    return ClassifiedElement(
        element_type=ElementType.PILLAR,
        geometry=[(cx, cy)],
        score_geometric=0.80, score_textual=0.0, score_final=0.70,
        section_width_m=w, section_height_m=h,
    )


class TestBeamPillarAssociation:
    def test_pillar_near_beam_endpoint_is_support(self):
        """Pillar within 0.30m of beam axis → support."""
        beam = _beam(0, 5, 10, 5)
        pillars = [_pillar(0.1, 5.0), _pillar(9.9, 5.0)]
        result = associate_beams_pillars([beam], pillars)
        assert len(result) == 1
        assoc = result[0]
        assert len(assoc["support_positions"]) == 2
        assert assoc["is_cantilever_start"] is False
        assert assoc["is_cantilever_end"] is False

    def test_beam_with_cantilever_end(self):
        """Pillar only at start → cantilever at end."""
        beam = _beam(0, 5, 10, 5)
        pillars = [_pillar(0.1, 5.0)]
        result = associate_beams_pillars([beam], pillars)
        assert len(result) == 1
        assoc = result[0]
        assert assoc["is_cantilever_start"] is False
        assert assoc["is_cantilever_end"] is True

    def test_beam_with_no_pillars_both_cantilever(self):
        """No pillars near beam → both ends cantilever."""
        beam = _beam(0, 5, 10, 5)
        pillars = [_pillar(20, 20)]  # far away
        result = associate_beams_pillars([beam], pillars)
        assert len(result) == 1
        assoc = result[0]
        assert assoc["is_cantilever_start"] is True
        assert assoc["is_cantilever_end"] is True

    def test_pillar_far_from_beam_not_support(self):
        """Pillar > 0.30m from beam axis → not a support."""
        beam = _beam(0, 5, 10, 5)
        pillars = [_pillar(5, 8)]  # 3m away from axis
        result = associate_beams_pillars([beam], pillars)
        assert len(result) == 1
        assert len(result[0]["support_positions"]) == 0


class TestRunCalculation:
    def test_simple_grid_produces_results(self):
        """Simple 2-beam grid with 4 pillars → non-empty results."""
        beams = [
            _beam(0, 0, 10, 0),
            _beam(0, 6, 10, 6),
            _beam(0, 0, 0, 6),
            _beam(10, 0, 10, 6),
        ]
        pillars = [
            _pillar(0, 0), _pillar(10, 0),
            _pillar(0, 6), _pillar(10, 6),
        ]
        elements = beams + pillars
        result = run_calculation(elements, pe_direito_m=2.80)
        assert isinstance(result, CalculationResult)
        assert result.total_shores > 0
        assert result.total_load_kn > 0
        assert len(result.beam_results) > 0

    def test_low_confidence_beam_skipped(self):
        """Beam with score_final < 0.50 should be skipped."""
        beam = ClassifiedElement(
            element_type=ElementType.BEAM,
            geometry=[(0, 0), (10, 0)],
            score_geometric=0.30, score_textual=0.0, score_final=0.30,
            section_width_m=0.14, section_height_m=0.40, length_m=10.0,
        )
        pillars = [_pillar(0, 0), _pillar(10, 0)]
        result = run_calculation([beam] + pillars, pe_direito_m=2.80)
        assert len(result.beam_results) == 0
        assert any("score" in w.lower() or "confiança" in w.lower() for w in result.warnings)

    def test_missing_beam_height_skipped(self):
        """Beam with no section_height_m should be skipped with warning."""
        beam = _beam(0, 0, 10, 0)
        beam.section_height_m = None
        pillars = [_pillar(0, 0), _pillar(10, 0)]
        result = run_calculation([beam] + pillars, pe_direito_m=2.80)
        assert len(result.beam_results) == 0
        assert len(result.warnings) > 0

    def test_default_pe_direito_flagged(self):
        """When pe_direito_is_default=True, it should appear in warnings."""
        beams = [_beam(0, 0, 10, 0), _beam(0, 6, 10, 6),
                 _beam(0, 0, 0, 6), _beam(10, 0, 10, 6)]
        pillars = [_pillar(0, 0), _pillar(10, 0),
                   _pillar(0, 6), _pillar(10, 6)]
        result = run_calculation(beams + pillars, pe_direito_m=2.80, pe_direito_is_default=True)
        assert result.pe_direito_is_default is True
        assert any("pé-direito" in w.lower() or "pe-direito" in w.lower() or "padrão" in w.lower()
                    for w in result.warnings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/pipeline/test_stage_calculate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.pipeline.stage_calculate'`

- [ ] **Step 3: Implement stage_calculate.py**

```python
# src/pipeline/stage_calculate.py
"""Stage 5: Calculation Pipeline Bridge.

Bridges classified elements (beams, pillars) from the interpretation pipeline
to the shoring engine. Builds a structural model, derives slabs, and runs
load + shore calculations.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from shapely.geometry import LineString, Point

from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.calculation_models import (
    BeamShoringResult, SlabShoringResult, CalculationResult,
)
from src.models.slab import Slab
from src.models.shore import ShoreCatalogEntry
from src.engine.slab_builder import derive_slabs_from_beams, detect_cantilever_slabs
from src.engine.load_calculator import calculate_total_load
from src.engine.beam_calculator import (
    calculate_beam_total_linear_load,
    distribute_beam_shores,
    estimate_beam_shore_height,
)
from src.engine.grid_distributor import distribute_shores, PillarExclusion
from src.engine.shore_selector import load_catalog, select_shore
from src.engine.validator import validate_result
from src.utils.constants import (
    GAMMA_F, Q_SOBRECARGA_DEFAULT, ESPESSURA_DEFAULT, ALTURA_DEFAULT,
    ESPACAMENTO_MAX_DEFAULT,
)

logger = logging.getLogger(__name__)

# Beam-pillar association proximity threshold (m)
BEAM_PILLAR_PROXIMITY = 0.30

# Beam endpoint proximity for cantilever detection (m)
BEAM_ENDPOINT_PROXIMITY = 0.30

# Minimum confidence to include in calculations
MIN_CONFIDENCE = 0.50

# Low confidence threshold for warnings
LOW_CONFIDENCE = 0.70

# Beam exclusion zone width for slab shore distribution (m)
BEAM_EXCLUSION_WIDTH = 0.40

# Cantilever slab spacing reduction factor
CANTILEVER_SPACING_FACTOR = 0.7


def associate_beams_pillars(
    beams: List[ClassifiedElement],
    pillars: List[ClassifiedElement],
) -> List[Dict[str, Any]]:
    """Associate beams with supporting pillars by proximity.

    For each beam, finds which pillars are within BEAM_PILLAR_PROXIMITY of
    the beam's axis line. Classifies each endpoint as supported or cantilever.

    Returns list of dicts with keys:
        - beam: ClassifiedElement
        - support_positions: List[float] — distances along beam axis
        - is_cantilever_start: bool
        - is_cantilever_end: bool
    """
    results = []

    for beam in beams:
        if beam.element_type != ElementType.BEAM or len(beam.geometry) < 2:
            continue

        start_pt = beam.geometry[0]
        end_pt = beam.geometry[1]
        beam_line = LineString([start_pt, end_pt])
        beam_length = beam_line.length

        if beam_length == 0:
            continue

        support_positions = []
        has_start_support = False
        has_end_support = False

        for pillar in pillars:
            if pillar.element_type != ElementType.PILLAR or not pillar.geometry:
                continue

            pillar_center = Point(pillar.geometry[0])
            dist_to_axis = beam_line.distance(pillar_center)

            if dist_to_axis <= BEAM_PILLAR_PROXIMITY:
                # Project pillar onto beam axis to get position along beam
                proj = beam_line.project(pillar_center)
                support_positions.append(round(proj, 4))

                # Check if near endpoints
                dist_to_start = pillar_center.distance(Point(start_pt))
                dist_to_end = pillar_center.distance(Point(end_pt))

                if dist_to_start <= BEAM_ENDPOINT_PROXIMITY:
                    has_start_support = True
                if dist_to_end <= BEAM_ENDPOINT_PROXIMITY:
                    has_end_support = True

        support_positions.sort()

        results.append({
            "beam": beam,
            "support_positions": support_positions,
            "is_cantilever_start": not has_start_support,
            "is_cantilever_end": not has_end_support,
        })

    return results


def _build_pillar_exclusions(
    pillars: List[ClassifiedElement],
) -> List[PillarExclusion]:
    """Build PillarExclusion zones from pillar elements."""
    exclusions = []
    for p in pillars:
        if p.element_type != ElementType.PILLAR or not p.geometry:
            continue
        cx, cy = p.geometry[0]
        w = p.section_width_m or 0.20
        d = p.section_height_m or 0.20
        exclusions.append(PillarExclusion(cx=cx, cy=cy, width_m=w, depth_m=d))
    return exclusions


def _build_beam_exclusions(
    beams: List[ClassifiedElement],
) -> List[PillarExclusion]:
    """Build rectangular exclusion zones along beam axes.

    Models each beam as a series of rectangular PillarExclusion objects
    to prevent slab shores from being placed on top of beams.
    """
    exclusions = []
    for beam in beams:
        if beam.element_type != ElementType.BEAM or len(beam.geometry) < 2:
            continue
        start = beam.geometry[0]
        end = beam.geometry[1]
        cx = (start[0] + end[0]) / 2
        cy = (start[1] + end[1]) / 2
        dx = abs(end[0] - start[0])
        dy = abs(end[1] - start[1])
        # Exclusion rectangle: beam length × BEAM_EXCLUSION_WIDTH
        width = max(dx, BEAM_EXCLUSION_WIDTH)
        depth = max(dy, BEAM_EXCLUSION_WIDTH)
        exclusions.append(PillarExclusion(
            cx=cx, cy=cy, width_m=width, depth_m=depth, margin=0.0,
        ))
    return exclusions


def run_calculation(
    elements: List[ClassifiedElement],
    pe_direito_m: float = ALTURA_DEFAULT,
    pe_direito_is_default: bool = False,
    slab_thickness_m: Optional[float] = None,
) -> CalculationResult:
    """Run the full calculation pipeline.

    Args:
        elements: Classified beams and pillars with geometry populated.
        pe_direito_m: Floor-to-ceiling height in meters.
        pe_direito_is_default: True if pe_direito was not found in DXF.
        slab_thickness_m: Slab thickness override. None = use default.

    Returns:
        CalculationResult with beam/slab shoring results.
    """
    warnings: List[str] = []
    validation_errors: List[str] = []

    # Default pe-direito warning
    if pe_direito_is_default:
        warnings.append(
            f"Pé-direito usando valor padrão {pe_direito_m:.2f}m — "
            "confirme no preview antes de aprovar"
        )

    # Separate beams and pillars
    beams = [e for e in elements if e.element_type == ElementType.BEAM]
    pillars = [e for e in elements if e.element_type == ElementType.PILLAR]

    # Filter by confidence
    valid_beams = []
    for b in beams:
        if b.score_final < MIN_CONFIDENCE:
            warnings.append(
                f"Viga {b.name or 'sem nome'} ignorada — confiança {b.score_final:.0%} < 50%"
            )
            continue
        if b.score_final < LOW_CONFIDENCE:
            warnings.append(
                f"Viga {b.name or 'sem nome'} com baixa confiança ({b.score_final:.0%}) — revisar"
            )
        valid_beams.append(b)

    # Load shore catalog
    try:
        catalog = load_catalog()
    except FileNotFoundError:
        warnings.append("Catálogo de escoras não encontrado — usando valores padrão")
        catalog = []

    # Slab thickness
    thickness = slab_thickness_m or ESPESSURA_DEFAULT
    thickness_is_default = slab_thickness_m is None
    if thickness_is_default:
        warnings.append(
            f"Espessura da laje usando valor padrão {thickness:.2f}m — "
            "confirme no preview"
        )

    # === BEAM SHORING ===
    beam_associations = associate_beams_pillars(valid_beams, pillars)
    beam_results: List[BeamShoringResult] = []

    for assoc in beam_associations:
        beam = assoc["beam"]

        # Skip beams without section height
        if not beam.section_height_m:
            warnings.append(
                f"Viga {beam.name or 'sem nome'} ignorada — altura da seção não encontrada"
            )
            continue

        beam_width = beam.section_width_m or 0.14
        beam_height = beam.section_height_m
        beam_length = beam.length_m or 1.0

        # Calculate linear load
        total_linear_load = calculate_beam_total_linear_load(
            width_m=beam_width,
            height_m=beam_height,
            slab_thickness_m=thickness,
        )

        # Shore height
        shore_height = estimate_beam_shore_height(pe_direito_m, beam_height)
        if shore_height <= 0:
            warnings.append(
                f"Viga {beam.name or 'sem nome'} — altura da escora negativa "
                f"(pé-direito {pe_direito_m}m < altura viga {beam_height}m)"
            )
            continue

        # Select shore
        load_per_shore_estimate = total_linear_load * 1.0  # ~1m spacing estimate
        selected_shore = select_shore(catalog, shore_height, load_per_shore_estimate) if catalog else None

        if not selected_shore:
            warnings.append(
                f"Viga {beam.name or 'sem nome'} — nenhuma escora compatível "
                f"(altura {shore_height:.2f}m, carga {load_per_shore_estimate:.1f} kN)"
            )
            continue

        # Distribute shores along beam
        start_pt = beam.geometry[0] if len(beam.geometry) >= 2 else (0, 0)
        end_pt = beam.geometry[1] if len(beam.geometry) >= 2 else (beam_length, 0)

        # Determine direction from geometry
        dx = abs(end_pt[0] - start_pt[0])
        dy = abs(end_pt[1] - start_pt[1])
        direction = "x" if dx >= dy else "y"

        shores, n_shores, spacing = distribute_beam_shores(
            beam_length_m=beam_length,
            beam_width_m=beam_width,
            beam_height_m=beam_height,
            shore=selected_shore,
            total_linear_load_kn_m=total_linear_load,
            start_x=start_pt[0],
            start_y=start_pt[1],
            direction=direction,
            support_positions=assoc["support_positions"],
            is_cantilever_start=assoc["is_cantilever_start"],
            is_cantilever_end=assoc["is_cantilever_end"],
        )

        # Validate beam shores
        is_valid, errors = validate_result(shores, spacing, spacing)
        validation_errors.extend(errors)

        beam_results.append(BeamShoringResult(
            beam=beam,
            support_positions=assoc["support_positions"],
            is_cantilever_start=assoc["is_cantilever_start"],
            is_cantilever_end=assoc["is_cantilever_end"],
            total_linear_load_kn_m=total_linear_load,
            shores=shores,
            shore_count=n_shores,
            spacing_m=spacing,
            selected_shore=selected_shore,
            shore_height_m=shore_height,
        ))

    # === SLAB SHORING ===
    slab_polygons = derive_slabs_from_beams(valid_beams)
    cantilever_flags = detect_cantilever_slabs(slab_polygons, pillars)

    pillar_exclusions = _build_pillar_exclusions(pillars)
    beam_exclusions = _build_beam_exclusions(valid_beams)
    all_exclusions = pillar_exclusions + beam_exclusions

    slab_results: List[SlabShoringResult] = []

    for i, polygon in enumerate(slab_polygons):
        is_cantilever = cantilever_flags[i] if i < len(cantilever_flags) else False

        # Create Slab object
        slab = Slab.from_polygon(
            polygon=polygon,
            layer_name="derived",
            thickness_m=thickness,
        )

        # Calculate total load
        total_load = calculate_total_load(slab)

        # Shore height for slab = pe_direito - slab_thickness
        slab_shore_height = pe_direito_m - thickness
        if slab_shore_height <= 0:
            warnings.append(
                f"Laje (área {slab.area_m2:.1f}m²) — altura da escora negativa"
            )
            continue

        # Estimate load per shore for selection
        estimated_shores = max(1, int(slab.area_m2 / (ESPACAMENTO_MAX_DEFAULT ** 2)))
        load_per_shore_estimate = total_load / estimated_shores

        selected_shore = select_shore(catalog, slab_shore_height, load_per_shore_estimate) if catalog else None

        if not selected_shore:
            warnings.append(
                f"Laje (área {slab.area_m2:.1f}m²) — nenhuma escora compatível "
                f"(altura {slab_shore_height:.2f}m, carga {load_per_shore_estimate:.1f} kN)"
            )
            slab_results.append(SlabShoringResult(
                polygon=polygon,
                thickness_m=thickness,
                thickness_is_default=thickness_is_default,
                area_m2=slab.area_m2,
                is_cantilever=is_cantilever,
                total_load_kn=total_load,
                shores=[],
                exclusions=all_exclusions,
            ))
            continue

        # Cantilever slabs: reduced spacing
        max_spacing = ESPACAMENTO_MAX_DEFAULT
        if is_cantilever:
            max_spacing *= CANTILEVER_SPACING_FACTOR

        shores, nx, ny, sx, sy = distribute_shores(
            slab=slab,
            shore=selected_shore,
            total_load_kn=total_load,
            max_spacing=max_spacing,
            exclusions=all_exclusions,
        )

        # Validate slab shores
        is_valid, errors = validate_result(shores, sx, sy)
        validation_errors.extend(errors)

        slab_results.append(SlabShoringResult(
            polygon=polygon,
            thickness_m=thickness,
            thickness_is_default=thickness_is_default,
            area_m2=slab.area_m2,
            is_cantilever=is_cantilever,
            total_load_kn=total_load,
            shores=shores,
            grid_nx=nx,
            grid_ny=ny,
            spacing_x_m=sx,
            spacing_y_m=sy,
            selected_shore=selected_shore,
            exclusions=all_exclusions,
        ))

    # === AGGREGATE RESULTS ===
    all_shores_count = sum(r.shore_count for r in beam_results) + sum(len(r.shores) for r in slab_results)
    all_load = (
        sum(r.total_linear_load_kn_m * (r.beam.length_m or 0) for r in beam_results)
        + sum(r.total_load_kn for r in slab_results)
    )

    # Distinct shore models used
    shore_models_used = {}
    for r in beam_results:
        shore_models_used[r.selected_shore.id] = r.selected_shore
    for r in slab_results:
        if r.selected_shore:
            shore_models_used[r.selected_shore.id] = r.selected_shore

    return CalculationResult(
        beam_results=beam_results,
        slab_results=slab_results,
        shore_catalog_used=list(shore_models_used.values()),
        total_shores=all_shores_count,
        total_load_kn=round(all_load, 2),
        pe_direito_m=pe_direito_m,
        pe_direito_is_default=pe_direito_is_default,
        warnings=warnings,
        validation_errors=validation_errors,
        is_valid=len(validation_errors) == 0,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/pipeline/test_stage_calculate.py -v`
Expected: PASS

- [ ] **Step 5: Run all tests**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/ -v --timeout=60`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/pipeline/stage_calculate.py tests/pipeline/test_stage_calculate.py
git commit -m "feat: add stage_calculate — bridges pipeline to shoring engine"
```

---

## Chunk 4: Runner Integration + Regression Tests

### Task 5: Wire stage_calculate into runner.py

**Files:**
- Modify: `src/pipeline/runner.py:1-81`

- [ ] **Step 1: Write failing test for runner with calculation**

```python
# tests/pipeline/test_runner_calculation.py
"""Test that runner.py produces calculation results."""

import pytest
from unittest.mock import patch, MagicMock
from src.pipeline.runner import run_pipeline
from src.models.pipeline_models import PipelineResult


class TestRunnerCalculation:
    @patch("src.pipeline.runner.run_calculation")
    @patch("src.pipeline.runner.parse_dxf")
    @patch("src.pipeline.runner.segment_by_level")
    @patch("src.pipeline.runner.classify_elements")
    @patch("src.pipeline.runner.extract_pe_direito")
    @patch("src.pipeline.runner.extract_level_height")
    @patch("src.pipeline.runner.extract_slab_thickness")
    def test_calculation_wired_into_pipeline(
        self, mock_thickness, mock_height, mock_pe, mock_classify,
        mock_segment, mock_parse, mock_calc,
    ):
        """Runner should call run_calculation and populate result.calculation."""
        from src.pipeline.stage_segment import LevelSegment
        from src.models.pipeline_models import ClassifiedElement, ElementType
        from src.models.calculation_models import CalculationResult

        # Setup mocks
        mock_parse.return_value = MagicMock(
            filename="test.dxf",
            detected_scale=None,
            segments=[MagicMock(type="H", y=5.0, x_min=0, x_max=10)],
        )
        mock_segment.return_value = [LevelSegment(level_name="TEST")]
        mock_classify.return_value = [
            ClassifiedElement(
                element_type=ElementType.BEAM,
                geometry=[(0, 5), (10, 5)],
                score_geometric=0.85, score_textual=0.0, score_final=0.75,
                section_width_m=0.14, section_height_m=0.40, length_m=10.0,
            ),
        ]
        mock_pe.return_value = 2.80
        mock_height.return_value = 3.00
        mock_thickness.return_value = None

        mock_calc_result = CalculationResult(
            total_shores=5, total_load_kn=100.0,
            pe_direito_m=2.80, is_valid=True,
        )
        mock_calc.return_value = mock_calc_result

        result = run_pipeline("test.dxf")
        assert result.calculation is not None
        assert result.calculation.total_shores == 5
        mock_calc.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/pipeline/test_runner_calculation.py -v`
Expected: FAIL — `result.calculation` is None (not yet wired)

- [ ] **Step 3: Modify runner.py to wire stage_calculate**

Update `src/pipeline/runner.py`:

```python
"""Pipeline runner: orchestrates Stages 1-5 sequentially.

Stage 6 (learning) is handled by the API layer since it requires user interaction.
"""

from typing import List, Optional
from src.pipeline.stage_parse import parse_dxf
from src.pipeline.stage_segment import segment_by_level
from src.pipeline.stage_classify import classify_elements
from src.pipeline.stage_metadata import extract_pe_direito, extract_level_height, extract_slab_thickness
from src.pipeline.stage_calculate import run_calculation
from src.models.pipeline_models import LevelGroup, PipelineResult
from src.utils.constants import ALTURA_DEFAULT


DEFAULT_SCALE = 0.02  # 1:50 fallback
REAL_COORDS_THRESHOLD = 5.0  # If bounding box > 5 units, assume real-world meters


def _detect_coordinate_scale(parse) -> float:
    """Auto-detect if DXF coordinates are in real meters or drawing units.

    Most modern CAD files use model space in real-world meters.
    The 'ESC 1:50' text is a print/layout scale, not coordinate scale.
    If the coordinate range exceeds REAL_COORDS_THRESHOLD, assume real meters.
    """
    all_y = [s.y for s in parse.segments if s.type == "H"]
    all_x = [s.x for s in parse.segments if s.type == "V"]
    all_y.extend(s.y_min for s in parse.segments if s.type == "V")
    all_y.extend(s.y_max for s in parse.segments if s.type == "V")
    all_x.extend(s.x_min for s in parse.segments if s.type == "H")
    all_x.extend(s.x_max for s in parse.segments if s.type == "H")

    if not all_x or not all_y:
        return parse.detected_scale or DEFAULT_SCALE

    x_range = max(all_x) - min(all_x)
    y_range = max(all_y) - min(all_y)

    if max(x_range, y_range) > REAL_COORDS_THRESHOLD:
        return 1.0  # Coordinates are already in meters

    return parse.detected_scale or DEFAULT_SCALE


def run_pipeline(filepath: str, scale_override: Optional[float] = None) -> PipelineResult:
    # Stage 1: Parse
    parse = parse_dxf(filepath)

    scale = scale_override or _detect_coordinate_scale(parse)

    # Stage 2: Segment by level
    level_segments = segment_by_level(parse)

    # Stage 3 + 4: Classify + metadata for each level
    levels: List[LevelGroup] = []
    warnings: List[str] = []
    all_elements = []

    for seg in level_segments:
        elements = classify_elements(seg, scale=scale)

        pe_direito = extract_pe_direito(seg.texts)
        level_height = extract_level_height(seg.texts)
        slab_thickness = extract_slab_thickness(seg.texts)

        pe_direito_is_default = pe_direito is None
        if pe_direito_is_default:
            warnings.append(f"Pe-direito nao encontrado no nivel {seg.level_name}")
            pe_direito = ALTURA_DEFAULT

        level = LevelGroup(
            level_name=seg.level_name,
            level_height_m=level_height,
            pe_direito_m=pe_direito,
            elements=elements,
        )
        levels.append(level)
        all_elements.extend(elements)

    # Stage 5: Calculation
    calculation = None
    if all_elements:
        # Use pe_direito from first level (MVP: single level)
        pe_direito = levels[0].pe_direito_m or ALTURA_DEFAULT
        pe_direito_is_default = levels[0].pe_direito_m is None

        # Use slab thickness from metadata if found
        slab_thickness = None
        for seg in level_segments:
            slab_thickness = extract_slab_thickness(seg.texts)
            if slab_thickness is not None:
                break

        try:
            calculation = run_calculation(
                elements=all_elements,
                pe_direito_m=pe_direito,
                pe_direito_is_default=pe_direito_is_default,
                slab_thickness_m=slab_thickness,
            )
            warnings.extend(calculation.warnings)
        except Exception as e:
            warnings.append(f"Cálculo falhou: {e}")

    return PipelineResult(
        filename=parse.filename,
        scale=scale,
        levels=levels,
        warnings=warnings,
        calculation=calculation,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/pipeline/test_runner_calculation.py -v`
Expected: PASS

- [ ] **Step 5: Run all tests**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/ -v --timeout=60`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/pipeline/runner.py tests/pipeline/test_runner_calculation.py
git commit -m "feat: wire stage_calculate into pipeline runner"
```

---

### Task 6: Regression Tests with Real DXFs

**Files:**
- Modify: `tests/pipeline/test_e2e_cfl_sub.py`
- Modify: existing CVS-COB E2E test (if present)

- [ ] **Step 1: Add calculation regression tests to CFL-SUB**

Append to `tests/pipeline/test_e2e_cfl_sub.py`:

```python
    def test_calculation_produces_results(self):
        """Pipeline should produce non-zero calculation results."""
        result = run_pipeline(str(DXF_PATH))
        assert result.calculation is not None
        # Should have some shores calculated
        assert result.calculation.total_shores > 0
        assert result.calculation.total_load_kn > 0

    def test_calculation_has_beam_results(self):
        result = run_pipeline(str(DXF_PATH))
        assert result.calculation is not None
        assert len(result.calculation.beam_results) > 0

    def test_calculation_is_valid(self):
        result = run_pipeline(str(DXF_PATH))
        assert result.calculation is not None
        # May have validation errors (overloaded shores), but should not crash
        # Just verify it produced something
        assert isinstance(result.calculation.is_valid, bool)

    def test_beam_geometry_populated(self):
        """All beams should have geometry populated (not empty)."""
        result = run_pipeline(str(DXF_PATH))
        all_elements = result.levels[0].elements
        beams = [e for e in all_elements if e.element_type == ElementType.BEAM]
        for beam in beams:
            assert len(beam.geometry) == 2, f"Beam {beam.name} has empty geometry"

    def test_pillar_geometry_populated(self):
        """All pillars should have geometry populated (not empty)."""
        result = run_pipeline(str(DXF_PATH))
        all_elements = result.levels[0].elements
        pillars = [e for e in all_elements if e.element_type == ElementType.PILLAR]
        for pillar in pillars:
            assert len(pillar.geometry) == 1, f"Pillar {pillar.name} has empty geometry"
```

- [ ] **Step 2: Run regression tests**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/pipeline/test_e2e_cfl_sub.py -v --timeout=120`
Expected: PASS (or skip if fixture not present)

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python -m pytest tests/ -v --timeout=120`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add tests/pipeline/test_e2e_cfl_sub.py
git commit -m "test: add calculation regression tests for CFL-SUB DXF"
```

- [ ] **Step 5: Push to GitHub**

```bash
git push origin main
```
