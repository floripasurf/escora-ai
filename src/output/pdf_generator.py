"""Generate PDF shoring report using ReportLab.

Generates three document types:
1. Relatório de Escoramento — summary + tables (existing)
2. Memória de Cálculo — detailed normative verification (NBR 15696)
3. Proposta Comercial / Orçamento — commercial budget with prices
"""

from datetime import date
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
    PageBreak, KeepTogether,
)
from src.output.report_data import ReportData
from src.utils.constants import (
    GAMMA_CONCRETO, GAMMA_F, Q_SOBRECARGA_DEFAULT, ESPESSURA_DEFAULT,
    ESPACAMENTO_MAX_DEFAULT, ESPACAMENTO_MAX_VIGA, ESPACAMENTO_POR_ALTURA,
    CONTRA_FLECHA, DISTANCIA_BORDA_MIN, DISTANCIA_PILAR_MIN,
)


PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 20 * mm

# Colors
HEADER_BG = colors.HexColor("#2C3E50")
HEADER_FG = colors.white
ROW_ALT = colors.HexColor("#F8F9FA")
WARNING_BG = colors.HexColor("#FFF3CD")
ERROR_BG = colors.HexColor("#F8D7DA")
ACCENT_BG = colors.HexColor("#EBF5FB")
OK_COLOR = colors.HexColor("#27AE60")
WARN_COLOR = colors.HexColor("#F39C12")
FAIL_COLOR = colors.HexColor("#E74C3C")


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


# =============================================================================
# MEMÓRIA DE CÁLCULO — Detailed normative verification document
# =============================================================================

