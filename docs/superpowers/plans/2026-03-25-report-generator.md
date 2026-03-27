# PDF/BOM Report Generator — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate PDF shoring reports and Excel BOM workbooks from `CalculationResult`.

**Architecture:** A `ReportData` intermediate normalizes `CalculationResult` into table rows. Two independent generators (PDF via ReportLab, Excel via openpyxl) consume `ReportData` — they only format, never extract.

**Tech Stack:** Python 3.11+, ReportLab (PDF), openpyxl (Excel), dataclasses

**Spec:** `docs/superpowers/specs/2026-03-25-report-generator-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/output/__init__.py` | Create | Package init |
| `src/output/report_data.py` | Create | ReportMetadata, SummaryData, BeamRow, SlabRow, BomRow, ReportData, `build_report_data()` |
| `src/output/pdf_generator.py` | Create | `generate_pdf(report, output_path)` |
| `src/output/excel_generator.py` | Create | `generate_excel(report, output_path)` |
| `tests/output/__init__.py` | Create | Package init |
| `tests/output/test_report_data.py` | Create | Unit tests for data extraction |
| `tests/output/test_pdf_generator.py` | Create | PDF smoke tests |
| `tests/output/test_excel_generator.py` | Create | Excel smoke tests |

---

## Chunk 1: Dependencies + Report Data

### Task 0: Install Dependencies

**Files:** None (pip install only)

- [ ] **Step 1: Install reportlab**

```bash
pip3 install reportlab
```

- [ ] **Step 2: Verify both dependencies available**

```bash
python3 -c "import reportlab; import openpyxl; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

No code changes — skip commit.

---

### Task 1: ReportData Models + build_report_data()

**Files:**
- Create: `src/output/__init__.py`
- Create: `src/output/report_data.py`
- Create: `tests/output/__init__.py`
- Test: `tests/output/test_report_data.py`

- [ ] **Step 1: Write failing tests for report data**

```python
# tests/output/test_report_data.py
"""Test report data extraction from CalculationResult."""

import pytest
from src.output.report_data import (
    ReportMetadata, ReportData, SummaryData,
    BeamRow, SlabRow, BomRow, build_report_data,
)
from src.models.calculation_models import (
    CalculationResult, BeamShoringResult, SlabShoringResult,
)
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.shore import ShoreCatalogEntry, PositionedShore
from shapely.geometry import box


def _shore(shore_id="ESC-01", capacity=20.0, price=65.0):
    return ShoreCatalogEntry(
        id=shore_id, manufacturer="Generico", model=f"Escora {shore_id}",
        type="telescopic", height_min_m=1.80, height_max_m=3.20,
        load_capacity_kn=capacity, weight_kg=11.0,
        tube_external_mm=60.0, tube_internal_mm=48.0,
        base_plate_mm=150.0, price_reference_brl=price,
    )


def _beam_result(name="V1", width=0.14, height=0.40, length=8.0,
                 shore_count=7, shore_id="ESC-01"):
    shore = _shore(shore_id)
    beam = ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[(0, 5), (length, 5)],
        score_geometric=0.85, score_textual=0.0, score_final=0.75,
        name=name, section_width_m=width, section_height_m=height,
        length_m=length,
    )
    shores = [
        PositionedShore(x=float(i), y=5.0, shore=shore,
                        load_applied_kn=10.0, utilization_ratio=0.5)
        for i in range(shore_count)
    ]
    return BeamShoringResult(
        beam=beam, support_positions=[0.0, length],
        is_cantilever_start=False, is_cantilever_end=False,
        total_linear_load_kn_m=12.5, shores=shores,
        shore_count=shore_count, spacing_m=1.2,
        selected_shore=shore, shore_height_m=2.40,
    )


def _slab_result(area=20.0, thickness=0.12, shore_count=9, shore_id="ESC-02"):
    shore = _shore(shore_id, capacity=15.0, price=45.0)
    polygon = box(0, 0, 5, 4)
    shores = [
        PositionedShore(x=float(i), y=float(j), shore=shore,
                        load_applied_kn=8.0, utilization_ratio=0.4)
        for i in range(3) for j in range(3)
    ]
    return SlabShoringResult(
        polygon=polygon, thickness_m=thickness, thickness_is_default=True,
        area_m2=area, is_cantilever=False, total_load_kn=100.0,
        shores=shores, grid_nx=3, grid_ny=3,
        spacing_x_m=1.5, spacing_y_m=1.2,
        selected_shore=shore, exclusions=[],
    )


