# Escora.AI Fase 1 — MVP Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the hardcoded CLI prototype into a generic DXF interpretation engine exposed via FastAPI, with a Next.js frontend for upload, preview, and download.

**Architecture:** Python engine pipeline (parse → segment → classify → extract metadata → calculate → generate outputs) served by FastAPI with background job processing (ARQ/Redis). Next.js frontend consumes REST API. Single-tenant MVP for one pilot customer (locadora).

**Tech Stack:** Python 3.14, FastAPI, ARQ (Redis), ezdxf, Shapely, Pydantic v2, Next.js 15, React, PostgreSQL, Supabase Auth

**Spec:** `docs/superpowers/specs/2026-03-25-escora-ai-saas-design.md`

---

## File Structure

### Engine Pipeline (Python — `src/`)

```
src/
├── pipeline/
│   ├── __init__.py
│   ├── runner.py              # Orchestrates all pipeline stages sequentially
│   ├── stage_parse.py         # Stage 1: Raw DXF entity extraction
│   ├── stage_segment.py       # Stage 2: Level/floor segmentation
│   ├── stage_classify.py      # Stage 3: Geometric + textual classification
│   ├── stage_metadata.py      # Stage 4: Section/thickness/level extraction
│   ├── stage_validate.py      # Stage 5: Validation + preview data generation
│   └── stage_learning.py      # Stage 6: Persist operator corrections
├── models/
│   ├── slab.py                # (exists) Slab model
│   ├── shore.py               # (exists) Shore models
│   ├── project.py             # (exists, modify) Add beam/pillar result models
│   ├── pipeline_models.py     # NEW: RawEntity, ClassifiedElement, PipelineResult
│   └── confidence.py          # NEW: Confidence score calculation
├── engine/
│   ├── load_calculator.py     # (exists) Slab loads
│   ├── beam_calculator.py     # (exists) Beam loads + shore distribution
│   ├── grid_distributor.py    # (exists) Slab shore distribution
│   ├── shore_selector.py      # (exists) Shore model selection
│   ├── validator.py           # (exists) Result validation
│   └── optimizer.py           # NEW: Multi-strategy optimization
├── parser/
│   ├── dxf_reader.py          # (exists, modify) Add generic entity extraction
│   ├── geometry_extractor.py  # (exists) Polygon extraction
│   ├── metadata_extractor.py  # (exists, modify) Expand regex patterns
│   ├── scale_detector.py      # NEW: Detect drawing scale from text/dims
│   ├── segment_classifier.py  # NEW: Parallel line pair detection for beams
│   └── text_classifier.py     # NEW: Regex-based element name/type detection
├── generator/
│   ├── dxf_writer.py          # (exists, modify) Add exclusion/legend layers
│   ├── bom_generator.py       # (exists) BOM CSV
│   └── pdf_generator.py       # NEW: PDF report generation
└── utils/
    ├── constants.py            # (exists) NBR constants
    └── units.py                # (exists) Unit conversion
```

### Backend API (FastAPI — `api/`)

```
api/
├── __init__.py
├── main.py                    # FastAPI app, CORS, lifespan
├── config.py                  # Settings (env vars)
├── deps.py                    # Dependencies (DB session, auth)
├── routes/
│   ├── __init__.py
│   ├── jobs.py                # POST /jobs, GET /jobs/{id}/status, etc.
│   ├── catalog.py             # CRUD catálogo/estoque
│   └── auth.py                # Login, /users/me
├── models/
│   ├── __init__.py
│   ├── db.py                  # SQLAlchemy models (Job, Tenant, Catalog, etc.)
│   └── schemas.py             # Pydantic request/response schemas
├── services/
│   ├── __init__.py
│   ├── job_service.py         # Job lifecycle (create, update status, get results)
│   └── storage.py             # File storage (local for MVP, S3-ready interface)
├── workers/
│   ├── __init__.py
│   └── pipeline_worker.py     # ARQ worker that runs the pipeline
└── migrations/
    └── (alembic managed)
```

### Frontend (Next.js — `web/`)

```
web/
├── app/
│   ├── layout.tsx             # Root layout + providers
│   ├── page.tsx               # Landing / upload page
│   ├── jobs/
│   │   └── [id]/
│   │       ├── page.tsx       # Job detail: preview + results
│   │       └── loading.tsx    # Job processing skeleton
│   └── catalog/
│       └── page.tsx           # Catalog management
├── components/
│   ├── UploadForm.tsx         # DXF upload with drag & drop
│   ├── DxfPreview.tsx         # Canvas-based DXF preview with overlays
│   ├── ElementEditor.tsx      # Click-to-reclassify element panel
│   ├── ResultsComparison.tsx  # 3-strategy comparison cards
│   └── JobStatusBadge.tsx     # Status polling indicator
├── lib/
│   ├── api.ts                 # API client (fetch wrapper)
│   └── types.ts               # TypeScript types matching API schemas
└── package.json
```

### Tests

```
tests/
├── pipeline/
│   ├── test_stage_parse.py
│   ├── test_stage_segment.py
│   ├── test_stage_classify.py
│   ├── test_stage_metadata.py
│   ├── test_confidence.py
│   └── test_runner.py         # E2E: CVS-COB DXF → expected output
├── engine/
│   ├── test_load_calculator.py
│   ├── test_beam_calculator.py
│   ├── test_grid_distributor.py
│   ├── test_optimizer.py
│   └── test_shore_selector.py
├── api/
│   ├── test_jobs.py
│   ├── test_catalog.py
│   └── conftest.py            # FastAPI TestClient fixtures
└── fixtures/
    ├── CVS-COB-FOR-006-R00.DXF   # Real test DXF
    └── simple_beam_slab.dxf       # Minimal synthetic DXF for unit tests
```

---

## Chunk 1: Pipeline Models + Confidence Scoring

### Task 1: Pipeline Data Models

**Files:**
- Create: `src/models/pipeline_models.py`
- Create: `tests/pipeline/test_stage_parse.py` (partial — just model tests)

- [ ] **Step 1: Write tests for pipeline models**

```python
# tests/pipeline/test_stage_parse.py
import pytest
from src.models.pipeline_models import (
    RawEntity, ClassifiedElement, ElementType, LevelGroup, PipelineResult
)


def test_raw_entity_creation():
    e = RawEntity(
        entity_type="LWPOLYLINE",
        layer="11",
        points=[(0, 0), (5, 0), (5, 1), (0, 1)],
        color=7,
        texts_nearby=[],
    )
    assert e.entity_type == "LWPOLYLINE"
    assert e.layer == "11"
    assert len(e.points) == 4


def test_classified_element_beam():
    el = ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[(0, 0), (5, 0), (5, 0.14), (0, 0.14)],
        score_geometric=0.85,
        score_textual=0.90,
        score_final=0.95,
        name="V1",
        section_width_m=0.14,
        section_height_m=0.40,
        length_m=5.0,
        source_layer="11",
    )
    assert el.element_type == ElementType.BEAM
    assert el.score_final == 0.95
    assert el.needs_review is False  # score >= 0.90


def test_classified_element_needs_review():
    el = ClassifiedElement(
        element_type=ElementType.SLAB,
        geometry=[(0, 0), (5, 0), (5, 4), (0, 4)],
        score_geometric=0.60,
        score_textual=0.0,
        score_final=0.51,
        source_layer="UNKNOWN",
    )
    assert el.needs_review is True  # score < 0.90
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/pipeline/test_stage_parse.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.models.pipeline_models'`

- [ ] **Step 3: Implement pipeline models**

