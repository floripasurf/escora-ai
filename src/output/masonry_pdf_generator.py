"""Gerador de memorial de cálculo PDF para alvenaria estrutural.

Seções:
1. Normas e Referências
2. Dados de Entrada
3. Definição da Planta
4. Cálculo de Cargas por Parede
5. Verificação do Bloco (fbk)
6. Dimensionamento de Vergas e Contravergas
7. Cintas de Amarração
8. Fundações
9. Lista de Materiais (resumo)
10. Conclusão

Referências:
- NBR 15961-1:2011 — Alvenaria estrutural
- NBR 15575:2013 — Desempenho de edificações
- NBR 6120:2019 — Ações para cálculo
"""

import logging
from datetime import date
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
)

from src.models.masonry import MasonryProject
from src.utils.masonry_constants import (
    GAMMA_ALVENARIA, GAMMA_F, GAMMA_M, ETA_PRISMA,
    WALL_CAPACITY_KN_PER_M, MIN_ROOM_AREAS,
)

logger = logging.getLogger(__name__)

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 20 * mm

HEADER_BG = colors.HexColor("#1B4332")
HEADER_FG = colors.white
ROW_ALT = colors.HexColor("#F0FFF4")
ACCENT_BG = colors.HexColor("#D8F3DC")
OK_COLOR = colors.HexColor("#2D6A4F")
WARN_COLOR = colors.HexColor("#E76F51")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading2"],
        fontSize=12, spaceAfter=6,
        textColor=HEADER_BG,
    ))
    styles.add(ParagraphStyle(
        name="SubSection",
        parent=styles["Heading3"],
        fontSize=10, spaceAfter=4, spaceBefore=8,
        textColor=HEADER_BG,
    ))
    styles.add(ParagraphStyle(
        name="Formula",
        parent=styles["Normal"],
        fontSize=9, fontName="Courier", spaceAfter=4,
        leftIndent=10 * mm,
    ))
    styles.add(ParagraphStyle(
        name="Check",
        parent=styles["Normal"],
        fontSize=9, spaceAfter=2,
    ))
    return styles


def _build_table(headers, rows, col_widths=None):
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
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    t.setStyle(TableStyle(style_cmds))
    return t