def _metadata():
    return ReportMetadata(
        project_name="CVS-COB", date="2026-03-25",
        scale=1.0, dxf_filename="CVS-COB-FOR-006-R00.DXF",
    )


def _calc_result(beam_results=None, slab_results=None, warnings=None,
                 validation_errors=None):
    return CalculationResult(
        beam_results=beam_results or [],
        slab_results=slab_results or [],
        shore_catalog_used=[],
        total_shores=sum(b.shore_count for b in (beam_results or []))
                     + sum(len(s.shores) for s in (slab_results or [])),
        total_load_kn=500.0,
        pe_direito_m=2.80, pe_direito_is_default=True,
        warnings=warnings or [],
        validation_errors=validation_errors or [],
        is_valid=not bool(validation_errors),
    )


class TestBuildReportData:
    def test_returns_report_data(self):
        calc = _calc_result(beam_results=[_beam_result()])
        report = build_report_data(calc, _metadata())
        assert isinstance(report, ReportData)
        assert report.project_name == "CVS-COB"

    def test_summary_totals(self):
        calc = _calc_result(
            beam_results=[_beam_result()],
            slab_results=[_slab_result()],
        )
        report = build_report_data(calc, _metadata())
        assert report.summary.total_shores == calc.total_shores
        assert report.summary.beam_count == 1
        assert report.summary.slab_count == 1
        assert report.summary.pe_direito_is_default is True

    def test_slab_thickness_from_first_slab(self):
        calc = _calc_result(slab_results=[_slab_result(thickness=0.15)])
        report = build_report_data(calc, _metadata())
        assert report.summary.slab_thickness_m == pytest.approx(0.15)
        assert report.summary.thickness_is_default is True

    def test_slab_thickness_default_when_no_slabs(self):
        calc = _calc_result()
        report = build_report_data(calc, _metadata())
        assert report.summary.slab_thickness_m == pytest.approx(0.12)
        assert report.summary.thickness_is_default is True

    def test_beam_rows(self):
        calc = _calc_result(beam_results=[_beam_result(name="V1")])
        report = build_report_data(calc, _metadata())
        assert len(report.beam_rows) == 1
        row = report.beam_rows[0]
        assert row.name == "V1"
        assert row.section == "14x40 cm"
        assert row.section_width_m == pytest.approx(0.14)
        assert row.section_height_m == pytest.approx(0.40)
        assert row.shore_count == 7

    def test_beam_row_no_name(self):
        calc = _calc_result(beam_results=[_beam_result(name=None)])
        report = build_report_data(calc, _metadata())
        assert report.beam_rows[0].name == "Viga sem nome"

    def test_beam_row_no_section(self):
        br = _beam_result()
        br.beam.section_width_m = None
        br.beam.section_height_m = None
        calc = _calc_result(beam_results=[br])
        report = build_report_data(calc, _metadata())
        assert report.beam_rows[0].section == "N/D"

    def test_slab_rows(self):
        calc = _calc_result(slab_results=[_slab_result()])
        report = build_report_data(calc, _metadata())
        assert len(report.slab_rows) == 1
        row = report.slab_rows[0]
        assert row.panel_id == 1
        assert row.grid == "3x3"
        assert row.area_m2 == pytest.approx(20.0)

    def test_slab_row_no_shore(self):
        sr = _slab_result()
        sr.selected_shore = None
        calc = _calc_result(slab_results=[sr])
        report = build_report_data(calc, _metadata())
        assert report.slab_rows[0].shore_model == "N/A"

    def test_bom_aggregation(self):
        """Two beams using same shore model -> aggregated quantity."""
        calc = _calc_result(beam_results=[
            _beam_result(name="V1", shore_count=5, shore_id="ESC-01"),
            _beam_result(name="V2", shore_count=3, shore_id="ESC-01"),
        ])
        report = build_report_data(calc, _metadata())
        assert len(report.bom_rows) == 1
        assert report.bom_rows[0].quantity == 8
        assert report.bom_rows[0].total_weight_kg == pytest.approx(8 * 11.0)

    def test_bom_multiple_models(self):
        calc = _calc_result(
            beam_results=[_beam_result(shore_id="ESC-01", shore_count=5)],
            slab_results=[_slab_result(shore_id="ESC-02", shore_count=9)],
        )
        report = build_report_data(calc, _metadata())
        assert len(report.bom_rows) == 2
        ids = {r.id for r in report.bom_rows}
        assert ids == {"ESC-01", "ESC-02"}

    def test_warnings_include_validation_errors(self):
        calc = _calc_result(
            warnings=["Aviso 1"],
            validation_errors=["Erro: capacidade excedida"],
        )
        report = build_report_data(calc, _metadata())
        assert "Aviso 1" in report.warnings
        assert any("capacidade" in w for w in report.warnings)

    def test_empty_calculation(self):
        calc = _calc_result()
        report = build_report_data(calc, _metadata())
        assert len(report.beam_rows) == 0
        assert len(report.slab_rows) == 0
        assert len(report.bom_rows) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ./Desktop/escora-ai && python3 -m pytest tests/output/test_report_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.output'`

