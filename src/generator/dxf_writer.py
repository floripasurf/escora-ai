"""Geração de arquivo DXF com escoras posicionadas."""

import ezdxf
from typing import List, Optional, TYPE_CHECKING
from src.models.project import ShoringResult
from src.models.calculation_models import CalculationResult
from src.utils.labels import CATEGORY_DXF_COLOR

if TYPE_CHECKING:
    from src.output.report_data import ReportData


def _centroid_or_representative(polygon):
    """Retorna (x, y) de um ponto seguro dentro do polígono.

    Centróide pode cair fora do polígono (lajes em U, painéis com furo), então
    usamos `representative_point()` como fallback quando centróide não está
    contido.
    """
    try:
        c = polygon.centroid
        if polygon.contains(c):
            return float(c.x), float(c.y)
    except Exception:
        pass
    try:
        r = polygon.representative_point()
        return float(r.x), float(r.y)
    except Exception:
        try:
            c = polygon.centroid
            return float(c.x), float(c.y)
        except Exception:
            return 0.0, 0.0


def _ensure_layer(doc, name: str, color: int) -> None:
    """Cria layer se ainda não existir."""
    if name not in doc.layers:
        doc.layers.add(name, color=color)


def _write_volume_label(msp, polygon, label: str, area_m2: float,
                         pe_direito_m: float, volume_m3: float,
                         color: int) -> None:
    """Escreve anotação de volume no centróide do painel (layer VOLUMES)."""
    cx, cy = _centroid_or_representative(polygon)
    line1 = label or "Painel"
    line2 = f"{area_m2:.1f} m² × {pe_direito_m:.2f} m = {volume_m3:.1f} m³"

    # Usa MTEXT para controlar duas linhas e cor por entidade (mesmo layer).
    try:
        mtext = msp.add_mtext(
            f"{line1}\\P{line2}",
            dxfattribs={"layer": "VOLUMES", "color": color, "char_height": 0.18},
        )
        mtext.set_location((cx, cy))
    except Exception:
        # Fallback: dois TEXT empilhados.
        msp.add_text(
            line1,
            height=0.18,
            dxfattribs={"layer": "VOLUMES", "color": color, "insert": (cx, cy + 0.15)},
        )
        msp.add_text(
            line2,
            height=0.16,
            dxfattribs={"layer": "VOLUMES", "color": color, "insert": (cx, cy - 0.05)},
        )


def _write_totalizer_block(msp, results: List[ShoringResult],
                            calc_result: Optional[CalculationResult]):
    """Insere bloco com totais (bruto, vigas, pilares, líquido) acima do bbox.

    Retorna (origin_x, min_y) do bbox para posicionamento de blocos
    subsequentes (ex.: consumo por pé-direito), ou `None` se não houver bbox.
    """
    # Bounding box global de todos os painéis
    min_x = min_y = float("inf")
    max_y = float("-inf")
    for r in results:
        try:
            mnx, mny, mxx, mxy = r.slab.polygon.bounds
            min_x = min(min_x, mnx)
            min_y = min(min_y, mny)
            max_y = max(max_y, mxy)
        except Exception:
            continue
    if min_x == float("inf"):
        return None

    if calc_result:
        bruto = calc_result.slab_volume_gross_m3
        vigas = calc_result.beam_volume_deducted_m3
        pilares = calc_result.pillar_volume_deducted_m3
        liquido = calc_result.total_volume_m3
    else:
        bruto = sum(r.volume_m3 for r in results if r.volume_m3)
        vigas = 0.0
        pilares = 0.0
        liquido = bruto

    origin_x = min_x
    origin_y = max_y + 1.0  # 1m acima do topo do desenho

    msp.add_text(
        "VOLUME ESCORADO",
        height=0.30,
        dxfattribs={"layer": "VOLUMES", "color": 7, "insert": (origin_x, origin_y + 1.40)},
    )

    lines = [
        f"Bruto:      {bruto:.2f} m³",
        f"(-) Vigas:   {vigas:.2f} m³",
        f"(-) Pilares: {pilares:.2f} m³",
        f"Liquido:    {liquido:.2f} m³",
    ]
    for idx, line in enumerate(lines):
        msp.add_text(
            line,
            height=0.22,
            dxfattribs={
                "layer": "VOLUMES",
                "color": 7,
                "insert": (origin_x, origin_y + 1.00 - idx * 0.32),
            },
        )

    # Bloco de consumo será posicionado abaixo do bbox (min_y).
    return origin_x, min_y