def generate_masonry_memorial(
    project: MasonryProject,
    output_path: str,
) -> str:
    """Gera memorial de cálculo PDF para projeto de alvenaria estrutural.

    Args:
        project: Projeto completo com cargas calculadas
        output_path: Caminho do PDF

    Returns:
        Caminho do arquivo salvo
    """
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )
    styles = _styles()
    el = []

    inp = project.input
    today = date.today().strftime("%d/%m/%Y")

    # === HEADER ===
    el.append(Paragraph(
        "<b>MEMORIAL DE CÁLCULO — ALVENARIA ESTRUTURAL</b>",
        styles["Title"],
    ))
    el.append(Paragraph(
        f"Data: {today} &nbsp;|&nbsp; "
        f"Área: {inp.target_area_m2:.0f}m² &nbsp;|&nbsp; "
        f"Bloco: {inp.block_size.value}cm",
        styles["Normal"],
    ))
    el.append(Spacer(1, 4 * mm))
    el.append(HRFlowable(width="100%", thickness=1, color=HEADER_BG))
    el.append(Spacer(1, 6 * mm))

    # === 1. NORMAS ===
    el.append(Paragraph("1. Normas e Referências", styles["SectionTitle"]))
    normas = [
        "NBR 15961-1:2011 — Alvenaria estrutural — Blocos de concreto — Projeto",
        "NBR 15575:2013 — Edificações habitacionais — Desempenho",
        "NBR 6120:2019 — Ações para o cálculo de estruturas",
        "NBR 6118:2023 — Projeto de estruturas de concreto",
        "NBR 6122:2019 — Projeto e execução de fundações",
        "NBR 14859-1:2016 — Lajes pré-fabricadas de concreto",
    ]
    for n in normas:
        el.append(Paragraph(f"• {n}", styles["Normal"]))
    el.append(Spacer(1, 6 * mm))

    # === 2. DADOS DE ENTRADA ===
    el.append(Paragraph("2. Dados de Entrada", styles["SectionTitle"]))
    input_data = [
        ["Parâmetro", "Valor", "Referência"],
        ["Pavimentos", str(inp.floors), "Input"],
        ["Área alvo", f"{inp.target_area_m2:.0f} m²", "Input"],
        ["Quartos", str(inp.bedrooms), "Input"],
        ["Banheiros", str(inp.bathrooms), "Input"],
        ["Lote", f"{inp.lot_width_m:.1f} × {inp.lot_depth_m:.1f} m", "Input"],
        ["Bloco", f"{inp.block_size.value} cm", "NBR 15961-1"],
        ["Pé-direito", f"{inp.ceiling_height_m:.2f} m", "Input"],
        ["Solo (σ_adm)", f"{inp.soil_capacity_kpa:.0f} kPa", "Input / Sondagem"],
        ["γ_alvenaria", f"{GAMMA_ALVENARIA:.1f} kN/m³", "NBR 6120:2019"],
        ["γf (majoração)", f"{GAMMA_F:.1f}", "NBR 15961-1"],
        ["γm (minoração)", f"{GAMMA_M:.1f}", "NBR 15961-1"],
        ["η (eficiência)", f"{ETA_PRISMA:.2f}", "NBR 15961-1"],
    ]
    t = Table(input_data, colWidths=[55 * mm, 45 * mm, 50 * mm])
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

    # === 3. PLANTA ===
    if project.floor_plans:
        floor = project.floor_plans[0]
        el.append(Paragraph("3. Definição da Planta", styles["SectionTitle"]))
        el.append(Paragraph(
            f"Dimensões: {floor.width_m:.2f} × {floor.depth_m:.2f} m "
            f"= {floor.width_m * floor.depth_m:.1f} m²",
            styles["Normal"],
        ))
        el.append(Spacer(1, 3 * mm))

        # Room table
        room_headers = ["Cômodo", "Tipo", "Área (m²)", "Mín. NBR (m²)", "Status"]
        room_rows = []
        for room in floor.rooms:
            min_a = MIN_ROOM_AREAS.get(room.type.value, 2.0)
            area = room.area_m2
            ok = "OK" if area >= min_a * 0.95 else "VERIFICAR"
            room_rows.append([
                room.name, room.type.value, f"{area:.1f}",
                f"{min_a:.1f}", ok,
            ])
        el.append(_build_table(room_headers, room_rows))
        el.append(Spacer(1, 6 * mm))

    # === 4. CARGAS POR PAREDE ===
    if project.floor_plans:
        floor = project.floor_plans[0]
        el.append(Paragraph("4. Cálculo de Cargas por Parede", styles["SectionTitle"]))

        wall_headers = ["Parede", "Comp.(m)", "Esp.(cm)", "Nd (kN/m)", "Aberturas"]
        wall_rows = []
        for wall in floor.walls:
            if not wall.is_structural:
                continue
            n_openings = len(wall.openings)
            wall_rows.append([
                wall.id,
                f"{wall.length_m:.2f}",
                f"{wall.thickness_m*100:.0f}",
                f"{wall.load_kn_per_m:.1f}",
                str(n_openings) if n_openings > 0 else "—",
            ])

        if wall_rows:
            el.append(_build_table(wall_headers, wall_rows))
        el.append(Spacer(1, 6 * mm))

    # === 5. VERIFICAÇÃO DO BLOCO ===
    el.append(Paragraph("5. Verificação do Bloco Estrutural", styles["SectionTitle"]))

    thickness_cm = int(inp.block_size.value)
    max_load = 0.0
    if project.floor_plans:
        for wall in project.floor_plans[0].walls:
            if wall.is_structural:
                max_load = max(max_load, wall.load_kn_per_m)

    capacity = WALL_CAPACITY_KN_PER_M.get(
        (project.block_fbk_mpa, thickness_cm), 0
    )

    el.append(Paragraph("Verificação:", styles["Check"]))
    el.append(Paragraph(
        f"Nd,max = {max_load:.1f} kN/m (parede mais carregada)",
        styles["Formula"],
    ))
    el.append(Paragraph(
        f"Rd = (η × fbk × t) / γm = "
        f"({ETA_PRISMA} × {project.block_fbk_mpa*1000:.0f} × {thickness_cm/100:.2f}) / {GAMMA_M} "
        f"= {capacity:.1f} kN/m",
        styles["Formula"],
    ))

    ok = capacity >= max_load
    status = "OK — Nd ≤ Rd" if ok else "NÃO CONFORME — Nd > Rd"
    el.append(Paragraph(
        f"<b>Resultado: {status}</b>",
        styles["Check"],
    ))
    el.append(Spacer(1, 6 * mm))

    # === 6. VERGAS ===
    if project.floor_plans and project.floor_plans[0].lintels:
        el.append(Paragraph("6. Vergas e Contravergas", styles["SectionTitle"]))

        lintel_headers = ["Parede", "Vão (m)", "Seção (cm)", "Armadura"]
        lintel_rows = []
        for lintel in project.floor_plans[0].lintels:
            lintel_rows.append([
                lintel.wall_id,
                f"{lintel.span_m:.2f}",
                f"{lintel.width_m*100:.0f}×{lintel.height_m*100:.0f}",
                lintel.rebar,
            ])
        el.append(_build_table(lintel_headers, lintel_rows))
        el.append(Spacer(1, 6 * mm))

    # === 7. CINTAS ===
    if project.floor_plans and project.floor_plans[0].tie_beams:
        el.append(Paragraph("7. Cintas de Amarração", styles["SectionTitle"]))
        for tb in project.floor_plans[0].tie_beams:
            el.append(Paragraph(
                f"Cinta de {tb.level}: seção {tb.width_m*100:.0f}×{tb.height_m*100:.0f}cm, "
                f"armadura {tb.rebar}",
                styles["Normal"],
            ))
        el.append(Spacer(1, 6 * mm))

    # === 8. FUNDAÇÕES ===
    if project.foundations:
        el.append(Paragraph("8. Fundações", styles["SectionTitle"]))
        for i, f in enumerate(project.foundations):
            if f.type.value == "sapata_corrida":
                el.append(Paragraph(
                    f"Sapata corrida: B={f.width_m:.2f}m, H={f.height_m:.2f}m, "
                    f"Prof.={f.depth_m:.2f}m",
                    styles["Normal"],
                ))
                el.append(Paragraph(
                    f"Nd = {f.load_per_m_kn:.1f} kN/m, "
                    f"σ_solo = {f.soil_capacity_kpa:.0f} kPa, "
                    f"σ_at = {f.load_per_m_kn/f.width_m:.1f} kPa"
                    if f.width_m > 0 else "",
                    styles["Formula"],
                ))
            else:
                el.append(Paragraph(
                    f"Radier: {f.width_m:.1f}×{f.width_m:.1f}m, "
                    f"H={f.height_m:.2f}m, {f.rebar}",
                    styles["Normal"],
                ))
        el.append(Spacer(1, 6 * mm))

    # === 9. RESUMO BOM ===
    el.append(Paragraph("9. Resumo de Materiais", styles["SectionTitle"]))
    el.append(Paragraph(
        f"Total de blocos: {project.total_block_count} unidades "
        f"(fbk ≥ {project.block_fbk_mpa:.1f} MPa)",
        styles["Normal"],
    ))
    el.append(Paragraph(
        f"Área total de paredes: {project.total_wall_area_m2:.1f} m²",
        styles["Normal"],
    ))
    el.append(Spacer(1, 6 * mm))

    # === 10. CONCLUSÃO ===
    el.append(Paragraph("10. Conclusão", styles["SectionTitle"]))
    has_warnings = bool(project.warnings)
    if not has_warnings:
        el.append(Paragraph(
            "O projeto de alvenaria estrutural atende aos requisitos das "
            "normas NBR 15961-1:2011 e NBR 15575:2013.",
            styles["Normal"],
        ))
    else:
        el.append(Paragraph(
            "O projeto apresenta os seguintes avisos que devem ser verificados:",
            styles["Normal"],
        ))
        for w in project.warnings[:20]:
            el.append(Paragraph(f"• {w}", styles["Check"]))

    el.append(Spacer(1, 12 * mm))
    el.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    el.append(Paragraph(
        "<i>Documento gerado automaticamente por Estrutura.AI — "
        "sujeito à validação do engenheiro responsável (ART/RRT).</i>",
        styles["Normal"],
    ))

    doc.build(el)
    logger.info(f"Memorial de cálculo salvo: {output_path}")
    return output_path