- [ ] **Step 3: Create package inits and report_data.py**

Create `src/output/__init__.py` and `tests/output/__init__.py` as empty files.

```python
# src/output/report_data.py
"""Extract and normalize report data from CalculationResult."""

from dataclasses import dataclass, field
from typing import List, Optional
from collections import Counter

from src.models.calculation_models import CalculationResult
from src.utils.constants import ESPESSURA_DEFAULT


@dataclass
class ReportMetadata:
    project_name: str
    date: str
    scale: float
    dxf_filename: str


@dataclass
class SummaryData:
    total_shores: int
    total_load_kn: float
    pe_direito_m: float
    pe_direito_is_default: bool
    slab_thickness_m: float
    thickness_is_default: bool
    beam_count: int
    slab_count: int
    is_valid: bool


@dataclass
class BeamRow:
    name: str
    section: str
    section_width_m: Optional[float]
    section_height_m: Optional[float]
    length_m: float
    load_kn_m: float
    shore_count: int
    spacing_m: float
    shore_model: str
    is_cantilever: bool


@dataclass
class SlabRow:
    panel_id: int
    area_m2: float
    thickness_m: float
    total_load_kn: float
    grid: str
    spacing_x_m: float
    spacing_y_m: float
    shore_model: str
    is_cantilever: bool


@dataclass
class BomRow:
    id: str
    model: str
    manufacturer: str
    quantity: int
    capacity_kn: float
    height_min_m: float
    height_max_m: float
    weight_kg: float
    total_weight_kg: float
    price_brl: float
    total_price_brl: float


@dataclass
class ReportData:
    project_name: str
    date: str
    summary: SummaryData
    beam_rows: List[BeamRow] = field(default_factory=list)
    slab_rows: List[SlabRow] = field(default_factory=list)
    bom_rows: List[BomRow] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _format_section(width_m: Optional[float], height_m: Optional[float]) -> str:
    if width_m is None or height_m is None:
        return "N/D"
    w_cm = round(width_m * 100)
    h_cm = round(height_m * 100)
    return f"{w_cm}x{h_cm} cm"


def build_report_data(
    calc: CalculationResult,
    metadata: ReportMetadata,
) -> ReportData:
    """Build normalized ReportData from CalculationResult."""

    # Summary — slab thickness from first slab or default
    if calc.slab_results:
        slab_thickness = calc.slab_results[0].thickness_m
        thickness_is_default = calc.slab_results[0].thickness_is_default
    else:
        slab_thickness = ESPESSURA_DEFAULT
        thickness_is_default = True

    summary = SummaryData(
        total_shores=calc.total_shores,
        total_load_kn=calc.total_load_kn,
        pe_direito_m=calc.pe_direito_m,
        pe_direito_is_default=calc.pe_direito_is_default,
        slab_thickness_m=slab_thickness,
        thickness_is_default=thickness_is_default,
        beam_count=len(calc.beam_results),
        slab_count=len(calc.slab_results),
        is_valid=calc.is_valid,
    )

    # Beam rows
    beam_rows = []
    for br in calc.beam_results:
        beam_rows.append(BeamRow(
            name=br.beam.name or "Viga sem nome",
            section=_format_section(br.beam.section_width_m, br.beam.section_height_m),
            section_width_m=br.beam.section_width_m,
            section_height_m=br.beam.section_height_m,
            length_m=br.beam.length_m or 0.0,
            load_kn_m=br.total_linear_load_kn_m,
            shore_count=br.shore_count,
            spacing_m=br.spacing_m,
            shore_model=br.selected_shore.model,
            is_cantilever=br.is_cantilever_start or br.is_cantilever_end,
        ))

    # Slab rows
    slab_rows = []
    for i, sr in enumerate(calc.slab_results):
        slab_rows.append(SlabRow(
            panel_id=i + 1,
            area_m2=sr.area_m2,
            thickness_m=sr.thickness_m,
            total_load_kn=sr.total_load_kn,
            grid=f"{sr.grid_nx}x{sr.grid_ny}",
            spacing_x_m=sr.spacing_x_m,
            spacing_y_m=sr.spacing_y_m,
            shore_model=sr.selected_shore.model if sr.selected_shore else "N/A",
            is_cantilever=sr.is_cantilever,
        ))

    # BOM — aggregate by shore model ID
    shore_counts: dict = {}  # id -> (ShoreCatalogEntry, count)
    for br in calc.beam_results:
        sid = br.selected_shore.id
        if sid not in shore_counts:
            shore_counts[sid] = [br.selected_shore, 0]
        shore_counts[sid][1] += br.shore_count
    for sr in calc.slab_results:
        if sr.selected_shore:
            sid = sr.selected_shore.id
            if sid not in shore_counts:
                shore_counts[sid] = [sr.selected_shore, 0]
            shore_counts[sid][1] += len(sr.shores)

    bom_rows = []
    for sid, (shore, qty) in shore_counts.items():
        bom_rows.append(BomRow(
            id=sid,
            model=shore.model,
            manufacturer=shore.manufacturer,
            quantity=qty,
            capacity_kn=shore.load_capacity_kn,
            height_min_m=shore.height_min_m,
            height_max_m=shore.height_max_m,
            weight_kg=shore.weight_kg,
            total_weight_kg=round(shore.weight_kg * qty, 2),
            price_brl=shore.price_reference_brl,
            total_price_brl=round(shore.price_reference_brl * qty, 2),
        ))

    # Warnings — merge warnings + validation_errors
    all_warnings = list(calc.warnings)
    for err in calc.validation_errors:
        all_warnings.append(f"ERRO: {err}")

    return ReportData(
        project_name=metadata.project_name,
        date=metadata.date,
        summary=summary,
        beam_rows=beam_rows,
        slab_rows=slab_rows,
        bom_rows=bom_rows,
        warnings=all_warnings,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ./Desktop/escora-ai && python3 -m pytest tests/output/test_report_data.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Run all tests**

Run: `cd ./Desktop/escora-ai && python3 -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/output/__init__.py src/output/report_data.py tests/output/__init__.py tests/output/test_report_data.py
git commit -m "feat: add ReportData models and build_report_data() extractor"
```

---

## Chunk 2: Excel Generator

### Task 2: Excel Generator

**Files:**
- Create: `src/output/excel_generator.py`
- Test: `tests/output/test_excel_generator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/output/test_excel_generator.py
"""Smoke tests for Excel report generation."""