```python
# src/models/pipeline_models.py
"""Data models for the DXF interpretation pipeline."""

from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field, computed_field


class ElementType(str, Enum):
    BEAM = "beam"
    SLAB = "slab"
    PILLAR = "pillar"
    UNKNOWN = "unknown"


class RawEntity(BaseModel):
    """Entity extracted from DXF in Stage 1 (raw parse)."""
    entity_type: str = Field(description="DXF entity type: LWPOLYLINE, POLYLINE, SOLID, etc.")
    layer: str = Field(description="Layer name from DXF")
    points: List[Tuple[float, float]] = Field(description="Vertex coordinates (already scaled)")
    color: int = Field(default=7, description="DXF color index")
    texts_nearby: List[str] = Field(default_factory=list, description="TEXT/MTEXT content near entity")
    block_name: Optional[str] = Field(default=None, description="Block reference name if applicable")


class ClassifiedElement(BaseModel):
    """Element after Stage 3 classification."""
    element_type: ElementType = Field(default=ElementType.UNKNOWN)
    geometry: List[Tuple[float, float]] = Field(description="Polygon vertices in real meters")
    score_geometric: float = Field(default=0.0, ge=0.0, le=1.0)
    score_textual: float = Field(default=0.0, ge=0.0, le=1.0)
    score_final: float = Field(default=0.0, ge=0.0, le=1.0)
    name: Optional[str] = Field(default=None, description="Element name (V1, L3, P5)")
    section_width_m: Optional[float] = Field(default=None, description="Beam/pillar section width")
    section_height_m: Optional[float] = Field(default=None, description="Beam/pillar section height")
    thickness_m: Optional[float] = Field(default=None, description="Slab thickness")
    length_m: Optional[float] = Field(default=None, description="Beam length")
    source_layer: str = Field(default="", description="Original DXF layer")
    support_positions: Optional[List[float]] = Field(default=None, description="Support positions along beam axis")
    is_cantilever_start: bool = Field(default=False)
    is_cantilever_end: bool = Field(default=False)

    @computed_field
    @property
    def needs_review(self) -> bool:
        return self.score_final < 0.90


class LevelGroup(BaseModel):
    """Group of entities belonging to the same floor level."""
    level_name: str = Field(description="Level identifier (e.g., 'COBERTURA', '+1330.40')")
    level_height_m: Optional[float] = Field(default=None, description="Absolute level in meters")
    pe_direito_m: Optional[float] = Field(default=None, description="Floor-to-ceiling height")
    entities: List[RawEntity] = Field(default_factory=list)
    elements: List[ClassifiedElement] = Field(default_factory=list)


class PipelineResult(BaseModel):
    """Complete result of the interpretation pipeline."""
    filename: str
    scale: float = Field(default=1.0, description="Drawing scale factor (DXF units → meters)")
    levels: List[LevelGroup] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/pipeline/test_stage_parse.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/models/pipeline_models.py tests/pipeline/ tests/pipeline/__init__.py
git commit -m "feat: add pipeline data models (RawEntity, ClassifiedElement, PipelineResult)"
```

---

### Task 2: Confidence Score Calculator

**Files:**
- Create: `src/models/confidence.py`
- Create: `tests/pipeline/test_confidence.py`

- [ ] **Step 1: Write failing tests for confidence scoring**

```python
# tests/pipeline/test_confidence.py
import pytest
from src.models.confidence import calculate_confidence


def test_both_signals_agree():
    """Geometry says beam (0.85), text says beam (0.90) → high confidence."""
    score = calculate_confidence(score_geo=0.85, score_txt=0.90, agree=True)
    assert score == min(max(0.85, 0.90) + 0.10, 1.0)  # 1.0 (capped)


def test_both_signals_contradict():
    """Geometry says beam (0.80), text says pillar (0.70) → low confidence."""
    score = calculate_confidence(score_geo=0.80, score_txt=0.70, agree=False)
    assert score == max(min(0.80, 0.70) - 0.20, 0.0)  # 0.50


def test_only_geometric_signal():
    """Only geometry signal (0.85), no text → moderate confidence."""
    score = calculate_confidence(score_geo=0.85, score_txt=0.0, agree=True)
    assert score == pytest.approx(0.85 * 0.85)  # 0.7225


def test_only_textual_signal():
    """Only text signal (0.90), no geometry → moderate confidence."""
    score = calculate_confidence(score_geo=0.0, score_txt=0.90, agree=True)
    assert score == pytest.approx(0.90 * 0.85)  # 0.765


def test_no_signal():
    """No signals at all → zero confidence."""
    score = calculate_confidence(score_geo=0.0, score_txt=0.0, agree=True)
    assert score == 0.0


def test_cap_at_1():
    """Both signals at 0.95 → capped at 1.0."""
    score = calculate_confidence(score_geo=0.95, score_txt=0.95, agree=True)
    assert score == 1.0


def test_floor_at_0():
    """Contradicting low signals → floored at 0.0."""
    score = calculate_confidence(score_geo=0.15, score_txt=0.10, agree=False)
    assert score == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/pipeline/test_confidence.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement confidence calculator**

```python
# src/models/confidence.py
"""Confidence score calculation for element classification.

Spec reference: Section 17 — Thresholds de Confiança.

Two independent signals (geometric + textual) are combined:
- Both agree → max(geo, txt) + 0.10 (capped at 1.0)
- Both contradict → min(geo, txt) - 0.20 (floored at 0.0)
- Only one signal → available_score × 0.85
"""

AGREE_BONUS = 0.10
CONTRADICT_PENALTY = 0.20
SINGLE_SIGNAL_FACTOR = 0.85
SIGNAL_THRESHOLD = 0.05  # below this, signal is considered absent


def calculate_confidence(
    score_geo: float,
    score_txt: float,
    agree: bool,
) -> float:
    has_geo = score_geo >= SIGNAL_THRESHOLD
    has_txt = score_txt >= SIGNAL_THRESHOLD

    if not has_geo and not has_txt:
        return 0.0

    if has_geo and has_txt:
        if agree:
            return min(max(score_geo, score_txt) + AGREE_BONUS, 1.0)
        else:
            return max(min(score_geo, score_txt) - CONTRADICT_PENALTY, 0.0)

    # Only one signal
    available = score_geo if has_geo else score_txt
    return available * SINGLE_SIGNAL_FACTOR
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/pipeline/test_confidence.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/models/confidence.py tests/pipeline/test_confidence.py
git commit -m "feat: add confidence score calculator (spec section 17)"
```

---

## Chunk 2: Stage 1 — Generic DXF Parser

### Task 3: Scale Detector

**Files:**
- Create: `src/parser/scale_detector.py`
- Create: `tests/pipeline/test_scale_detector.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/pipeline/test_scale_detector.py
import pytest
from src.parser.scale_detector import detect_scale_from_texts


def test_detect_1_50():
    texts = ["PLANTA DE FORMAS", "ESC 1:50", "NIVEL +3.00"]
    assert detect_scale_from_texts(texts) == 0.02  # 1/50


def test_detect_1_25():
    texts = ["ESCALA 1:25", "COBERTURA"]
    assert detect_scale_from_texts(texts) == 0.04  # 1/25


def test_detect_1_100():
    texts = ["ESC.: 1/100"]
    assert detect_scale_from_texts(texts) == 0.01  # 1/100


def test_no_scale_returns_none():
    texts = ["PLANTA DE FORMAS", "NIVEL +3.00"]
    assert detect_scale_from_texts(texts) is None


def test_detect_case_insensitive():
    texts = ["esc 1:50"]
    assert detect_scale_from_texts(texts) == 0.02
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/pipeline/test_scale_detector.py -v`
Expected: FAIL

- [ ] **Step 3: Implement scale detector**

```python
# src/parser/scale_detector.py
"""Detect drawing scale from text annotations in DXF.

Searches for patterns like 'ESC 1:50', 'ESCALA 1:25', 'ESC.: 1/100'.
Returns scale factor: DXF_units × factor = meters.
"""

import re
from typing import List, Optional

SCALE_PATTERN = re.compile(
    r"ESC(?:ALA)?[\s.:]*1\s*[:/]\s*(\d+)",
    re.IGNORECASE,
)


def detect_scale_from_texts(texts: List[str]) -> Optional[float]:
    for text in texts:
        match = SCALE_PATTERN.search(text)
        if match:
            denominator = int(match.group(1))
            if denominator > 0:
                return 1.0 / denominator
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/pipeline/test_scale_detector.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/parser/scale_detector.py tests/pipeline/test_scale_detector.py
git commit -m "feat: add scale detector for DXF text annotations"
```

---

### Task 4: Text Classifier (element name/type from text)

**Files:**
- Create: `src/parser/text_classifier.py`
- Create: `tests/pipeline/test_text_classifier.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/pipeline/test_text_classifier.py
import pytest
from src.parser.text_classifier import (
    classify_text, extract_section, extract_thickness,
    TextClassification, ElementType,
)


