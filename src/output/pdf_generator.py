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