import pytest
import os
from pathlib import Path
from openpyxl import load_workbook
from src.output.excel_generator import generate_excel
from src.output.report_data import (
    ReportData, ReportMetadata, SummaryData,
    BeamRow, SlabRow, BomRow, build_report_data,
)
from src.models.calculation_models import CalculationResult


def _empty_report():
    return ReportData(
        project_name="TEST",
        date="2026-03-25",
        summary=SummaryData(
            total_shores=0, total_load_kn=0.0,
            pe_direito_m=2.80, pe_direito_is_default=False,
            slab_thickness_m=0.12, thickness_is_default=True,
            beam_count=0, slab_count=0, is_valid=True,
        ),
    )


def _report_with_data():
    return ReportData(
        project_name="TEST",
        date="2026-03-25",
        summary=SummaryData(
            total_shores=10, total_load_kn=500.0,
            pe_direito_m=2.80, pe_direito_is_default=True,
            slab_thickness_m=0.12, thickness_is_default=True,
            beam_count=2, slab_count=1, is_valid=True,
        ),
        beam_rows=[
            BeamRow(name="V1", section="14x40 cm", section_width_m=0.14,
                    section_height_m=0.40, length_m=8.0, load_kn_m=12.5,
                    shore_count=7, spacing_m=1.2, shore_model="Escora T-01",
                    is_cantilever=False),
        ],
        slab_rows=[
            SlabRow(panel_id=1, area_m2=20.0, thickness_m=0.12,
                    total_load_kn=100.0, grid="3x3", spacing_x_m=1.5,
                    spacing_y_m=1.2, shore_model="Escora T-02",
                    is_cantilever=False),
        ],
        bom_rows=[
            BomRow(id="ESC-01", model="Escora T-01", manufacturer="Generico",
                   quantity=7, capacity_kn=20.0, height_min_m=1.80,
                   height_max_m=3.20, weight_kg=11.0, total_weight_kg=77.0,
                   price_brl=65.0, total_price_brl=455.0),
        ],
        warnings=["Pe-direito padrao"],
    )