class TestClassifyText:
    def test_beam_v1(self):
        r = classify_text("V1")
        assert r.element_type == ElementType.BEAM
        assert r.name == "V1"
        assert r.score > 0.8

    def test_beam_vg301(self):
        r = classify_text("VG-301")
        assert r.element_type == ElementType.BEAM

    def test_beam_viga(self):
        r = classify_text("VIGA 5")
        assert r.element_type == ElementType.BEAM
        assert r.name == "VIGA 5"

    def test_pillar_p1(self):
        r = classify_text("P1")
        assert r.element_type == ElementType.PILLAR

    def test_pillar_pilar(self):
        r = classify_text("PILAR 7")
        assert r.element_type == ElementType.PILLAR

    def test_slab_l1(self):
        r = classify_text("L1")
        assert r.element_type == ElementType.SLAB

    def test_slab_laje(self):
        r = classify_text("LAJE 3")
        assert r.element_type == ElementType.SLAB

    def test_unknown(self):
        r = classify_text("QUADRO DE AREAS")
        assert r.element_type == ElementType.UNKNOWN

    def test_layer_vigas(self):
        r = classify_text("VIGAS")
        assert r.element_type == ElementType.BEAM


class TestExtractSection:
    def test_14x40(self):
        w, h = extract_section("14x40")
        assert w == 0.14
        assert h == 0.40

    def test_14_slash_60(self):
        w, h = extract_section("14/60")
        assert w == 0.14
        assert h == 0.60

    def test_20x50_in_context(self):
        w, h = extract_section("V3 (20x50)")
        assert w == 0.20
        assert h == 0.50

    def test_no_section(self):
        result = extract_section("V1")
        assert result is None


class TestExtractThickness:
    def test_h_12(self):
        assert extract_thickness("h=12") == 0.12

    def test_e_15cm(self):
        assert extract_thickness("e=15cm") == 0.15

    def test_esp_10(self):
        assert extract_thickness("ESP. 10") == 0.10

    def test_no_thickness(self):
        assert extract_thickness("LAJE") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/pipeline/test_text_classifier.py -v`
Expected: FAIL

- [ ] **Step 3: Implement text classifier**

```python
# src/parser/text_classifier.py
"""Classify structural elements from DXF text content and layer names.

Spec reference: Section 6, Etapa 3 — Sinal Textual.

Patterns detected:
- Beams: V\d+, VG\d+, VIGA
- Pillars: P\d+, PIL, PILAR
- Slabs: L\d+, LAJE, LJ
- Sections: \d+x\d+, \d+/\d+
- Thickness: h=\d+, e=\d+cm, ESP
"""

import re
from typing import Optional, Tuple
from dataclasses import dataclass
from src.models.pipeline_models import ElementType


@dataclass
class TextClassification:
    element_type: ElementType
    name: Optional[str]
    score: float


# Patterns ordered by specificity (most specific first)
BEAM_PATTERNS = [
    (re.compile(r"\bVIGA\s*\d*\w*", re.IGNORECASE), 0.95),
    (re.compile(r"\bVG[-.]?\d+", re.IGNORECASE), 0.90),
    (re.compile(r"\bV\d+\w*\b"), 0.85),
    (re.compile(r"\bVIGAS?\b", re.IGNORECASE), 0.80),
]

PILLAR_PATTERNS = [
    (re.compile(r"\bPILAR\s*\d*\w*", re.IGNORECASE), 0.95),
    (re.compile(r"\bPIL[-.]?\d+", re.IGNORECASE), 0.90),
    (re.compile(r"\bP\d+\w*\b"), 0.85),
    (re.compile(r"\bPILARES?\b", re.IGNORECASE), 0.80),
]

SLAB_PATTERNS = [
    (re.compile(r"\bLAJE\s*\d*\w*", re.IGNORECASE), 0.95),
    (re.compile(r"\bLJ[-.]?\d+", re.IGNORECASE), 0.90),
    (re.compile(r"\bL\d+\w*\b"), 0.85),
    (re.compile(r"\bLAJES?\b", re.IGNORECASE), 0.80),
]

SECTION_PATTERN = re.compile(r"(\d+)\s*[x/]\s*(\d+)")
THICKNESS_PATTERN = re.compile(r"(?:[he]=?\s*|ESP\.?\s*)(\d+)\s*(?:cm)?", re.IGNORECASE)


def classify_text(text: str) -> TextClassification:
    for pattern, score in BEAM_PATTERNS:
        m = pattern.search(text)
        if m:
            return TextClassification(ElementType.BEAM, m.group(0).strip(), score)

    for pattern, score in PILLAR_PATTERNS:
        m = pattern.search(text)
        if m:
            return TextClassification(ElementType.PILLAR, m.group(0).strip(), score)

    for pattern, score in SLAB_PATTERNS:
        m = pattern.search(text)
        if m:
            return TextClassification(ElementType.SLAB, m.group(0).strip(), score)

    return TextClassification(ElementType.UNKNOWN, None, 0.0)


def extract_section(text: str) -> Optional[Tuple[float, float]]:
    m = SECTION_PATTERN.search(text)
    if m:
        w_cm = int(m.group(1))
        h_cm = int(m.group(2))
        return (w_cm / 100.0, h_cm / 100.0)
    return None


def extract_thickness(text: str) -> Optional[float]:
    m = THICKNESS_PATTERN.search(text)
    if m:
        value = int(m.group(1))
        if value < 100:
            return value / 100.0  # cm → m
        return value / 1000.0  # mm → m
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/pipeline/test_text_classifier.py -v`
Expected: PASS (16 tests)

- [ ] **Step 5: Commit**

```bash
git add src/parser/text_classifier.py tests/pipeline/test_text_classifier.py
git commit -m "feat: add text classifier for beam/slab/pillar detection from DXF text"
```

---

### Task 5: Segment Classifier (parallel line pair detection for beams)

**Files:**
- Create: `src/parser/segment_classifier.py`
- Create: `tests/pipeline/test_segment_classifier.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/pipeline/test_segment_classifier.py
import pytest
from src.parser.segment_classifier import (
    find_beam_candidates, BeamCandidate,
    find_pillar_candidates, PillarCandidate,
)


class TestBeamCandidates:
    def test_horizontal_pair(self):
        """Two horizontal segments close together → beam candidate."""
        segments = [
            {"type": "H", "y": 5.00, "x_min": 0, "x_max": 6.0},
            {"type": "H", "y": 5.14, "x_min": 0, "x_max": 6.0},
        ]
        beams = find_beam_candidates(segments)
        assert len(beams) == 1
        assert beams[0].width_m == pytest.approx(0.14, abs=0.02)
        assert beams[0].length_m == pytest.approx(6.0, abs=0.1)
        assert beams[0].direction == "x"

    def test_vertical_pair(self):
        """Two vertical segments close together → beam candidate."""
        segments = [
            {"type": "V", "x": 3.00, "y_min": 0, "y_max": 5.0},
            {"type": "V", "x": 3.14, "y_min": 0, "y_max": 5.0},
        ]
        beams = find_beam_candidates(segments)
        assert len(beams) == 1
        assert beams[0].direction == "y"

    def test_no_pair_far_apart(self):
        """Segments too far apart → not a beam."""
        segments = [
            {"type": "H", "y": 5.00, "x_min": 0, "x_max": 6.0},
            {"type": "H", "y": 6.00, "x_min": 0, "x_max": 6.0},
        ]
        beams = find_beam_candidates(segments)
        assert len(beams) == 0

    def test_min_length_filter(self):
        """Very short segment pair → filtered out (not a beam)."""
        segments = [
            {"type": "H", "y": 5.00, "x_min": 0, "x_max": 0.20},
            {"type": "H", "y": 5.14, "x_min": 0, "x_max": 0.20},
        ]
        beams = find_beam_candidates(segments, min_length=0.5)
        assert len(beams) == 0


