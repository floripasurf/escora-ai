# PDF/BOM Report Generator — Design Spec

**Date**: 2026-03-25
**Status**: Approved
**Author**: Raphael + Claude

---

## 1. Problem

The calculation pipeline produces `CalculationResult` with beam/slab shoring data, but there's no way to export this as a deliverable report. Operators need a printable PDF for clients and an Excel file for procurement/internal use.

## 2. Solution

A report generation module that consumes `CalculationResult` and produces:
1. A PDF report (A4, professional layout, Portuguese)
2. An Excel workbook with 3 sheets (BOM, Vigas, Lajes)

No new calculations — purely formatting and data extraction.

## 3. Architecture

### Data Flow

```
CalculationResult + ReportMetadata (filename, date, scale)
        |
        v
  ReportData (normalized intermediate — pre-computed table rows)
        |
        ├──> pdf_generator.py  → .pdf file
        └──> excel_generator.py → .xlsx file
```

### ReportMetadata

Simple dataclass passed alongside `CalculationResult`:
- `project_name: str` — derived from DXF filename (strip extension)
- `date: str` — generation date
- `scale: float` — drawing scale used
- `dxf_filename: str` — original filename

### ReportData

Intermediate dataclass that pre-computes all table rows from `CalculationResult`. Generators only format — they don't extract data.

Fields:
- `project_name: str`
- `date: str`
- `summary: SummaryData` — totals, pe_direito, thickness, is_valid
- `beam_rows: List[BeamRow]` — one per beam result
- `slab_rows: List[SlabRow]` — one per slab result
- `bom_rows: List[BomRow]` — aggregated by shore model
- `warnings: List[str]` — combined from `CalculationResult.warnings` + `CalculationResult.validation_errors`

#### SummaryData
- `total_shores: int`
- `total_load_kn: float`
- `pe_direito_m: float`
- `pe_direito_is_default: bool`
- `slab_thickness_m: float` — derived from `slab_results[0].thickness_m` (all panels share the same thickness in current implementation). If no slab results, use `ESPESSURA_DEFAULT` (0.12m).
- `thickness_is_default: bool` — derived from `slab_results[0].thickness_is_default`. If no slab results, `True`.
- `beam_count: int`
- `slab_count: int`
- `is_valid: bool`

#### BeamRow
- `name: str` — beam name or "Viga sem nome"
- `section: str` — formatted "14x40 cm". When width or height is `None`, use "N/D".
- `section_width_m: Optional[float]` — raw width for Excel export
- `section_height_m: Optional[float]` — raw height for Excel export
- `length_m: float`
- `load_kn_m: float` — total linear load
- `shore_count: int`
- `spacing_m: float`
- `shore_model: str` — selected shore model name
- `is_cantilever: bool` — either end is cantilever

#### SlabRow
- `panel_id: int` — sequential panel number
- `area_m2: float`
- `thickness_m: float`
- `total_load_kn: float`
- `grid: str` — formatted "3x4"
- `spacing_x_m: float`
- `spacing_y_m: float`
- `shore_model: str`
- `is_cantilever: bool`

#### BomRow
- `id: str` — shore catalog ID
- `model: str` — shore model name
- `manufacturer: str`
- `quantity: int` — total count across all beams + slabs
- `capacity_kn: float`
- `height_min_m: float`
- `height_max_m: float`
- `weight_kg: float` — unit weight
- `total_weight_kg: float`
- `price_brl: float` — unit price reference
- `total_price_brl: float`

## 4. PDF Layout

A4 portrait, single or multi-page. Generated with ReportLab.

### Page Structure

1. **Header**
   - Title: "Relatório de Escoramento"
   - Project name (from DXF filename)
   - Date
   - Logo placeholder area (top-right, future: per-tenant logo)

2. **Summary Box**
   - Total de escoras: N
   - Carga total: X kN
   - Pé-direito: X.XX m (+ "PADRÃO" tag if default)
   - Espessura da laje: X.XX m (+ "PADRÃO" tag if default)
   - Status: "VÁLIDO" / "COM ERROS"

3. **Beam Shoring Table**
   | Viga | Seção (cm) | Comp. (m) | Carga (kN/m) | Escoras | Espaç. (m) | Modelo | Balanço |
   |------|-----------|-----------|-------------|---------|-----------|--------|---------|