class TestExcelGenerator:
    def test_generates_file(self, tmp_path):
        path = str(tmp_path / "test.xlsx")
        generate_excel(_report_with_data(), path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0

    def test_has_three_sheets(self, tmp_path):
        path = str(tmp_path / "test.xlsx")
        generate_excel(_report_with_data(), path)
        wb = load_workbook(path)
        assert wb.sheetnames == ["BOM", "Vigas", "Lajes"]

    def test_bom_sheet_headers(self, tmp_path):
        path = str(tmp_path / "test.xlsx")
        generate_excel(_report_with_data(), path)
        wb = load_workbook(path)
        ws = wb["BOM"]
        headers = [cell.value for cell in ws[1]]
        assert "id" in headers
        assert "modelo" in headers
        assert "quantidade" in headers

    def test_bom_sheet_data(self, tmp_path):
        path = str(tmp_path / "test.xlsx")
        generate_excel(_report_with_data(), path)
        wb = load_workbook(path)
        ws = wb["BOM"]
        assert ws.cell(row=2, column=1).value == "ESC-01"
        assert ws.cell(row=2, column=4).value == 7

    def test_vigas_sheet_data(self, tmp_path):
        path = str(tmp_path / "test.xlsx")
        generate_excel(_report_with_data(), path)
        wb = load_workbook(path)
        ws = wb["Vigas"]
        assert ws.cell(row=2, column=1).value == "V1"

    def test_lajes_sheet_data(self, tmp_path):
        path = str(tmp_path / "test.xlsx")
        generate_excel(_report_with_data(), path)
        wb = load_workbook(path)
        ws = wb["Lajes"]
        assert ws.cell(row=2, column=1).value == 1  # panel_id

    def test_empty_report_generates(self, tmp_path):
        path = str(tmp_path / "test.xlsx")
        generate_excel(_empty_report(), path)
        assert os.path.exists(path)
        wb = load_workbook(path)
        assert wb.sheetnames == ["BOM", "Vigas", "Lajes"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ./Desktop/escora-ai && python3 -m pytest tests/output/test_excel_generator.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement excel_generator.py**

```python
# src/output/excel_generator.py
"""Generate Excel workbook with BOM, Vigas, and Lajes sheets."""

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter
from src.output.report_data import ReportData


BOM_HEADERS = [
    "id", "modelo", "fabricante", "quantidade", "capacidade_kn",
    "altura_min_m", "altura_max_m", "peso_unitario_kg", "peso_total_kg",
    "preco_unitario_brl", "preco_total_brl",
]

VIGAS_HEADERS = [
    "nome", "secao_largura_m", "secao_altura_m", "comprimento_m",
    "carga_linear_kn_m", "qtd_escoras", "espacamento_m",
    "modelo_escora", "balanco",
]

LAJES_HEADERS = [
    "painel", "area_m2", "espessura_m", "carga_total_kn",
    "grid_nx", "grid_ny", "espacamento_x_m", "espacamento_y_m",
    "modelo_escora", "balanco",
]


def _write_sheet(ws, headers, rows):
    """Write headers + data rows to a worksheet."""
    bold = Font(bold=True)
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = bold
    for row_idx, row_data in enumerate(rows, 2):
        for col, value in enumerate(row_data, 1):
            ws.cell(row=row_idx, column=col, value=value)
    # Freeze header row
    ws.freeze_panes = "A2"
    # Auto-width columns
    for col in range(1, len(headers) + 1):
        max_len = len(str(headers[col - 1]))
        for row in range(2, len(rows) + 2):
            val = ws.cell(row=row, column=col).value
            if val is not None:
                max_len = max(max_len, len(str(val)))
        ws.column_dimensions[get_column_letter(col)].width = min(max_len + 2, 30)


def generate_excel(report: ReportData, output_path: str) -> str:
    """Generate Excel workbook from ReportData.

    Args:
        report: Normalized report data.
        output_path: Path to write .xlsx file.

    Returns:
        The output_path written to.
    """
    wb = Workbook()

    # Sheet 1: BOM
    ws_bom = wb.active
    ws_bom.title = "BOM"
    bom_rows = [
        [r.id, r.model, r.manufacturer, r.quantity, r.capacity_kn,
         r.height_min_m, r.height_max_m, r.weight_kg, r.total_weight_kg,
         r.price_brl, r.total_price_brl]
        for r in report.bom_rows
    ]
    _write_sheet(ws_bom, BOM_HEADERS, bom_rows)

    # Sheet 2: Vigas
    ws_vigas = wb.create_sheet("Vigas")
    vigas_rows = [
        [r.name, r.section_width_m, r.section_height_m, r.length_m,
         r.load_kn_m, r.shore_count, r.spacing_m, r.shore_model,
         "Sim" if r.is_cantilever else "Não"]
        for r in report.beam_rows
    ]
    _write_sheet(ws_vigas, VIGAS_HEADERS, vigas_rows)

    # Sheet 3: Lajes
    ws_lajes = wb.create_sheet("Lajes")
    lajes_rows = []
    for r in report.slab_rows:
        parts = r.grid.split("x")
        nx = int(parts[0]) if len(parts) == 2 else 0
        ny = int(parts[1]) if len(parts) == 2 else 0
        lajes_rows.append([
            r.panel_id, r.area_m2, r.thickness_m, r.total_load_kn,
            nx, ny, r.spacing_x_m, r.spacing_y_m, r.shore_model,
            "Sim" if r.is_cantilever else "Não",
        ])
    _write_sheet(ws_lajes, LAJES_HEADERS, lajes_rows)

    wb.save(output_path)
    return output_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ./Desktop/escora-ai && python3 -m pytest tests/output/test_excel_generator.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/output/excel_generator.py tests/output/test_excel_generator.py
git commit -m "feat: add Excel report generator (BOM + Vigas + Lajes sheets)"
```

---

## Chunk 3: PDF Generator

### Task 3: PDF Generator

**Files:**
- Create: `src/output/pdf_generator.py`
- Test: `tests/output/test_pdf_generator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/output/test_pdf_generator.py
"""Smoke tests for PDF report generation."""

import pytest
import os
from src.output.pdf_generator import generate_pdf
from src.output.report_data import (
    ReportData, SummaryData, BeamRow, SlabRow, BomRow,
)


def _empty_report():
    return ReportData(
        project_name="TEST",
        date="2026-03-25",
        summary=SummaryData(
            total_shores=0, total_load_kn=0.0,
            pe_direito_m=2.80, pe_direito_is_default=False,
            slab_thickness_m=0.12, thickness_is_default=True,
            beam_count=0, slab_count=0, is_valid=True,
        ),
    )


def _report_with_data():
    return ReportData(
        project_name="CVS-COB",
        date="2026-03-25",
        summary=SummaryData(
            total_shores=16, total_load_kn=500.0,
            pe_direito_m=2.80, pe_direito_is_default=True,
            slab_thickness_m=0.12, thickness_is_default=True,
            beam_count=2, slab_count=1, is_valid=True,
        ),
        beam_rows=[
            BeamRow(name="V1", section="14x40 cm", section_width_m=0.14,
                    section_height_m=0.40, length_m=8.0, load_kn_m=12.5,
                    shore_count=7, spacing_m=1.2, shore_model="Escora T-01",
                    is_cantilever=False),
            BeamRow(name="V2", section="14x50 cm", section_width_m=0.14,
                    section_height_m=0.50, length_m=6.0, load_kn_m=15.0,
                    shore_count=5, spacing_m=1.1, shore_model="Escora T-01",
                    is_cantilever=True),
        ],
        slab_rows=[
            SlabRow(panel_id=1, area_m2=20.0, thickness_m=0.12,
                    total_load_kn=100.0, grid="3x3", spacing_x_m=1.5,
                    spacing_y_m=1.2, shore_model="Escora T-02",
                    is_cantilever=False),
        ],
        bom_rows=[
            BomRow(id="ESC-01", model="Escora T-01", manufacturer="Generico",
                   quantity=12, capacity_kn=20.0, height_min_m=1.80,
                   height_max_m=3.20, weight_kg=11.0, total_weight_kg=132.0,
                   price_brl=65.0, total_price_brl=780.0),
            BomRow(id="ESC-02", model="Escora T-02", manufacturer="Generico",
                   quantity=9, capacity_kn=15.0, height_min_m=1.80,
                   height_max_m=3.20, weight_kg=8.0, total_weight_kg=72.0,
                   price_brl=45.0, total_price_brl=405.0),
        ],
        warnings=["Pe-direito padrao 2.80m", "ERRO: Escora #3 sobrecarregada"],
    )


class TestPdfGenerator:
    def test_generates_file(self, tmp_path):
        path = str(tmp_path / "test.pdf")
        generate_pdf(_report_with_data(), path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 1000  # non-trivial PDF

    def test_empty_report_generates(self, tmp_path):
        path = str(tmp_path / "test.pdf")
        generate_pdf(_empty_report(), path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 500

    def test_returns_output_path(self, tmp_path):
        path = str(tmp_path / "test.pdf")
        result = generate_pdf(_report_with_data(), path)
        assert result == path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ./Desktop/escora-ai && python3 -m pytest tests/output/test_pdf_generator.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement pdf_generator.py**

```python
# src/output/pdf_generator.py
"""Generate PDF shoring report using ReportLab."""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
)
from src.output.report_data import ReportData


PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 20 * mm

# Colors
HEADER_BG = colors.HexColor("#2C3E50")
HEADER_FG = colors.white
ROW_ALT = colors.HexColor("#F8F9FA")
WARNING_BG = colors.HexColor("#FFF3CD")
ERROR_BG = colors.HexColor("#F8D7DA")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading2"],
        fontSize=12,
        spaceAfter=6,
        textColor=HEADER_BG,
    ))
    styles.add(ParagraphStyle(
        name="WarningText",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#856404"),
    ))
    styles.add(ParagraphStyle(
        name="ErrorText",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#721C24"),
    ))
    return styles