class TestPillarCandidates:
    def test_small_rectangle(self):
        """Small closed rectangle → pillar candidate."""
        rects = [
            {"cx": 5.0, "cy": 10.0, "width": 0.20, "height": 0.40, "area": 0.08},
        ]
        pillars = find_pillar_candidates(rects)
        assert len(pillars) == 1
        assert pillars[0].width_m == pytest.approx(0.20)
        assert pillars[0].depth_m == pytest.approx(0.40)

    def test_large_rectangle_filtered(self):
        """Large rectangle → not a pillar (area > 0.5m²)."""
        rects = [
            {"cx": 5.0, "cy": 10.0, "width": 2.0, "height": 3.0, "area": 6.0},
        ]
        pillars = find_pillar_candidates(rects)
        assert len(pillars) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/pipeline/test_segment_classifier.py -v`
Expected: FAIL

- [ ] **Step 3: Implement segment classifier**

```python
# src/parser/segment_classifier.py
"""Geometric classification of DXF segments into structural elements.

Spec reference: Section 6, Etapa 3 — Sinal Geométrico.

Beams: parallel line pairs with small gap (= beam width), long length.
Pillars: small closed rectangles (area < MAX_PILLAR_AREA).
"""

from dataclasses import dataclass
from typing import List

MAX_BEAM_WIDTH = 0.50  # meters — beams wider than this are unlikely
MIN_BEAM_WIDTH = 0.08  # meters — beams narrower than this are unlikely
MAX_PILLAR_AREA = 0.50  # m² — pillars larger than this are unlikely
MIN_BEAM_LENGTH_DEFAULT = 0.50  # meters


@dataclass
class BeamCandidate:
    axis_coord: float  # center Y (horizontal beam) or center X (vertical beam)
    start: float       # start X (horizontal) or start Y (vertical)
    end: float         # end X (horizontal) or end Y (vertical)
    width_m: float
    length_m: float
    direction: str     # "x" (horizontal) or "y" (vertical)
    score: float = 0.0


@dataclass
class PillarCandidate:
    cx: float
    cy: float
    width_m: float
    depth_m: float
    score: float = 0.0


def find_beam_candidates(
    segments: List[dict],
    min_length: float = MIN_BEAM_LENGTH_DEFAULT,
) -> List[BeamCandidate]:
    h_segs = sorted(
        [s for s in segments if s["type"] == "H"],
        key=lambda s: s["y"],
    )
    v_segs = sorted(
        [s for s in segments if s["type"] == "V"],
        key=lambda s: s["x"],
    )

    beams = []

    # Pair horizontal segments
    for i in range(len(h_segs)):
        for j in range(i + 1, len(h_segs)):
            gap = abs(h_segs[j]["y"] - h_segs[i]["y"])
            if gap < MIN_BEAM_WIDTH or gap > MAX_BEAM_WIDTH:
                continue
            # Check overlap in X
            overlap_start = max(h_segs[i]["x_min"], h_segs[j]["x_min"])
            overlap_end = min(h_segs[i]["x_max"], h_segs[j]["x_max"])
            overlap_len = overlap_end - overlap_start
            if overlap_len < min_length:
                continue

            axis_y = (h_segs[i]["y"] + h_segs[j]["y"]) / 2
            length_ratio = overlap_len / gap
            score = min(0.95, 0.50 + 0.05 * min(length_ratio, 9))

            beams.append(BeamCandidate(
                axis_coord=axis_y,
                start=overlap_start,
                end=overlap_end,
                width_m=gap,
                length_m=overlap_len,
                direction="x",
                score=score,
            ))

    # Pair vertical segments
    for i in range(len(v_segs)):
        for j in range(i + 1, len(v_segs)):
            gap = abs(v_segs[j]["x"] - v_segs[i]["x"])
            if gap < MIN_BEAM_WIDTH or gap > MAX_BEAM_WIDTH:
                continue
            overlap_start = max(v_segs[i]["y_min"], v_segs[j]["y_min"])
            overlap_end = min(v_segs[i]["y_max"], v_segs[j]["y_max"])
            overlap_len = overlap_end - overlap_start
            if overlap_len < min_length:
                continue

            axis_x = (v_segs[i]["x"] + v_segs[j]["x"]) / 2
            length_ratio = overlap_len / gap
            score = min(0.95, 0.50 + 0.05 * min(length_ratio, 9))

            beams.append(BeamCandidate(
                axis_coord=axis_x,
                start=overlap_start,
                end=overlap_end,
                width_m=gap,
                length_m=overlap_len,
                direction="y",
                score=score,
            ))

    return beams


def find_pillar_candidates(
    rects: List[dict],
    max_area: float = MAX_PILLAR_AREA,
) -> List[PillarCandidate]:
    pillars = []
    for r in rects:
        if r["area"] > max_area:
            continue
        aspect = max(r["width"], r["height"]) / max(min(r["width"], r["height"]), 0.01)
        # Pillars tend to have aspect ratio < 4 (not too elongated)
        if aspect > 4.0:
            continue
        score = min(0.90, 0.60 + 0.10 * (1.0 / max(aspect, 1.0)))
        pillars.append(PillarCandidate(
            cx=r["cx"], cy=r["cy"],
            width_m=r["width"], depth_m=r["height"],
            score=score,
        ))
    return pillars
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/pipeline/test_segment_classifier.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/parser/segment_classifier.py tests/pipeline/test_segment_classifier.py
git commit -m "feat: add segment classifier for beam/pillar geometric detection"
```

---

### Task 6: Stage 1 — Generic DXF Entity Extractor

**Files:**
- Create: `src/pipeline/stage_parse.py`
- Modify: `src/parser/dxf_reader.py` (add `extract_all_entities`)
- Create: `tests/pipeline/test_stage_parse_integration.py`

- [ ] **Step 1: Write failing test for entity extraction**

```python
# tests/pipeline/test_stage_parse_integration.py
import pytest
import ezdxf
from src.pipeline.stage_parse import parse_dxf


@pytest.fixture
def simple_dxf(tmp_path):
    """Create a minimal DXF with known entities for testing."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add("VIGAS", color=1)
    doc.layers.add("TEXTO", color=7)

    # Two parallel horizontal lines (beam edges)
    msp.add_line((0, 0), (100, 0), dxfattribs={"layer": "VIGAS"})
    msp.add_line((0, 2.8), (100, 2.8), dxfattribs={"layer": "VIGAS"})

    # A SOLID rectangle (pillar)
    msp.add_solid([(40, 40), (44, 40), (44, 48), (40, 48)], dxfattribs={"layer": "PILARES"})

    # Text annotations
    msp.add_text("V1 14x40", height=2.0, dxfattribs={"layer": "TEXTO", "insert": (10, 5)})
    msp.add_text("ESC 1:50", height=2.0, dxfattribs={"layer": "TEXTO", "insert": (80, 80)})

    path = tmp_path / "test.dxf"
    doc.saveas(str(path))
    return str(path)


def test_parse_extracts_all_entities(simple_dxf):
    result = parse_dxf(simple_dxf)
    assert result.filename == "test.dxf"
    assert len(result.raw_entities) > 0
    assert len(result.texts) >= 2  # V1 and ESC


def test_parse_detects_scale(simple_dxf):
    result = parse_dxf(simple_dxf)
    assert result.detected_scale == pytest.approx(0.02)  # 1:50


def test_parse_extracts_layers(simple_dxf):
    result = parse_dxf(simple_dxf)
    assert "VIGAS" in result.layers
    assert "TEXTO" in result.layers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/pipeline/test_stage_parse_integration.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Stage 1 parser**

```python
# src/pipeline/stage_parse.py
"""Stage 1: Raw DXF entity extraction.