def _write_consumption_block(msp, report_data: "ReportData",
                              origin_x: float, origin_y: float) -> None:
    """Insere bloco `CONSUMO POR PÉ-DIREITO` na layer VOLUMES.

    Layout em colunas com largura fixa (sem grade), abaixo do totalizador
    de volume escorado. Linhas por pé-direito + linha TOTAL ao final.
    """
    if not report_data or not report_data.consumption_rows:
        return

    msp.add_text(
        "CONSUMO POR PÉ-DIREITO",
        height=0.22,
        dxfattribs={"layer": "VOLUMES", "color": 7, "insert": (origin_x, origin_y)},
    )

    header = (
        f"{'Pe-direito':<10}|{'Area':>10}|{'V.Bruto':>12}|"
        f"{'V.Liquido':>13}|{'Escoras':>11}|{'Acessorios':>13}|"
        f"{'Total':>11}|{'Taxa(kg/m3 bruto)':>22}"
    )
    msp.add_text(
        header,
        height=0.18,
        dxfattribs={
            "layer": "VOLUMES", "color": 7,
            "insert": (origin_x, origin_y - 0.40),
        },
    )

    def _row_text(label, area, vbruto, vliq, escoras, acc, total, taxa) -> str:
        return (
            f"{label:<10}|{area:>8.2f} m²|{vbruto:>9.2f} m³|"
            f"{vliq:>10.2f} m³|{escoras:>8.0f} kg|"
            f"{acc:>10.0f} kg|{total:>8.0f} kg|{taxa:>22.2f}"
        )

    y = origin_y - 0.72
    for r in report_data.consumption_rows:
        line = _row_text(
            f"{r.pe_direito_m:.2f} m", r.area_m2, r.volume_bruto_m3,
            r.volume_liquido_m3, r.shores_weight_kg,
            r.accessories_weight_kg, r.total_weight_kg, r.rate_kg_m3_bruto,
        )
        msp.add_text(
            line,
            height=0.18,
            dxfattribs={"layer": "VOLUMES", "color": 7, "insert": (origin_x, y)},
        )
        y -= 0.30

    totals = report_data.consumption_totals or {}
    if totals:
        # Linha separadora textual
        msp.add_text(
            "-" * 110,
            height=0.18,
            dxfattribs={"layer": "VOLUMES", "color": 7, "insert": (origin_x, y)},
        )
        y -= 0.30
        total_line = _row_text(
            "TOTAL",
            totals.get("area_m2", 0.0),
            totals.get("volume_bruto_m3", 0.0),
            totals.get("volume_liquido_m3", 0.0),
            totals.get("shores_kg", 0.0),
            totals.get("accessories_kg", 0.0),
            totals.get("total_kg", 0.0),
            totals.get("rate_kg_m3_bruto", 0.0),
        )
        msp.add_text(
            total_line,
            height=0.18,
            dxfattribs={"layer": "VOLUMES", "color": 7, "insert": (origin_x, y)},
        )