def _build_table(headers, rows, col_widths=None):
    """Build a styled table with alternating rows."""
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), HEADER_FG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    # Alternating row colors
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    t.setStyle(TableStyle(style_cmds))
    return t


def generate_pdf(report: ReportData, output_path: str) -> str:
    """Generate PDF report from ReportData.

    Args:
        report: Normalized report data.
        output_path: Path to write .pdf file.

    Returns:
        The output_path written to.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )
    styles = _styles()
    elements = []

    # === HEADER ===
    elements.append(Paragraph(
        f"<b>Relatório de Escoramento</b>", styles["Title"],
    ))
    elements.append(Paragraph(
        f"Projeto: {report.project_name} &nbsp;&nbsp;|&nbsp;&nbsp; Data: {report.date}",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 8 * mm))

    # === SUMMARY ===
    elements.append(Paragraph("Resumo", styles["SectionTitle"]))
    s = report.summary
    pe_tag = " (PADRÃO)" if s.pe_direito_is_default else ""
    esp_tag = " (PADRÃO)" if s.thickness_is_default else ""
    status = "VÁLIDO" if s.is_valid else "COM ERROS"

    summary_data = [
        ["Total de escoras", str(s.total_shores)],
        ["Carga total", f"{s.total_load_kn:.1f} kN"],
        ["Pé-direito", f"{s.pe_direito_m:.2f} m{pe_tag}"],
        ["Espessura da laje", f"{s.slab_thickness_m:.2f} m{esp_tag}"],
        ["Vigas calculadas", str(s.beam_count)],
        ["Painéis de laje", str(s.slab_count)],
        ["Status", status],
    ]
    summary_table = Table(summary_data, colWidths=[50 * mm, 80 * mm])
    summary_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 8 * mm))

    # === BEAM TABLE ===
    if report.beam_rows:
        elements.append(Paragraph("Escoramento de Vigas", styles["SectionTitle"]))
        beam_headers = ["Viga", "Seção", "Comp.(m)", "Carga(kN/m)",
                        "Escoras", "Espaç.(m)", "Modelo", "Balanço"]
        beam_data = [
            [r.name, r.section, f"{r.length_m:.1f}", f"{r.load_kn_m:.1f}",
             str(r.shore_count), f"{r.spacing_m:.2f}", r.shore_model,
             "Sim" if r.is_cantilever else ""]
            for r in report.beam_rows
        ]
        elements.append(_build_table(beam_headers, beam_data))
        elements.append(Spacer(1, 6 * mm))

    # === SLAB TABLE ===
    if report.slab_rows:
        elements.append(Paragraph("Escoramento de Lajes", styles["SectionTitle"]))
        slab_headers = ["Painel", "Área(m²)", "Esp.(m)", "Carga(kN)",
                        "Grid", "Espaç.X(m)", "Espaç.Y(m)", "Modelo", "Balanço"]
        slab_data = [
            [str(r.panel_id), f"{r.area_m2:.1f}", f"{r.thickness_m:.2f}",
             f"{r.total_load_kn:.1f}", r.grid, f"{r.spacing_x_m:.2f}",
             f"{r.spacing_y_m:.2f}", r.shore_model,
             "Sim" if r.is_cantilever else ""]
            for r in report.slab_rows
        ]
        elements.append(_build_table(slab_headers, slab_data))
        elements.append(Spacer(1, 6 * mm))

    # === BOM TABLE ===
    if report.bom_rows:
        elements.append(Paragraph("Lista de Materiais (BOM)", styles["SectionTitle"]))
        bom_headers = ["Modelo", "Fabricante", "Qtd", "Capac.(kN)",
                       "Altura(m)", "Peso Un.(kg)", "Peso Total(kg)"]
        bom_data = [
            [r.model, r.manufacturer, str(r.quantity), f"{r.capacity_kn:.0f}",
             f"{r.height_min_m:.1f}-{r.height_max_m:.1f}",
             f"{r.weight_kg:.1f}", f"{r.total_weight_kg:.1f}"]
            for r in report.bom_rows
        ]
        elements.append(_build_table(bom_headers, bom_data))
        elements.append(Spacer(1, 6 * mm))

    # === WARNINGS ===
    if report.warnings:
        elements.append(Paragraph("Avisos e Erros", styles["SectionTitle"]))
        for w in report.warnings:
            if w.startswith("ERRO:"):
                elements.append(Paragraph(f"• {w}", styles["ErrorText"]))
            else:
                elements.append(Paragraph(f"• {w}", styles["WarningText"]))

    doc.build(elements)
    return output_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ./Desktop/escora-ai && python3 -m pytest tests/output/test_pdf_generator.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run all tests**

Run: `cd ./Desktop/escora-ai && python3 -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/output/pdf_generator.py tests/output/test_pdf_generator.py
git commit -m "feat: add PDF report generator with beam/slab/BOM tables"
```

- [ ] **Step 7: Push to GitHub**

```bash
git push origin main
```