Reads any DXF file and extracts all entities with their attributes,
layer names, coordinates, and nearby text annotations.
Detects drawing scale from text annotations.
"""

import ezdxf
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from src.parser.scale_detector import detect_scale_from_texts


@dataclass
class TextEntity:
    content: str
    x: float
    y: float
    layer: str


@dataclass
class SegmentEntity:
    """A line segment (horizontal or vertical)."""
    type: str  # "H" or "V"
    x: float = 0.0   # for V segments
    y: float = 0.0   # for H segments
    x_min: float = 0.0
    x_max: float = 0.0
    y_min: float = 0.0
    y_max: float = 0.0
    layer: str = ""


@dataclass
class RectEntity:
    """A closed rectangle (potential pillar)."""
    cx: float
    cy: float
    width: float
    height: float
    area: float
    layer: str = ""


@dataclass
class PolylineEntity:
    """A closed polyline (potential slab boundary)."""
    points: List[Tuple[float, float]]
    layer: str = ""
    is_closed: bool = False


@dataclass
class ParseResult:
    filename: str
    layers: List[str]
    detected_scale: Optional[float]
    texts: List[TextEntity] = field(default_factory=list)
    segments: List[SegmentEntity] = field(default_factory=list)
    rects: List[RectEntity] = field(default_factory=list)
    polylines: List[PolylineEntity] = field(default_factory=list)
    raw_entities: List[dict] = field(default_factory=list)


def parse_dxf(filepath: str) -> ParseResult:
    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()
    filename = Path(filepath).name
    layers = [layer.dxf.name for layer in doc.layers]

    texts: List[TextEntity] = []
    segments: List[SegmentEntity] = []
    rects: List[RectEntity] = []
    polylines: List[PolylineEntity] = []
    raw_entities: List[dict] = []

    for entity in msp:
        etype = entity.dxftype()
        layer = entity.dxf.layer

        raw_entities.append({"type": etype, "layer": layer})

        if etype in ("TEXT", "MTEXT"):
            content = entity.dxf.text if etype == "TEXT" else entity.text
            insert = entity.dxf.insert if hasattr(entity.dxf, "insert") else (0, 0, 0)
            texts.append(TextEntity(
                content=content,
                x=insert[0],
                y=insert[1],
                layer=layer,
            ))

        elif etype == "LINE":
            x1, y1 = entity.dxf.start.x, entity.dxf.start.y
            x2, y2 = entity.dxf.end.x, entity.dxf.end.y
            if abs(y1 - y2) < 0.01:  # horizontal
                segments.append(SegmentEntity(
                    type="H", y=(y1 + y2) / 2,
                    x_min=min(x1, x2), x_max=max(x1, x2), layer=layer,
                ))
            elif abs(x1 - x2) < 0.01:  # vertical
                segments.append(SegmentEntity(
                    type="V", x=(x1 + x2) / 2,
                    y_min=min(y1, y2), y_max=max(y1, y2), layer=layer,
                ))

        elif etype == "SOLID":
            pts = [entity.dxf.vtx0, entity.dxf.vtx1, entity.dxf.vtx2, entity.dxf.vtx3]
            xs = [p.x for p in pts]
            ys = [p.y for p in pts]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            if w > 0 and h > 0:
                rects.append(RectEntity(
                    cx=(min(xs) + max(xs)) / 2,
                    cy=(min(ys) + max(ys)) / 2,
                    width=w, height=h, area=w * h, layer=layer,
                ))

        elif etype in ("LWPOLYLINE", "POLYLINE"):
            if etype == "LWPOLYLINE":
                pts = [(p[0], p[1]) for p in entity.get_points(format="xy")]
                closed = entity.closed
            else:
                pts = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                closed = entity.is_closed
            if len(pts) >= 2:
                polylines.append(PolylineEntity(
                    points=pts, layer=layer, is_closed=closed,
                ))
                # Also extract as line segments if 2-point polyline
                if len(pts) == 2:
                    x1, y1 = pts[0]
                    x2, y2 = pts[1]
                    if abs(y1 - y2) < 0.01:
                        segments.append(SegmentEntity(
                            type="H", y=(y1 + y2) / 2,
                            x_min=min(x1, x2), x_max=max(x1, x2), layer=layer,
                        ))
                    elif abs(x1 - x2) < 0.01:
                        segments.append(SegmentEntity(
                            type="V", x=(x1 + x2) / 2,
                            y_min=min(y1, y2), y_max=max(y1, y2), layer=layer,
                        ))

    # Detect scale
    text_contents = [t.content for t in texts]
    detected_scale = detect_scale_from_texts(text_contents)

    return ParseResult(
        filename=filename,
        layers=layers,
        detected_scale=detected_scale,
        texts=texts,
        segments=segments,
        rects=rects,
        polylines=polylines,
        raw_entities=raw_entities,
    )
```

Also create `src/pipeline/__init__.py`:

```python
# src/pipeline/__init__.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/pipeline/test_stage_parse_integration.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/__init__.py src/pipeline/stage_parse.py tests/pipeline/test_stage_parse_integration.py
git commit -m "feat: add Stage 1 generic DXF parser with scale detection"
```

---

## Chunk 3: Stages 2-4 (Segmentation, Classification, Metadata)

### Task 7: Stage 2 — Level Segmentation

**Files:**
- Create: `src/pipeline/stage_segment.py`
- Create: `tests/pipeline/test_stage_segment.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/pipeline/test_stage_segment.py
import pytest
from src.pipeline.stage_parse import ParseResult, TextEntity, SegmentEntity
from src.pipeline.stage_segment import segment_by_level


def test_single_level():
    """DXF with one level → 1 group with all entities."""
    parse = ParseResult(
        filename="test.dxf", layers=["11"], detected_scale=0.02,
        texts=[TextEntity("COBERTURA +1330.40", 10, 10, "TEXTO")],
        segments=[SegmentEntity("H", y=5.0, x_min=0, x_max=10, layer="11")],
    )
    levels = segment_by_level(parse)
    assert len(levels) == 1
    assert "COBERTURA" in levels[0].level_name or "+1330" in levels[0].level_name


def test_no_level_text():
    """DXF with no level text → 1 default group."""
    parse = ParseResult(
        filename="test.dxf", layers=["11"], detected_scale=0.02,
        texts=[TextEntity("V1 14x40", 10, 10, "TEXTO")],
        segments=[SegmentEntity("H", y=5.0, x_min=0, x_max=10, layer="11")],
    )
    levels = segment_by_level(parse)
    assert len(levels) == 1
    assert levels[0].level_name == "DEFAULT"
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Implement**

```python
# src/pipeline/stage_segment.py
"""Stage 2: Segment DXF entities by floor level.