def generate_memoria_calculo(report: ReportData, output_path: str) -> str:
    """Generate Memória de Cálculo PDF — detailed normative verification.

    This is the engineering calculation report that documents every
    verification step per NBR 15696:2009 and NBR 6120:2019.
    """
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )
    styles = _styles()
    styles.add(ParagraphStyle(
        name="Formula", parent=styles["Normal"],
        fontSize=9, fontName="Courier", spaceAfter=4,
        leftIndent=10 * mm,
    ))
    styles.add(ParagraphStyle(
        name="Check", parent=styles["Normal"],
        fontSize=9, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="SubSection", parent=styles["Heading3"],
        fontSize=10, spaceAfter=4, spaceBefore=8,
        textColor=HEADER_BG,
    ))
    el = []  # elements

    # --- HEADER ---
    el.append(Paragraph("<b>MEMÓRIA DE CÁLCULO DE ESCORAMENTO</b>", styles["Title"]))
    el.append(Paragraph(
        f"Projeto: {report.project_name} &nbsp;|&nbsp; Data: {report.date}",
        styles["Normal"],
    ))
    el.append(Spacer(1, 4 * mm))
    el.append(HRFlowable(width="100%", thickness=1, color=HEADER_BG))
    el.append(Spacer(1, 6 * mm))

    # --- 1. NORMAS E REFERÊNCIAS ---
    el.append(Paragraph("1. Normas e Referências", styles["SectionTitle"]))
    normas = [
        "NBR 15696:2009 — Fôrmas e escoramentos para estruturas de concreto",
        "NBR 6120:2019 — Ações para o cálculo de estruturas de edificações",
        "NBR 14931:2004 — Execução de estruturas de concreto — Procedimento",
        "Manual de Lajes Martins — Espaçamento entre escoras",
    ]
    for n in normas:
        el.append(Paragraph(f"• {n}", styles["Normal"]))
    el.append(Spacer(1, 6 * mm))

    # --- 2. DADOS DE ENTRADA ---
    el.append(Paragraph("2. Dados de Entrada", styles["SectionTitle"]))
    s = report.summary
    pe_nota = " (valor padrão — não encontrado no DXF)" if s.pe_direito_is_default else ""
    esp_nota = " (valor padrão)" if s.thickness_is_default else ""

    input_data = [
        ["Parâmetro", "Valor", "Referência"],
        ["Pé-direito (H)", f"{s.pe_direito_m:.2f} m{pe_nota}", "DXF / input"],
        ["Espessura da laje (h)", f"{s.slab_thickness_m:.2f} m{esp_nota}", "DXF / input"],
        ["Peso específico concreto (γc)", f"{GAMMA_CONCRETO:.1f} kN/m³", "NBR 6120:2019"],
        ["Sobrecarga de trabalho (q)", f"{Q_SOBRECARGA_DEFAULT:.1f} kN/m²", "NBR 15696:2009"],
        ["Coeficiente de majoração (γf)", f"{GAMMA_F:.1f}", "NBR 15696:2009"],
        ["Vigas identificadas", str(s.beam_count), "Parser DXF"],
        ["Painéis de laje", str(s.slab_count), "Derivação geométrica"],
    ]
    t = Table(input_data, colWidths=[55 * mm, 50 * mm, 50 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), HEADER_FG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    el.append(t)
    el.append(Spacer(1, 6 * mm))

    # --- 3. CRITÉRIOS DE ESPAÇAMENTO ---
    el.append(Paragraph("3. Critérios de Espaçamento", styles["SectionTitle"]))
    el.append(Paragraph("3.1 Lajes — Manual Lajes Martins", styles["SubSection"]))

    esp_data = [["Espessura (cm)", "Espaçamento máx. (m)"]]
    for (min_cm, max_cm), spacing in ESPACAMENTO_POR_ALTURA.items():
        esp_data.append([f"{min_cm} – {max_cm}", f"{spacing:.2f}"])
    el.append(_build_table(esp_data[0], esp_data[1:], col_widths=[50 * mm, 50 * mm]))
    el.append(Spacer(1, 4 * mm))

    el.append(Paragraph("3.2 Vigas", styles["SubSection"]))
    el.append(Paragraph(
        f"Espaçamento máximo entre escoras de viga: <b>{ESPACAMENTO_MAX_VIGA:.2f} m</b>",
        styles["Normal"],
    ))
    el.append(Paragraph(
        f"Distância mínima ao pilar: <b>{DISTANCIA_PILAR_MIN:.2f} m</b> (face do pilar)",
        styles["Normal"],
    ))
    el.append(Paragraph(
        f"Distância mínima à borda da laje: <b>{DISTANCIA_BORDA_MIN:.2f} m</b>",
        styles["Normal"],
    ))
    el.append(Spacer(1, 6 * mm))

    # --- 4. VERIFICAÇÃO DAS VIGAS ---
    if report.beam_rows:
        el.append(Paragraph("4. Verificação das Vigas", styles["SectionTitle"]))

        for i, br in enumerate(report.beam_rows, 1):
            beam_section = []
            beam_section.append(Paragraph(
                f"<b>4.{i} Viga: {br.name}</b>", styles["SubSection"],
            ))

            # Geometry
            w_cm = br.section_width_m * 100 if br.section_width_m else 0
            h_cm = br.section_height_m * 100 if br.section_height_m else 0
            beam_section.append(Paragraph(
                f"Seção: {w_cm:.0f} x {h_cm:.0f} cm &nbsp;|&nbsp; "
                f"Comprimento: {br.length_m:.2f} m &nbsp;|&nbsp; "
                f"Balanço: {'Sim' if br.is_cantilever else 'Não'}",
                styles["Normal"],
            ))

            # Load calculation
            h_m = br.section_height_m or 0
            w_m = br.section_width_m or 0
            pp_viga = GAMMA_CONCRETO * w_m * h_m
            thickness = s.slab_thickness_m
            pp_laje_contrib = GAMMA_CONCRETO * thickness * 0.5  # half-span contribution

            beam_section.append(Paragraph("Cálculo de cargas:", styles["Check"]))
            beam_section.append(Paragraph(
                f"Peso próprio viga: γc × b × h = {GAMMA_CONCRETO} × {w_m:.3f} × {h_m:.3f} "
                f"= {pp_viga:.2f} kN/m",
                styles["Formula"],
            ))
            beam_section.append(Paragraph(
                f"Carga linear total majorada: q = {br.load_kn_m:.2f} kN/m",
                styles["Formula"],
            ))
            beam_section.append(Paragraph(
                f"Carga total na viga: Q = q × L = {br.load_kn_m:.2f} × {br.length_m:.2f} "
                f"= {br.load_kn_m * br.length_m:.2f} kN",
                styles["Formula"],
            ))

            # Shore verification
            beam_section.append(Paragraph("Verificação do escoramento:", styles["Check"]))
            beam_section.append(Paragraph(
                f"Modelo: {br.shore_model} &nbsp;|&nbsp; "
                f"Quantidade: {br.shore_count} &nbsp;|&nbsp; "
                f"Espaçamento: {br.spacing_m:.2f} m",
                styles["Formula"],
            ))

            if br.shore_count > 0:
                load_per = (br.load_kn_m * br.length_m) / br.shore_count
                beam_section.append(Paragraph(
                    f"Carga por escora: Q/n = {br.load_kn_m * br.length_m:.2f} / {br.shore_count} "
                    f"= {load_per:.2f} kN",
                    styles["Formula"],
                ))

            # Spacing check
            ok_spacing = br.spacing_m <= ESPACAMENTO_MAX_VIGA
            status = "OK" if ok_spacing else "NÃO CONFORME"
            beam_section.append(Paragraph(
                f"Espaçamento {br.spacing_m:.2f}m ≤ {ESPACAMENTO_MAX_VIGA:.2f}m → <b>{status}</b>",
                styles["Check"],
            ))

            # Contra-flecha
            for (vao_min, vao_max), flecha_m in CONTRA_FLECHA.items():
                if vao_min <= br.length_m < vao_max:
                    beam_section.append(Paragraph(
                        f"Contra-flecha recomendada (vão {br.length_m:.1f}m): "
                        f"<b>{flecha_m*100:.1f} cm</b> na escora central",
                        styles["Check"],
                    ))
                    break

            el.append(KeepTogether(beam_section))
            el.append(Spacer(1, 4 * mm))

    # --- 5. VERIFICAÇÃO DAS LAJES ---
    if report.slab_rows:
        el.append(Paragraph("5. Verificação das Lajes", styles["SectionTitle"]))

        for sr in report.slab_rows:
            slab_section = []
            slab_section.append(Paragraph(
                f"<b>5.{sr.panel_id} Painel de Laje #{sr.panel_id}</b>",
                styles["SubSection"],
            ))
            slab_section.append(Paragraph(
                f"Área: {sr.area_m2:.1f} m² &nbsp;|&nbsp; "
                f"Espessura: {sr.thickness_m:.2f} m &nbsp;|&nbsp; "
                f"Balanço: {'Sim' if sr.is_cantilever else 'Não'}",
                styles["Normal"],
            ))

            # Load
            pp = GAMMA_CONCRETO * sr.thickness_m * sr.area_m2
            sc = Q_SOBRECARGA_DEFAULT * sr.area_m2
            total_char = pp + sc
            total_maj = total_char * GAMMA_F

            slab_section.append(Paragraph("Cálculo de cargas:", styles["Check"]))
            slab_section.append(Paragraph(
                f"Peso próprio: γc × h × A = {GAMMA_CONCRETO} × {sr.thickness_m:.3f} × {sr.area_m2:.1f} "
                f"= {pp:.2f} kN",
                styles["Formula"],
            ))
            slab_section.append(Paragraph(
                f"Sobrecarga: q × A = {Q_SOBRECARGA_DEFAULT} × {sr.area_m2:.1f} = {sc:.2f} kN",
                styles["Formula"],
            ))
            slab_section.append(Paragraph(
                f"Carga característica: {total_char:.2f} kN",
                styles["Formula"],
            ))
            slab_section.append(Paragraph(
                f"Carga majorada (×{GAMMA_F}): <b>{total_maj:.2f} kN</b> "
                f"(calculado: {sr.total_load_kn:.2f} kN)",
                styles["Formula"],
            ))

            # Grid
            slab_section.append(Paragraph("Verificação do escoramento:", styles["Check"]))
            slab_section.append(Paragraph(
                f"Grid: {sr.grid} &nbsp;|&nbsp; "
                f"Espaçamento: {sr.spacing_x_m:.2f} × {sr.spacing_y_m:.2f} m &nbsp;|&nbsp; "
                f"Modelo: {sr.shore_model}",
                styles["Formula"],
            ))

            # Spacing check
            thickness_cm = round(sr.thickness_m * 100)
            max_esp = ESPACAMENTO_MAX_DEFAULT
            for (min_cm, max_cm), esp in ESPACAMENTO_POR_ALTURA.items():
                if min_cm <= thickness_cm <= max_cm:
                    max_esp = esp
                    break
            ok_x = sr.spacing_x_m <= max_esp
            ok_y = sr.spacing_y_m <= max_esp
            slab_section.append(Paragraph(
                f"Esp. X: {sr.spacing_x_m:.2f}m ≤ {max_esp:.2f}m → <b>{'OK' if ok_x else 'NÃO CONFORME'}</b> "
                f"&nbsp;|&nbsp; "
                f"Esp. Y: {sr.spacing_y_m:.2f}m ≤ {max_esp:.2f}m → <b>{'OK' if ok_y else 'NÃO CONFORME'}</b>",
                styles["Check"],
            ))

            el.append(KeepTogether(slab_section))
            el.append(Spacer(1, 4 * mm))

    # --- 6. CONCLUSÃO ---
    el.append(Paragraph("6. Conclusão", styles["SectionTitle"]))
    status_txt = (
        "O escoramento proposto atende aos requisitos normativos da NBR 15696:2009."
        if s.is_valid else
        "O escoramento apresenta não conformidades que devem ser corrigidas antes da execução."
    )
    el.append(Paragraph(status_txt, styles["Normal"]))
    el.append(Spacer(1, 4 * mm))

    if report.warnings:
        el.append(Paragraph("Observações:", styles["SubSection"]))
        for w in report.warnings[:30]:
            style = styles["ErrorText"] if w.startswith("ERRO:") else styles["WarningText"]
            el.append(Paragraph(f"• {w}", style))

    el.append(Spacer(1, 12 * mm))
    el.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    el.append(Paragraph(
        "<i>Documento gerado automaticamente por Escora.AI — "
        "sujeito à validação do engenheiro responsável.</i>",
        styles["Normal"],
    ))

    doc.build(el)
    return output_path


# =============================================================================
# PROPOSTA COMERCIAL / ORÇAMENTO
# =============================================================================

def generate_orcamento(report: ReportData, output_path: str,
                       client_name: str = "",
                       validity_days: int = 15,
                       delivery_days: int = 3,
                       rental_period_days: int = 30,
                       ) -> str:
    """Generate commercial budget/proposal PDF.

    Args:
        report: Normalized report data with BOM and prices.
        output_path: Path to write .pdf file.
        client_name: Client/company name for the proposal.
        validity_days: Proposal validity in days.
        delivery_days: Equipment delivery time in days.
        rental_period_days: Default rental period in days.

    Returns:
        The output_path written to.
    """
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )
    styles = _styles()
    styles.add(ParagraphStyle(
        name="Right", parent=styles["Normal"],
        alignment=2,  # RIGHT
        fontSize=9,
    ))
    styles.add(ParagraphStyle(
        name="SmallNote", parent=styles["Normal"],
        fontSize=7, textColor=colors.grey,
    ))
    el = []

    today = report.date or date.today().isoformat()

    # --- HEADER ---
    el.append(Paragraph("<b>PROPOSTA COMERCIAL</b>", styles["Title"]))
    el.append(Paragraph("Locação de Equipamentos para Escoramento", styles["Normal"]))
    el.append(Spacer(1, 4 * mm))
    el.append(HRFlowable(width="100%", thickness=1, color=HEADER_BG))
    el.append(Spacer(1, 6 * mm))

    # --- PROPOSAL INFO ---
    info_data = [
        ["Projeto:", report.project_name],
        ["Cliente:", client_name or "(a definir)"],
        ["Data:", today],
        ["Validade:", f"{validity_days} dias"],
        ["Prazo de entrega:", f"{delivery_days} dias úteis"],
        ["Período de locação:", f"{rental_period_days} dias"],
    ]
    info_table = Table(info_data, colWidths=[45 * mm, 110 * mm])
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    el.append(info_table)
    el.append(Spacer(1, 8 * mm))

    # --- SCOPE ---
    el.append(Paragraph("1. Escopo", styles["SectionTitle"]))
    s = report.summary
    el.append(Paragraph(
        f"Fornecimento de equipamentos para escoramento de {s.beam_count} vigas "
        f"e {s.slab_count} painéis de laje, conforme projeto técnico analisado. "
        f"Pé-direito: {s.pe_direito_m:.2f}m. "
        f"Espessura da laje: {s.slab_thickness_m:.2f}m. "
        f"Carga total calculada: {s.total_load_kn:.1f} kN.",
        styles["Normal"],
    ))
    el.append(Spacer(1, 6 * mm))

    # --- EQUIPMENT TABLE ---
    el.append(Paragraph("2. Equipamentos e Valores", styles["SectionTitle"]))

    if report.bom_rows:
        equip_headers = [
            "Item", "Modelo", "Fabricante", "Qtd",
            "Valor Unit. (R$)", "Valor Total (R$)",
        ]
        equip_rows = []
        subtotal = 0.0
        for i, r in enumerate(report.bom_rows, 1):
            equip_rows.append([
                str(i), r.model, r.manufacturer, str(r.quantity),
                f"{r.price_brl:.2f}", f"{r.total_price_brl:.2f}",
            ])
            subtotal += r.total_price_brl

        # Add weight info
        total_weight = sum(r.total_weight_kg for r in report.bom_rows)

        equip_table = _build_table(equip_headers, equip_rows,
                                   col_widths=[12*mm, 40*mm, 30*mm, 15*mm, 28*mm, 28*mm])
        el.append(equip_table)
        el.append(Spacer(1, 4 * mm))

        # --- TOTALS ---
        monthly_total = subtotal  # prices are per month rental
        period_total = monthly_total * (rental_period_days / 30.0)

        totals_data = [
            ["Subtotal mensal (locação):", f"R$ {monthly_total:.2f}"],
            [f"Valor para {rental_period_days} dias:", f"R$ {period_total:.2f}"],
            ["Peso total dos equipamentos:", f"{total_weight:.1f} kg"],
            ["Frete:", "A combinar"],
            ["Montagem/Desmontagem:", "A combinar"],
        ]
        totals_table = Table(totals_data, colWidths=[80 * mm, 50 * mm])
        totals_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEABOVE", (0, 0), (-1, 0), 1, HEADER_BG),
            ("BACKGROUND", (0, 1), (-1, 1), ACCENT_BG),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ]))
        el.append(totals_table)
    else:
        el.append(Paragraph(
            "Nenhum equipamento identificado para este projeto.",
            styles["Normal"],
        ))
    el.append(Spacer(1, 8 * mm))

    # --- TECHNICAL SUMMARY ---
    el.append(Paragraph("3. Resumo Técnico", styles["SectionTitle"]))
    tech_items = [
        f"Total de escoras/torres: {s.total_shores}",
        f"Norma de referência: NBR 15696:2009",
        f"Coeficiente de majoração: γf = {GAMMA_F}",
        f"Sobrecarga de trabalho: {Q_SOBRECARGA_DEFAULT} kN/m²",
    ]
    for item in tech_items:
        el.append(Paragraph(f"• {item}", styles["Normal"]))
    el.append(Spacer(1, 6 * mm))

    # --- CONDITIONS ---
    el.append(Paragraph("4. Condições Gerais", styles["SectionTitle"]))
    conditions = [
        f"Esta proposta tem validade de {validity_days} dias a partir da data de emissão.",
        f"Prazo de entrega estimado: {delivery_days} dias úteis após confirmação do pedido.",
        f"Período mínimo de locação: {rental_period_days} dias.",
        "Os equipamentos serão entregues em perfeito estado de conservação e funcionamento.",
        "A montagem e desmontagem são de responsabilidade do locatário, salvo acordo contrário.",
        "O projeto de escoramento deve ser validado por engenheiro responsável (ART/RRT).",
        "Valores não incluem frete, montagem/desmontagem ou seguro, salvo indicação contrária.",
        "Danos aos equipamentos por mau uso serão cobrados conforme tabela de reposição.",
    ]
    for i, cond in enumerate(conditions, 1):
        el.append(Paragraph(f"{i}. {cond}", styles["Normal"]))
    el.append(Spacer(1, 10 * mm))

    # --- SIGNATURES ---
    el.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    el.append(Spacer(1, 15 * mm))

    sig_data = [
        ["_" * 35, "", "_" * 35],
        ["Locador", "", "Locatário"],
        ["", "", client_name or ""],
    ]
    sig_table = Table(sig_data, colWidths=[60 * mm, 30 * mm, 60 * mm])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    el.append(sig_table)

    el.append(Spacer(1, 8 * mm))
    el.append(Paragraph(
        "<i>Proposta gerada automaticamente por Escora.AI</i>",
        styles["SmallNote"],
    ))

    doc.build(el)
    return output_path
