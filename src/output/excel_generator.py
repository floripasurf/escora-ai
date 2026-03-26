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