Searches for TEXT/MTEXT with level patterns (+1330, COBERTURA, TIPO 1, N+3.00).
For MVP, treats entire DXF as single level if no level text found.
Multi-level segmentation by spatial proximity is Fase 2.
"""

import re
from typing import List
from dataclasses import dataclass, field
from src.pipeline.stage_parse import ParseResult, TextEntity, SegmentEntity, RectEntity, PolylineEntity

LEVEL_PATTERN = re.compile(
    r"(?:COBERTURA|COBERTA|TIPO\s*\d+|PAVT?\.?\s*\d+|"
    r"N[IÍ]VEL\s*[\+\-]?\s*[\d.]+|"
    r"[\+\-]\s*\d{2,}\.\d+|"
    r"N\s*[\+\-]\s*\d+\.?\d*)",
    re.IGNORECASE,
)


@dataclass
class LevelSegment:
    level_name: str
    level_height_m: float = 0.0
    texts: List[TextEntity] = field(default_factory=list)
    segments: List[SegmentEntity] = field(default_factory=list)
    rects: List[RectEntity] = field(default_factory=list)
    polylines: List[PolylineEntity] = field(default_factory=list)


def _extract_level_height(text: str) -> float:
    m = re.search(r"[\+\-]?\s*(\d{2,}\.?\d*)", text)
    if m:
        return float(m.group(1).replace(" ", ""))
    return 0.0


def segment_by_level(parse: ParseResult) -> List[LevelSegment]:
    # Find level annotations
    level_texts = []
    for t in parse.texts:
        if LEVEL_PATTERN.search(t.content):
            level_texts.append(t)

    if not level_texts:
        # Single level — everything in one group
        seg = LevelSegment(
            level_name="DEFAULT",
            texts=parse.texts,
            segments=parse.segments,
            rects=parse.rects,
            polylines=parse.polylines,
        )
        return [seg]

    # MVP: use first found level for the whole file
    # Multi-level spatial segmentation deferred to Fase 2
    first = level_texts[0]
    level_name = LEVEL_PATTERN.search(first.content).group(0).strip()
    level_height = _extract_level_height(first.content)

    seg = LevelSegment(
        level_name=level_name,
        level_height_m=level_height,
        texts=parse.texts,
        segments=parse.segments,
        rects=parse.rects,
        polylines=parse.polylines,
    )
    return [seg]
```

- [ ] **Step 4: Run test — expect PASS**

Run: `python3 -m pytest tests/pipeline/test_stage_segment.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/stage_segment.py tests/pipeline/test_stage_segment.py
git commit -m "feat: add Stage 2 level segmentation (single-level MVP)"
```

---

### Task 8: Stage 3 — Combined Classification

**Files:**
- Create: `src/pipeline/stage_classify.py`
- Create: `tests/pipeline/test_stage_classify.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/pipeline/test_stage_classify.py
import pytest
from src.pipeline.stage_segment import LevelSegment
from src.pipeline.stage_parse import SegmentEntity, RectEntity, TextEntity
from src.pipeline.stage_classify import classify_elements
from src.models.pipeline_models import ElementType


def test_classify_beam_from_segments():
    """Parallel segments → beam classified with geometric score."""
    level = LevelSegment(
        level_name="TEST",
        segments=[
            SegmentEntity("H", y=5.00, x_min=0, x_max=6.0, layer="11"),
            SegmentEntity("H", y=5.14, x_min=0, x_max=6.0, layer="11"),
        ],
        texts=[TextEntity("V1 14x40", 3.0, 5.5, "TEXTO")],
    )
    elements = classify_elements(level, scale=0.02)
    beams = [e for e in elements if e.element_type == ElementType.BEAM]
    assert len(beams) >= 1
    assert beams[0].score_final >= 0.70


def test_classify_pillar_from_rect():
    """Small SOLID rectangle → pillar classified."""
    level = LevelSegment(
        level_name="TEST",
        rects=[RectEntity(cx=5.0, cy=10.0, width=4.0, height=8.0, area=32.0, layer="21")],
        texts=[TextEntity("P1", 5.5, 10.5, "21")],
    )
    elements = classify_elements(level, scale=0.02)
    pillars = [e for e in elements if e.element_type == ElementType.PILLAR]
    assert len(pillars) >= 1
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Implement**

```python
# src/pipeline/stage_classify.py
"""Stage 3: Combined geometric + textual classification.

Spec reference: Section 6, Etapa 3.

Combines geometric signal (parallel pairs, small rects) with textual signal
(layer names, nearby text annotations) to classify elements as beams, slabs, or pillars.
"""

import math
from typing import List, Optional
from src.pipeline.stage_segment import LevelSegment
from src.pipeline.stage_parse import TextEntity
from src.parser.segment_classifier import find_beam_candidates, find_pillar_candidates
from src.parser.text_classifier import classify_text, extract_section, extract_thickness, TextClassification
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.confidence import calculate_confidence

# Maximum distance to associate a text annotation with a geometric element
MAX_TEXT_DISTANCE = 2.0  # in DXF units (before scaling)


def _find_nearest_texts(
    x: float, y: float, texts: List[TextEntity], max_dist: float = MAX_TEXT_DISTANCE,
) -> List[TextEntity]:
    nearby = []
    for t in texts:
        dist = math.hypot(t.x - x, t.y - y)
        if dist <= max_dist:
            nearby.append(t)
    return nearby


def classify_elements(level: LevelSegment, scale: float = 1.0) -> List[ClassifiedElement]:
    elements: List[ClassifiedElement] = []

    # Convert segments to dicts for segment_classifier
    seg_dicts = []
    for s in level.segments:
        if s.type == "H":
            seg_dicts.append({"type": "H", "y": s.y * scale, "x_min": s.x_min * scale, "x_max": s.x_max * scale})
        else:
            seg_dicts.append({"type": "V", "x": s.x * scale, "y_min": s.y_min * scale, "y_max": s.y_max * scale})

    # Beams from geometry
    beam_candidates = find_beam_candidates(seg_dicts, min_length=0.5)
    for bc in beam_candidates:
        # Find nearby text
        if bc.direction == "x":
            cx = (bc.start + bc.end) / 2 / scale
            cy = bc.axis_coord / scale
        else:
            cx = bc.axis_coord / scale
            cy = (bc.start + bc.end) / 2 / scale

        nearby = _find_nearest_texts(cx, cy, level.texts)
        text_cls = TextClassification(ElementType.UNKNOWN, None, 0.0)
        section = None
        for t in nearby:
            tc = classify_text(t.content)
            if tc.score > text_cls.score:
                text_cls = tc
            s = extract_section(t.content)
            if s:
                section = s

        agree = text_cls.element_type in (ElementType.BEAM, ElementType.UNKNOWN)
        score_final = calculate_confidence(bc.score, text_cls.score, agree)

        el = ClassifiedElement(
            element_type=ElementType.BEAM,
            geometry=[],  # simplified for now
            score_geometric=bc.score,
            score_textual=text_cls.score,
            score_final=score_final,
            name=text_cls.name,
            section_width_m=section[0] if section else bc.width_m,
            section_height_m=section[1] if section else None,
            length_m=bc.length_m,
            source_layer="",
        )
        elements.append(el)

    # Pillars from rectangles
    rect_dicts = [
        {"cx": r.cx * scale, "cy": r.cy * scale,
         "width": r.width * scale, "height": r.height * scale,
         "area": r.area * scale * scale}
        for r in level.rects
    ]
    pillar_candidates = find_pillar_candidates(rect_dicts)
    for pc in pillar_candidates:
        cx_dxf = pc.cx / scale
        cy_dxf = pc.cy / scale
        nearby = _find_nearest_texts(cx_dxf, cy_dxf, level.texts)
        text_cls = TextClassification(ElementType.UNKNOWN, None, 0.0)
        for t in nearby:
            tc = classify_text(t.content)
            if tc.score > text_cls.score:
                text_cls = tc

        agree = text_cls.element_type in (ElementType.PILLAR, ElementType.UNKNOWN)
        score_final = calculate_confidence(pc.score, text_cls.score, agree)

        el = ClassifiedElement(
            element_type=ElementType.PILLAR,
            geometry=[],
            score_geometric=pc.score,
            score_textual=text_cls.score,
            score_final=score_final,
            name=text_cls.name,
            section_width_m=pc.width_m,
            section_height_m=pc.depth_m,
            source_layer="",
        )
        elements.append(el)

    return elements
```

- [ ] **Step 4: Run test — expect PASS**

Run: `python3 -m pytest tests/pipeline/test_stage_classify.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/stage_classify.py tests/pipeline/test_stage_classify.py
git commit -m "feat: add Stage 3 combined geometric + textual classification"
```

---

### Task 9: Stage 4 — Metadata Extraction

**Files:**
- Create: `src/pipeline/stage_metadata.py`
- Create: `tests/pipeline/test_stage_metadata.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/pipeline/test_stage_metadata.py
import pytest
from src.pipeline.stage_metadata import extract_pe_direito, extract_level_height
from src.pipeline.stage_parse import TextEntity


def test_extract_pe_direito():
    texts = [
        TextEntity("PE DIREITO 2.92m", 10, 10, "TEXTO"),
        TextEntity("V1 14x40", 5, 5, "TEXTO"),
    ]
    assert extract_pe_direito(texts) == pytest.approx(2.92)


def test_extract_pe_direito_pattern2():
    texts = [TextEntity("PD=2.80", 10, 10, "TEXTO")]
    assert extract_pe_direito(texts) == pytest.approx(2.80)


def test_pe_direito_not_found():
    texts = [TextEntity("V1 14x40", 5, 5, "TEXTO")]
    assert extract_pe_direito(texts) is None


def test_extract_level():
    texts = [TextEntity("NIVEL +1330.40", 10, 10, "TEXTO")]
    assert extract_level_height(texts) == pytest.approx(1330.40)
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Implement**

```python
# src/pipeline/stage_metadata.py
"""Stage 4: Extract metadata from text annotations.