4. **Slab Shoring Table**
   | Painel | Área (m²) | Esp. (m) | Carga (kN) | Grid | Espaç. X (m) | Espaç. Y (m) | Modelo | Balanço |
   |--------|----------|---------|-----------|------|-------------|-------------|--------|---------|

5. **BOM Table**
   | Modelo | Fabricante | Qtd | Capacidade (kN) | Altura (m) | Peso Unit. (kg) | Peso Total (kg) |
   |--------|-----------|-----|----------------|-----------|----------------|-----------------|

6. **Avisos e Erros Section**
   - Each warning as a bulleted line
   - Validation errors (from `validation_errors`) prefixed with "ERRO:"
   - Defaults used highlighted
   - Low-confidence elements noted

### Styling

- Clean, professional. No colors beyond header bar and warning highlights.
- Tables with alternating row shading for readability.
- Font: Helvetica (built into ReportLab, no external fonts needed).
- All text in Portuguese.

## 5. Excel Layout

Generated with openpyxl. Single `.xlsx` file with 3 sheets.

### Sheet 1: BOM
Columns match the existing CSV format for backwards compatibility:
`id, modelo, fabricante, quantidade, capacidade_kn, altura_min_m, altura_max_m, peso_unitario_kg, peso_total_kg, preco_unitario_brl, preco_total_brl`

### Sheet 2: Vigas
`nome, secao_largura_m, secao_altura_m, comprimento_m, carga_linear_kn_m, qtd_escoras, espacamento_m, modelo_escora, balanco`

### Sheet 3: Lajes
`painel, area_m2, espessura_m, carga_total_kn, grid_nx, grid_ny, espacamento_x_m, espacamento_y_m, modelo_escora, balanco`

### Formatting
- Header row bold + frozen
- Column widths auto-sized
- Number cells formatted to 2 decimal places

## 6. API Integration

The report generator is called after `run_calculation()` succeeds:

```python
from src.output.report_data import build_report_data, ReportMetadata
from src.output.pdf_generator import generate_pdf
from src.output.excel_generator import generate_excel

metadata = ReportMetadata(
    project_name="CVS-COB",
    date="2026-03-25",
    scale=1.0,
    dxf_filename="CVS-COB-FOR-006-R00.DXF",
)
report = build_report_data(calculation_result, metadata)
generate_pdf(report, output_path="output/CVS-COB-relatorio.pdf")
generate_excel(report, output_path="output/CVS-COB-bom.xlsx")
```

The runner does NOT call the generators — they are invoked by the API/CLI layer. The runner only produces `CalculationResult`.

## 7. File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/output/__init__.py` | Create | Package init |
| `src/output/report_data.py` | Create | ReportMetadata, ReportData, build_report_data() |
| `src/output/pdf_generator.py` | Create | generate_pdf(report, output_path) |
| `src/output/excel_generator.py` | Create | generate_excel(report, output_path) |
| `tests/output/__init__.py` | Create | Package init |
| `tests/output/test_report_data.py` | Create | Unit tests for data extraction |
| `tests/output/test_pdf_generator.py` | Create | PDF smoke tests (file created, non-zero size) |
| `tests/output/test_excel_generator.py` | Create | Excel smoke tests (file created, correct sheets) |

## 8. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `reportlab` | >=4.0 | PDF generation |
| `openpyxl` | >=3.1 | Excel generation |

Both are pure Python, no system dependencies.

## 9. Error Handling

- Empty `CalculationResult` (no beams, no slabs) → generate report with empty tables + "Nenhum elemento calculado" warning
- Missing shore selection on a slab → include slab row with "N/A" for shore model
- `generate_pdf` / `generate_excel` raise on I/O errors (caller handles)
- BOM aggregation: group by `ShoreCatalogEntry.id`, sum quantities and weights

## 10. Testing Strategy

- **Unit tests**: `build_report_data()` with synthetic `CalculationResult` → verify row counts, BOM aggregation, summary totals
- **Smoke tests**: `generate_pdf()` → file exists, size > 0, no exceptions
- **Smoke tests**: `generate_excel()` → file exists, 3 sheets, correct headers
- **Integration**: generate from real DXF pipeline result (CFL-SUB or CVS-COB)

## 11. Out of Scope

- Per-tenant branding (logo upload)
- DXF overlay output (shore positions drawn on structural plan)
- Email/delivery of reports
- Cost estimation beyond price_reference_brl from catalog