def generate_output_dxf(
    results: List[ShoringResult],
    output_path: str,
    calc_result: Optional[CalculationResult] = None,
    report_data: Optional["ReportData"] = None,
) -> str:
    """
    Gera DXF de saída com geometria original + escoras posicionadas.

    Layers criados:
    - ESTRUTURA: geometria original da laje
    - ESCORAS: círculos representando escoras
    - TEXTO_ESCORAS: código do modelo ao lado de cada escora
    - INFO: informações gerais (título, cargas)
    - VOLUMES: rótulo por painel + bloco totalizador (bruto/vigas/pilares/líquido)

    Args:
        results: lista de `ShoringResult` (um por painel).
        output_path: caminho de saída.
        calc_result: opcional — quando presente, totalizador mostra bruto/deduções.
    """
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Criar layers (idempotente)
    _ensure_layer(doc, "ESTRUTURA", color=7)       # Branco
    _ensure_layer(doc, "ESCORAS", color=1)         # Vermelho
    _ensure_layer(doc, "TEXTO_ESCORAS", color=3)   # Verde
    _ensure_layer(doc, "INFO", color=5)            # Azul
    _ensure_layer(doc, "VOLUMES", color=7)         # Branco (cor definida por entidade)

    for result in results:
        slab = result.slab

        # Desenhar contorno da laje
        if hasattr(slab.polygon, "exterior"):
            coords = list(slab.polygon.exterior.coords)
            msp.add_lwpolyline(
                [(x, y) for x, y in coords],
                close=True,
                dxfattribs={"layer": "ESTRUTURA"},
            )

        # Desenhar escoras
        shore_radius = 0.05  # 5cm de raio visual
        for shore in result.shores:
            # Círculo representando a escora
            msp.add_circle(
                center=(shore.x, shore.y),
                radius=shore_radius,
                dxfattribs={"layer": "ESCORAS"},
            )

            # Texto com modelo da escora
            msp.add_text(
                shore.shore.id,
                height=0.08,
                dxfattribs={
                    "layer": "TEXTO_ESCORAS",
                    "insert": (shore.x + 0.1, shore.y + 0.1),
                },
            )

        # Info da laje
        bb = slab.bounding_box
        info_y = bb.max_y + 0.5
        info_parts = [
            f"Laje: {slab.layer_name}",
            f"Area: {slab.area_m2:.2f}m²",
            f"Esp: {slab.thickness_m*100:.0f}cm",
            f"Carga: {result.total_load_kn:.1f}kN",
        ]
        if result.volume_m3 > 0:
            info_parts.append(f"Volume: {result.volume_m3:.2f}m³")
        msp.add_text(
            " | ".join(info_parts),
            height=0.12,
            dxfattribs={
                "layer": "INFO",
                "insert": (bb.min_x, info_y),
            },
        )
        msp.add_text(
            f"Escoras: {len(result.shores)}x {result.selected_shore.model} | "
            f"Grid: {result.grid_nx}x{result.grid_ny} | "
            f"Esp: {result.spacing_x_m:.2f}x{result.spacing_y_m:.2f}m",
            height=0.10,
            dxfattribs={
                "layer": "INFO",
                "insert": (bb.min_x, info_y + 0.25),
            },
        )

        # === LAYER VOLUMES ===
        # Anotação didática no centróide com categoria + volume.
        category = getattr(result, "category", "laje") or "laje"
        color = CATEGORY_DXF_COLOR.get(category, 7)
        label = getattr(result, "label", "") or f"Laje {slab.layer_name}"
        pe = getattr(result, "pe_direito_m", 0.0) or 0.0
        vol = getattr(result, "volume_m3", 0.0) or (slab.area_m2 * pe)
        _write_volume_label(
            msp=msp,
            polygon=slab.polygon,
            label=label,
            area_m2=slab.area_m2,
            pe_direito_m=pe,
            volume_m3=vol,
            color=color,
        )

    # Bloco totalizador no canto superior
    if results:
        position = _write_totalizer_block(msp, results, calc_result)
        # Bloco de consumo por pé-direito (abaixo do bbox), se houver dados.
        if position is not None and report_data is not None \
                and getattr(report_data, "consumption_rows", None):
            origin_x, min_y = position
            _write_consumption_block(
                msp, report_data, origin_x, min_y - 1.0
            )

    doc.saveas(output_path)
    return output_path