Searches for floor height (pé-direito), level heights, and associates
section/thickness data with already-classified elements.
"""

import re
from typing import List, Optional
from src.pipeline.stage_parse import TextEntity

PE_DIREITO_PATTERN = re.compile(
    r"(?:P[EÉ]\s*DIR(?:EITO)?|PD)\s*[=:]?\s*(\d+[.,]\d+)\s*m?",
    re.IGNORECASE,
)

LEVEL_HEIGHT_PATTERN = re.compile(
    r"(?:N[IÍ]VEL|COTA|N)\s*[\+\-]?\s*(\d{2,}[.,]?\d*)",
    re.IGNORECASE,
)


def extract_pe_direito(texts: List[TextEntity]) -> Optional[float]:
    for t in texts:
        m = PE_DIREITO_PATTERN.search(t.content)
        if m:
            return float(m.group(1).replace(",", "."))
    return None


def extract_level_height(texts: List[TextEntity]) -> Optional[float]:
    for t in texts:
        m = LEVEL_HEIGHT_PATTERN.search(t.content)
        if m:
            return float(m.group(1).replace(",", "."))
    return None
```

- [ ] **Step 4: Run test — expect PASS**

Run: `python3 -m pytest tests/pipeline/test_stage_metadata.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/stage_metadata.py tests/pipeline/test_stage_metadata.py
git commit -m "feat: add Stage 4 metadata extraction (pé-direito, level height)"
```

---

### Task 10: Pipeline Runner (orchestrates all stages)

**Files:**
- Create: `src/pipeline/runner.py`
- Create: `tests/pipeline/test_runner.py`

- [ ] **Step 1: Write failing test**

```python
# tests/pipeline/test_runner.py
import pytest
import ezdxf
from src.pipeline.runner import run_pipeline


@pytest.fixture
def synthetic_dxf(tmp_path):
    """Create a synthetic DXF with beams and pillars."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Beam: two parallel horizontal lines (14cm apart at 1:50 → 2.8 DXF units)
    msp.add_line((0, 100), (120, 100), dxfattribs={"layer": "11"})
    msp.add_line((0, 102.8), (120, 102.8), dxfattribs={"layer": "11"})

    # Pillar SOLID (4x8 DXF units = 0.20x0.40m at 1:50)
    msp.add_solid(
        [(0, 98), (4, 98), (4, 106), (0, 106)],
        dxfattribs={"layer": "21"},
    )

    # Text
    msp.add_text("V1 14x40", height=2, dxfattribs={"layer": "TEXTO", "insert": (60, 105)})
    msp.add_text("P1", height=2, dxfattribs={"layer": "TEXTO", "insert": (1, 110)})
    msp.add_text("ESC 1:50", height=2, dxfattribs={"layer": "TEXTO", "insert": (80, 130)})

    path = tmp_path / "synthetic.dxf"
    doc.saveas(str(path))
    return str(path)


def test_pipeline_runs_end_to_end(synthetic_dxf):
    result = run_pipeline(synthetic_dxf)
    assert result.filename == "synthetic.dxf"
    assert result.scale == pytest.approx(0.02)
    assert len(result.levels) >= 1
    # Should find at least 1 beam and 1 pillar
    all_elements = result.levels[0].elements
    types = [e.element_type.value for e in all_elements]
    assert "beam" in types
    assert "pillar" in types
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Implement runner**

```python
# src/pipeline/runner.py
"""Pipeline runner: orchestrates Stages 1-4 sequentially.

Stage 5 (validation/preview) and Stage 6 (learning) are handled
by the API layer, not the runner, since they require user interaction.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from src.pipeline.stage_parse import parse_dxf, ParseResult
from src.pipeline.stage_segment import segment_by_level, LevelSegment
from src.pipeline.stage_classify import classify_elements
from src.pipeline.stage_metadata import extract_pe_direito, extract_level_height
from src.models.pipeline_models import ClassifiedElement, LevelGroup, PipelineResult


DEFAULT_SCALE = 0.02  # 1:50 fallback


def run_pipeline(filepath: str, scale_override: Optional[float] = None) -> PipelineResult:
    # Stage 1: Parse
    parse = parse_dxf(filepath)

    scale = scale_override or parse.detected_scale or DEFAULT_SCALE

    # Stage 2: Segment by level
    level_segments = segment_by_level(parse)

    # Stage 3 + 4: Classify + metadata for each level
    levels: List[LevelGroup] = []
    warnings: List[str] = []

    for seg in level_segments:
        elements = classify_elements(seg, scale=scale)

        pe_direito = extract_pe_direito(seg.texts)
        level_height = extract_level_height(seg.texts)

        if pe_direito is None:
            warnings.append(f"Pé-direito não encontrado no nível {seg.level_name}")

        level = LevelGroup(
            level_name=seg.level_name,
            level_height_m=level_height,
            pe_direito_m=pe_direito,
            elements=elements,
        )
        levels.append(level)

    return PipelineResult(
        filename=parse.filename,
        scale=scale,
        levels=levels,
        warnings=warnings,
    )
```

- [ ] **Step 4: Run test — expect PASS**

Run: `python3 -m pytest tests/pipeline/test_runner.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/runner.py tests/pipeline/test_runner.py
git commit -m "feat: add pipeline runner orchestrating stages 1-4"
```

---

## Chunk 4: Backend API (FastAPI)

### Task 11: Project Setup — FastAPI + DB

**Files:**
- Create: `api/__init__.py`, `api/main.py`, `api/config.py`
- Create: `api/models/__init__.py`, `api/models/db.py`, `api/models/schemas.py`
- Create: `requirements-api.txt`

- [ ] **Step 1: Create requirements file**

```
# requirements-api.txt
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlalchemy>=2.0
alembic>=1.13
psycopg2-binary>=2.9
python-multipart>=0.0.9
arq>=0.26
redis>=5.0
```

- [ ] **Step 2: Create FastAPI app and DB models**

```python
# api/config.py
"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./escora.db"  # MVP: SQLite, Fase 2: PostgreSQL
    redis_url: str = "redis://localhost:6379"
    upload_dir: str = "./uploads"
    output_dir: str = "./output"
    default_tenant_id: str = "pilot"  # Single-tenant MVP

    class Config:
        env_file = ".env"


settings = Settings()
```

```python
# api/models/db.py
"""SQLAlchemy models for Escora.AI."""

from sqlalchemy import Column, String, Float, Integer, JSON, DateTime, Enum as SAEnum, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import enum

Base = declarative_base()


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    APPROVED = "approved"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="pilot")
    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING)
    filename = Column(String, nullable=False)
    office_name = Column(String, nullable=True)
    input_path = Column(String, nullable=False)
    scale = Column(Float, nullable=True)
    pe_direito_m = Column(Float, nullable=True)
    preview_data = Column(JSON, nullable=True)  # ClassifiedElements as JSON
    results_data = Column(JSON, nullable=True)  # Calculation results as JSON
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CatalogEntry(Base):
    __tablename__ = "catalog"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="pilot")
    manufacturer = Column(String)
    model = Column(String)
    type = Column(String, default="telescopic")
    height_min_m = Column(Float)
    height_max_m = Column(Float)
    load_capacity_kn = Column(Float)
    weight_kg = Column(Float)
    price_reference_brl = Column(Float)
    stock_quantity = Column(Integer, default=0)
    notes = Column(String, default="")
```

```python
# api/main.py
"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Escora.AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 3: Verify server starts**

Run: `cd /Users/raphaellages/Desktop/escora-ai && python3 -m uvicorn api.main:app --port 8000 &`
Then: `curl http://localhost:8000/api/v1/health`
Expected: `{"status":"ok"}`
Kill: `kill %1`

- [ ] **Step 4: Commit**

```bash
git add api/ requirements-api.txt
git commit -m "feat: add FastAPI project skeleton with DB models"
```

---

### Task 12: Jobs API — Upload + Status + Preview

**Files:**
- Create: `api/routes/__init__.py`, `api/routes/jobs.py`
- Create: `api/services/__init__.py`, `api/services/job_service.py`, `api/services/storage.py`
- Create: `api/models/schemas.py`
- Create: `tests/api/conftest.py`, `tests/api/test_jobs.py`

- [ ] **Step 1: Write failing API tests**

```python
# tests/api/conftest.py
import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client():
    return TestClient(app)
```

```python
# tests/api/test_jobs.py
import pytest
import io


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200


def test_upload_dxf(client, tmp_path):
    import ezdxf
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0), (10, 0))
    path = tmp_path / "test.dxf"
    doc.saveas(str(path))

    with open(path, "rb") as f:
        r = client.post(
            "/api/v1/jobs",
            files={"file": ("test.dxf", f, "application/octet-stream")},
        )
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["status"] == "pending"


def test_get_job_status(client, tmp_path):
    import ezdxf
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0), (10, 0))
    path = tmp_path / "test.dxf"
    doc.saveas(str(path))

    with open(path, "rb") as f:
        r = client.post("/api/v1/jobs", files={"file": ("test.dxf", f, "application/octet-stream")})
    job_id = r.json()["id"]

    r = client.get(f"/api/v1/jobs/{job_id}/status")
    assert r.status_code == 200
    assert r.json()["status"] in ("pending", "processing")
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement job routes and services**

```python
# api/models/schemas.py
"""Pydantic request/response schemas."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class JobCreateResponse(BaseModel):
    id: str
    status: str
    filename: str
    created_at: datetime


class JobStatusResponse(BaseModel):
    id: str
    status: str
    filename: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class JobPreviewResponse(BaseModel):
    id: str
    elements: List[dict]
    warnings: List[str]
    scale: float
    pe_direito_m: Optional[float]
```

```python
# api/services/storage.py
"""File storage service (local filesystem for MVP)."""

import os
import shutil
from pathlib import Path
from api.config import settings


def save_upload(file_content: bytes, filename: str, job_id: str) -> str:
    upload_dir = Path(settings.upload_dir) / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / filename
    dest.write_bytes(file_content)
    return str(dest)
```

```python
# api/services/job_service.py
"""Job lifecycle management."""

import uuid
from datetime import datetime
from typing import Optional


# In-memory store for MVP (replace with DB in production)
_jobs: dict = {}


def create_job(filename: str, input_path: str, office_name: Optional[str] = None) -> dict:
    job_id = str(uuid.uuid4())[:8]
    job = {
        "id": job_id,
        "tenant_id": "pilot",
        "status": "pending",
        "filename": filename,
        "office_name": office_name,
        "input_path": input_path,
        "scale": None,
        "pe_direito_m": None,
        "preview_data": None,
        "results_data": None,
        "error_message": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    _jobs[job_id] = job
    return job


def get_job(job_id: str) -> Optional[dict]:
    return _jobs.get(job_id)


def update_job(job_id: str, **kwargs) -> Optional[dict]:
    job = _jobs.get(job_id)
    if job:
        job.update(kwargs)
        job["updated_at"] = datetime.utcnow()
    return job
```

```python
# api/routes/jobs.py
"""Job endpoints: upload, status, preview, calculate, approve."""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from api.services import job_service, storage
from api.models.schemas import JobCreateResponse, JobStatusResponse

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("", status_code=201, response_model=JobCreateResponse)
async def upload_dxf(
    file: UploadFile = File(...),
    office_name: Optional[str] = Form(None),
):
    if not file.filename.lower().endswith((".dxf", ".dwg")):
        raise HTTPException(400, "Formato não suportado. Envie .dxf ou .dwg")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "Arquivo excede 50MB")

    job = job_service.create_job(file.filename, "")
    input_path = storage.save_upload(content, file.filename, job["id"])
    job_service.update_job(job["id"], input_path=input_path)

    # TODO: enqueue pipeline processing via ARQ
    # For now, mark as pending
    return JobCreateResponse(
        id=job["id"],
        status=job["status"],
        filename=job["filename"],
        created_at=job["created_at"],
    )


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_status(job_id: str):
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado")
    return JobStatusResponse(**job)
```

Update `api/main.py` to include the router:

```python
# api/main.py (updated)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.jobs import router as jobs_router

app = FastAPI(title="Escora.AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python3 -m pytest tests/api/test_jobs.py -v`

- [ ] **Step 5: Commit**

```bash
git add api/ tests/api/
git commit -m "feat: add Jobs API (upload, status) with in-memory store"
```

---

## Chunk 5: Frontend (Next.js) — Deferred

> **Note:** The frontend (Next.js) chunk is deferred to a separate plan.
> Priority is getting the Python engine pipeline + API stable first.
> The frontend plan will cover:
> - Next.js project setup
> - Upload form with drag & drop
> - DXF preview with canvas rendering
> - Element reclassification UI
> - Results comparison view
> - Job status polling

---

## Chunk 6: Integration — E2E Test with CVS-COB DXF

### Task 13: End-to-End Regression Test

**Files:**
- Create: `tests/pipeline/test_e2e_cvs_cob.py`
- Copy: `input/CVS-COB-FOR-006-R00.DXF` → `tests/fixtures/`

- [ ] **Step 1: Write E2E test**

```python
# tests/pipeline/test_e2e_cvs_cob.py
"""End-to-end regression test using the real CVS-COB DXF.

This test verifies that the generic pipeline can interpret
the same DXF that was previously handled by hardcoded scripts.
"""

import pytest
from pathlib import Path
from src.pipeline.runner import run_pipeline
from src.models.pipeline_models import ElementType

DXF_PATH = Path(__file__).parent.parent / "fixtures" / "CVS-COB-FOR-006-R00.DXF"


@pytest.mark.skipif(not DXF_PATH.exists(), reason="CVS-COB DXF not in fixtures")
class TestCVSCOBRegression:
    def test_pipeline_completes(self):
        result = run_pipeline(str(DXF_PATH))
        assert len(result.levels) >= 1
        assert len(result.errors) == 0

    def test_detects_beams(self):
        result = run_pipeline(str(DXF_PATH))
        all_elements = result.levels[0].elements
        beams = [e for e in all_elements if e.element_type == ElementType.BEAM]
        # CVS-COB has ~22 beams — we expect at least 15 detected generically
        assert len(beams) >= 15

    def test_detects_pillars(self):
        result = run_pipeline(str(DXF_PATH))
        all_elements = result.levels[0].elements
        pillars = [e for e in all_elements if e.element_type == ElementType.PILLAR]
        # CVS-COB has 25 pillars — we expect at least 20 detected
        assert len(pillars) >= 20

    def test_detects_scale(self):
        result = run_pipeline(str(DXF_PATH))
        assert result.scale == pytest.approx(0.02, abs=0.005)  # ~1:50
```

- [ ] **Step 2: Copy DXF fixture**

Run: `cp input/CVS-COB-FOR-006-R00.DXF tests/fixtures/`

- [ ] **Step 3: Run tests — track what passes/fails**

Run: `python3 -m pytest tests/pipeline/test_e2e_cvs_cob.py -v`
Expected: some tests pass, some may fail (this is the baseline for iteration)

- [ ] **Step 4: Iterate on pipeline stages until regression tests pass**

This is the core development loop — tune heuristics, thresholds, and patterns
based on the real DXF until the E2E tests achieve ≥ 80% element detection.

- [ ] **Step 5: Commit**

```bash
git add tests/pipeline/test_e2e_cvs_cob.py tests/fixtures/
git commit -m "feat: add E2E regression test with CVS-COB DXF"
```

---

## Summary

| Chunk | Tasks | What it builds |
|---|---|---|
| 1 | 1-2 | Pipeline models + confidence scoring |
| 2 | 3-6 | Stage 1: Generic DXF parser + classifiers |
| 3 | 7-10 | Stages 2-4: Segmentation, classification, metadata + runner |
| 4 | 11-12 | FastAPI backend with job upload/status |
| 5 | (deferred) | Next.js frontend |
| 6 | 13 | E2E regression test with real DXF |

**Total: 13 tasks, ~65 steps**

After completing these tasks, the system can:
1. Accept any DXF file via API
2. Parse it generically (no hardcoded layers)
3. Classify beams, pillars, slabs using geometry + text
4. Detect scale, pé-direito, levels
5. Present classified elements for operator review
6. Feed into the existing calculation engine
