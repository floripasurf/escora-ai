"""Pipeline execution service — runs the shoring calculation and generates output DXF."""

import csv
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import ezdxf

from src.pipeline.runner import run_pipeline
from src.models.pipeline_models import ElementType
from src.output.report_data import build_report_data, ReportMetadata
from src.output.pdf_generator import generate_pdf, generate_memoria_calculo, generate_orcamento
from src.output.ifc_generator import generate_ifc
from src.output.csv_generator import write_consumption_csv
from src.output.mermaid_generator import generate_all_diagrams
from api.config import settings

logger = logging.getLogger(__name__)


def process_dxf(
    input_path: str,
    job_id: str,
    mode: str = "price",
    inventory_name: Optional[str] = None,
    output_suffix: str = "",
    branch_id: Optional[str] = None,
) -> dict:
    """Run the full pipeline on a DXF file and generate output.

    output_suffix is appended to all output filenames so a regenerated
    bundle (e.g. '_validated') does not overwrite the originals.

    branch_id scopes the learning store so each locadora branch keeps its
    own accumulated knowledge.
    """
    result = run_pipeline(
        input_path,
        mode=mode,
        inventory_name=inventory_name,
        branch_id=branch_id,
    )
    calc = result.calculation

    if calc is None:
        return {"error": "Pipeline falhou — nenhum resultado de calculo"}

    # Generate output DXF
    output_dir = Path(settings.output_dir) / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    stem_base = Path(input_path).stem
    output_dxf = str(output_dir / f"{stem_base}_escoras{output_suffix}.dxf")

    # Build report data upfront — DXF, CSVs e PDFs compartilham.
    metadata = ReportMetadata(
        project_name=stem_base,
        date=date.today().strftime("%d/%m/%Y"),
        scale=result.scale,
        dxf_filename=Path(input_path).name,
    )
    report_data = build_report_data(calc, metadata)

    _generate_output_dxf(
        input_path, calc, output_dxf, scale=result.scale,
        report_data=report_data,
    )

    total_beam_shores = sum(br.shore_count for br in calc.beam_results)
    total_slab_shores = sum(len(sr.shores) for sr in calc.slab_results)

    # Count pillars from elements
    pillar_count = 0
    for level in result.levels:
        pillar_count += sum(1 for e in level.elements if e.element_type == ElementType.PILLAR)

    # Generate DWG from the DXF (requires ODA File Converter)
    dwg_path: Optional[str] = None
    try:
        from ezdxf.addons import odafc
        if odafc.is_installed():
            dwg_candidate = str(output_dir / f"{stem_base}_escoras{output_suffix}.dwg")
            odafc.export_dwg(ezdxf.readfile(output_dxf), dwg_candidate)
            dwg_path = dwg_candidate
            logger.info(f"Generated DWG: {dwg_path}")
        else:
            logger.debug("ODA File Converter not installed — DWG export skipped")
    except Exception as e:
        logger.debug(f"DWG conversion skipped: {e}")

    # Generate BOM CSV
    csv_path = str(output_dir / f"{stem_base}_BOM{output_suffix}.csv")
    _generate_bom_csv(calc, csv_path, report_data=report_data)

    # Generate consumption CSV (consumo por pé-direito — orçamento interno)
    consumption_csv_path: Optional[str] = None
    try:
        consumption_csv_candidate = str(
            output_dir / f"{stem_base}_consumo{output_suffix}.csv"
        )
        write_consumption_csv(report_data, consumption_csv_candidate)
        consumption_csv_path = consumption_csv_candidate
        logger.info(f"Generated consumption CSV: {consumption_csv_path}")
    except Exception as e:
        logger.warning(f"Consumption CSV generation failed (non-fatal): {e}")

    # Resumo compacto do consumo ((pé-direito, categoria) × taxa kg/m³ bruto)
    # — usado pela UI pra exibir validação rápida sem parsear o CSV.
    consumption_summary = [
        {
            "pe_direito_m": round(r.pe_direito_m, 2),
            "rate_kg_m3_bruto": round(r.rate_kg_m3_bruto, 2),
            "rate_kg_m3_liquido": round(r.rate_kg_m3_liquido, 2),
            "area_m2": round(r.area_m2, 2),
            "volume_bruto_m3": round(r.volume_bruto_m3, 2),
            "total_kg": round(r.total_weight_kg, 2),
            "category_label": r.category_label,
        }
        for r in (report_data.consumption_rows or [])
    ]

    # Generate IFC (BIM export)
    ifc_path: Optional[str] = None
    try:
        ifc_candidate = str(output_dir / f"{stem_base}{output_suffix}.ifc")
        generate_ifc(result, ifc_candidate, project_name=Path(input_path).stem)
        ifc_path = ifc_candidate
        logger.info(f"Generated IFC: {ifc_path}")
    except Exception as e:
        logger.warning(f"IFC generation failed (non-fatal): {e}")

    # Generate PDF reports (memória de cálculo + orçamento)
    stem = stem_base
    pdf_paths = {}
    try:
        pdf_report = str(output_dir / f"{stem}_relatorio{output_suffix}.pdf")
        generate_pdf(report_data, pdf_report)
        pdf_paths["relatorio"] = pdf_report

        pdf_memoria = str(output_dir / f"{stem}_memoria_calculo{output_suffix}.pdf")
        generate_memoria_calculo(report_data, pdf_memoria)
        pdf_paths["memoria_calculo"] = pdf_memoria

        pdf_orcamento = str(output_dir / f"{stem}_orcamento{output_suffix}.pdf")
        generate_orcamento(report_data, pdf_orcamento)
        pdf_paths["orcamento"] = pdf_orcamento

        logger.info(f"Generated PDFs: {list(pdf_paths.keys())}")
    except Exception as e:
        logger.warning(f"PDF generation failed (non-fatal): {e}")

    # Generate Mermaid.js diagrams (decision flow + project summary + spacing)
    mermaid_diagrams = {}
    try:
        mermaid_diagrams = generate_all_diagrams(calc)
        logger.info(f"Generated {len(mermaid_diagrams)} Mermaid diagrams")
    except Exception as e:
        logger.warning(f"Mermaid diagram generation failed (non-fatal): {e}")

    return {
        "beam_count": len(calc.beam_results),
        "pillar_count": pillar_count,
        "slab_count": len(calc.slab_results),
        "total_shores": total_beam_shores + total_slab_shores,
        "support_breakdown": _support_breakdown(calc),
        "warnings": result.warnings[:60],  # Limit warnings (diagnostics first)
        "output_dxf_path": output_dxf,
        "dwg_path": dwg_path,
        "csv_path": csv_path,
        "consumption_csv_path": consumption_csv_path,
        "consumption_summary": consumption_summary,
        "ifc_path": ifc_path,
        "mermaid_diagrams": mermaid_diagrams,
        **pdf_paths,
    }


def regenerate_from_revision(
    original_input_path: str,
    revised_input_path: str,
    job_id: str,
    branch_id: Optional[str] = None,
) -> dict:
    """Re-run the pipeline on the revised DXF and write *_validated.* outputs.

    Reuses the entire process_dxf path with output_suffix='_validated' so the
    original outputs are preserved for audit/comparison.
    """
    return process_dxf(
        input_path=revised_input_path,
        job_id=job_id,
        output_suffix="_validated",
        branch_id=branch_id,
    )


def _count_shores_by_id(calc):
    """Return (beam_telescopic, slab_telescopic, tower_count) from CalculationResult.

    Split between beams and slabs is required because cruzetas follow
    different rules per locadora Q5:
    - Lajes: 0.25 ratio per telescopic shore
    - Vigas: ceil(length / 0.80 m) — driven by beam geometry, not shore count
    """
    from src.models.shore import SupportType
    beam_telescopic: dict = {}
    slab_telescopic: dict = {}
    tower_count = 0
    for br in calc.beam_results:
        for s in br.shores:
            if getattr(s, "support_type", None) == SupportType.TOWER:
                tower_count += 1
            else:
                sid = s.shore.id
                beam_telescopic[sid] = beam_telescopic.get(sid, 0) + 1
    for sr in calc.slab_results:
        for s in sr.shores:
            if getattr(s, "support_type", None) == SupportType.TOWER:
                tower_count += 1
            else:
                sid = s.shore.id
                slab_telescopic[sid] = slab_telescopic.get(sid, 0) + 1
    return beam_telescopic, slab_telescopic, tower_count


def _support_breakdown(calc):
    """Return support counts by element role and physical support type."""
    from src.models.shore import SupportType

    counts = {
        "total": 0,
        "beam": 0,
        "slab": 0,
        "tower": 0,
        "telescopic": 0,
    }

    def add(positioned, role: str) -> None:
        counts["total"] += 1
        counts[role] += 1
        shore_id = getattr(positioned.shore, "id", "")
        is_tower = (
            getattr(positioned, "support_type", None) == SupportType.TOWER
            or shore_id.startswith("TWR-")
        )
        counts["tower" if is_tower else "telescopic"] += 1

    for br in calc.beam_results:
        for positioned in br.shores:
            add(positioned, "beam")
    for sr in calc.slab_results:
        for positioned in sr.shores:
            add(positioned, "slab")
    return counts


def _generate_bom_csv(calc, output_path: str, report_data=None):
    """Generate Bill of Materials CSV from calculation results.

    When `report_data` is provided, vigas vazadas (distribution beams) BOM
    rows são incluídas como acessórios — mantendo paridade com a aba BOM
    do Excel/PDF.
    """
    rows = []

    # Beam shores
    for br in calc.beam_results:
        b = br.beam
        rows.append({
            "Tipo": "Viga",
            "Elemento": b.name or "—",
            "Comprimento (m)": round(b.length_m or 0, 2),
            "Secao (cm)": f"{round((b.section_width_m or 0)*100)}x{round((b.section_height_m or 0)*100)}" if b.section_height_m else "—",
            "Qtd Escoras": br.shore_count,
            "Espacamento (m)": round(br.spacing_m, 2),
            "Regra": br.decision_rule or "—",
        })

    # Slab shores
    for i, sr in enumerate(calc.slab_results):
        rows.append({
            "Tipo": "Laje",
            "Elemento": f"Laje {i+1}",
            "Comprimento (m)": round(sr.area_m2, 1),
            "Secao (cm)": f"e={round(sr.thickness_m*100)}cm",
            "Qtd Escoras": len(sr.shores),
            "Espacamento (m)": f"{round(sr.spacing_x_m, 2)}x{round(sr.spacing_y_m, 2)}",
            "Regra": sr.decision_rule or "—",
        })

    # Summary row
    total_beam = sum(br.shore_count for br in calc.beam_results)
    total_slab = sum(len(sr.shores) for sr in calc.slab_results)
    rows.append({
        "Tipo": "TOTAL",
        "Elemento": "",
        "Comprimento (m)": "",
        "Secao (cm)": "",
        "Qtd Escoras": total_beam + total_slab,
        "Espacamento (m)": "",
        "Regra": "",
    })

    # Accessories — cruzetas
    try:
            compute_cruzeta_bom,
            count_cruzetas_laje,
            count_cruzetas_viga,
            load_tower_catalog,
        )
        _, _, accessories = load_tower_catalog()
        _, slab_telescopic, tower_count = _count_shores_by_id(calc)
        beam_cruzetas = count_cruzetas_viga(calc.beam_results)
        slab_cruzetas = count_cruzetas_laje(slab_telescopic)
        for acc, qty in compute_cruzeta_bom(
            accessories, beam_cruzetas, slab_cruzetas, tower_count,
        ):
            rows.append({
                "Tipo": "Acessório",
                "Elemento": acc.model,
                "Comprimento (m)": "",
                "Secao (cm)": "",
                "Qtd Escoras": qty,
                "Espacamento (m)": "",
            })
    except Exception as exc:
        logger.warning(f"Cruzeta BOM rows skipped: {exc}")

    # Accessories — vigas vazadas (distribution beams VD-*) já agregadas
    # em report_data.bom_rows; reusar a contagem evita duplicar lógica.
    if report_data is not None:
        for r in report_data.bom_rows:
            if r.id.startswith("VD-"):
                rows.append({
                    "Tipo": "Acessório",
                    "Elemento": r.model,
                    "Comprimento (m)": "",
                    "Secao (cm)": "",
                    "Qtd Escoras": r.quantity,
                    "Espacamento (m)": "",
                    "Regra": "",
                })

    fieldnames = ["Tipo", "Elemento", "Comprimento (m)", "Secao (cm)", "Qtd Escoras", "Espacamento (m)", "Regra"]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _generate_output_dxf(
    input_path: str,
    calc,
    output_path: str,
    scale: float = 1.0,
    report_data=None,
):
    """Overlay shores onto the original DXF using Supplier layer naming.

    Symbology (Supplier convention):
    - Telescopic shore — filled hexagon (~0.30 m across) + label on first
      occurrence per cluster.
    - Tower — double square (outer 0.40 m, inner 0.28 m) + 4 corner ticks.
    - VM distribution beam — TWO parallel rails alongside the concrete beam,
      one each side of the web (real Supplier plans never draw a single
      centerline). Towers under those rails are nudged perpendicular to the
      beam axis so they sit on the rails, not on the concrete centerline.
    - Slab VM rails — each row gets a thin rectangle (paired lines).

    All internal coordinates (shore positions, beam geometry) are in meters.
    We convert back to DXF units using inv_scale = 1/scale so entities overlay
    correctly on the original drawing.
    """
    import math
    from src.output.dxf_generator import _ensure_layer, _shore_layer_name
    from src.models.shore import SupportType

    doc = ezdxf.readfile(input_path)
    # Upgrade old DXF versions so LWPOLYLINE / HATCH are supported
    if doc.dxfversion < "AC1015":  # < R2000
        doc.dxfversion = "AC1015"
    msp = doc.modelspace()

    _ensure_layer(doc, "INFO_ESCORAS", 5)

    inv_scale = 1.0 / scale if scale > 0 else 1.0
    SHORE_HEX_RADIUS = 0.15 * inv_scale
    SHORE_LABEL_HEIGHT = 0.20 * inv_scale
    SHORE_LABEL_OFFSET = 0.18 * inv_scale
    TOWER_OUTER = 0.20 * inv_scale
    TOWER_INNER = 0.14 * inv_scale
    TOWER_TICK = 0.08 * inv_scale
    SLAB_RAIL_HALF = 0.04 * inv_scale

    def _dx(v):
        """Convert a meters-coordinate to DXF units."""
        return v * inv_scale

    def _hex_points(cx, cy, r):
        return [
            (cx + r * math.cos(math.radians(60 * i)),
             cy + r * math.sin(math.radians(60 * i)))
            for i in range(6)
        ]

    def _draw_telescopic(cx, cy, layer, label: str = ""):
        pts = _hex_points(cx, cy, SHORE_HEX_RADIUS)
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})
        try:
            hatch = msp.add_hatch(dxfattribs={"layer": layer})
            hatch.paths.add_polyline_path(pts + [pts[0]], is_closed=True)
        except Exception:
            pass
        if label:
            msp.add_text(
                label,
                height=SHORE_LABEL_HEIGHT,
                dxfattribs={"layer": "INFO_ESCORAS"},
            ).set_placement((cx + SHORE_HEX_RADIUS + SHORE_LABEL_OFFSET, cy))

    def _draw_tower(cx, cy, layer):
        outer = TOWER_OUTER
        inner = TOWER_INNER
        tick = TOWER_TICK
        msp.add_lwpolyline(
            [(cx - outer, cy - outer), (cx + outer, cy - outer),
             (cx + outer, cy + outer), (cx - outer, cy + outer)],
            close=True, dxfattribs={"layer": layer},
        )
        msp.add_lwpolyline(
            [(cx - inner, cy - inner), (cx + inner, cy - inner),
             (cx + inner, cy + inner), (cx - inner, cy + inner)],
            close=True, dxfattribs={"layer": layer},
        )
        for ox, oy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
            x0, y0 = cx + ox * outer, cy + oy * outer
            x1, y1 = x0 + ox * tick, y0 + oy * tick
            msp.add_line((x0, y0), (x1, y1), dxfattribs={"layer": layer})

    def _vm_layer_for(dist_beam, target: str) -> str:
        """Map a DistributionBeamEntry to its VM*_{Viga|Laje} layer."""
        if dist_beam is None:
            return f"VM80_{target}"
        token = next(
            (t for t in dist_beam.id.split("-") if t.startswith("VM")),
            "VM80",
        )
        return f"{token}_{target}"

    # ----- Beam loop with VM rails + nudged tower markers ---------------
    seen_models: set = set()
    for br in calc.beam_results:
        beam = br.beam
        if not beam.geometry or len(beam.geometry) < 2:
            # Fallback: just place markers raw
            for shore in br.shores:
                layer = _shore_layer_name(shore, "Viga")
                _ensure_layer(doc, layer)
                sx, sy = _dx(shore.x), _dx(shore.y)
                if getattr(shore, "support_type", None) == SupportType.TOWER:
                    _draw_tower(sx, sy, layer)
                else:
                    label = ""
                    if shore.shore.id not in seen_models:
                        seen_models.add(shore.shore.id)
                        label = shore.shore.id
                    _draw_telescopic(sx, sy, layer, label)
            continue

        ax, ay = _dx(beam.geometry[0][0]), _dx(beam.geometry[0][1])
        bx, by = _dx(beam.geometry[1][0]), _dx(beam.geometry[1][1])
        length = math.hypot(bx - ax, by - ay) or 1.0
        ux, uy = (bx - ax) / length, (by - ay) / length
        nx, ny = -uy, ux
        half_w = (beam.section_width_m or 0.14) / 2.0
        clearance = 0.05
        offset = (half_w + clearance) * inv_scale

        tower_shores = [
            s for s in br.shores
            if getattr(s, "support_type", None) == SupportType.TOWER
        ]
        telescopic_shores = [
            s for s in br.shores
            if getattr(s, "support_type", None) != SupportType.TOWER
        ]

        # Draw two VM rails when this beam is shored by towers
        if len(tower_shores) >= 2:
            dist_beam = getattr(tower_shores[0], "distribution_beam", None)
            vm_layer = _vm_layer_for(dist_beam, "Viga")
            _ensure_layer(doc, vm_layer)
            p_start = (ax + nx * offset, ay + ny * offset)
            p_end = (bx + nx * offset, by + ny * offset)
            q_start = (ax - nx * offset, ay - ny * offset)
            q_end = (bx - nx * offset, by - ny * offset)
            msp.add_line(p_start, p_end, dxfattribs={"layer": vm_layer})
            msp.add_line(q_start, q_end, dxfattribs={"layer": vm_layer})

        # Place tower markers shifted onto the rails (alternating sides)
        for idx, shore in enumerate(tower_shores):
            layer = _shore_layer_name(shore, "Viga")
            _ensure_layer(doc, layer)
            side = 1 if (idx % 2 == 0) else -1
            cx = _dx(shore.x) + nx * offset * side
            cy = _dx(shore.y) + ny * offset * side
            _draw_tower(cx, cy, layer)

        # Draw VM50 travamento (lateral bracing) perpendicular to beam axis
        # between consecutive telescopic shores — this creates the Supplier-style
        # grid pattern. Supplier places VM50-TRAV every ~0.45m perpendicular.
        if len(telescopic_shores) >= 2:
            vm50_layer = "VM50_Viga"
            _ensure_layer(doc, vm50_layer, 6)
            sorted_tel = sorted(telescopic_shores, key=lambda s: _dx(s.x) * ux + _dx(s.y) * uy)
            for si in range(len(sorted_tel) - 1):
                s1, s2 = sorted_tel[si], sorted_tel[si + 1]
                # Short perpendicular VM50 lines at shore positions
                trav_half = 0.20 * inv_scale
                for s in (s1, s2):
                    sx, sy = _dx(s.x), _dx(s.y)
                    tx0 = sx - nx * trav_half
                    ty0 = sy - ny * trav_half
                    tx1 = sx + nx * trav_half
                    ty1 = sy + ny * trav_half
                    msp.add_line((tx0, ty0), (tx1, ty1),
                                 dxfattribs={"layer": vm50_layer})

        # Place telescopic shore markers as-is (no VM rails)
        for shore in telescopic_shores:
            layer = _shore_layer_name(shore, "Viga")
            _ensure_layer(doc, layer)
            label = ""
            if shore.shore.id not in seen_models:
                seen_models.add(shore.shore.id)
                label = shore.shore.id
            _draw_telescopic(_dx(shore.x), _dx(shore.y), layer, label)

    # ----- Slab loop ----------------------------------------------------
    for sr in calc.slab_results:
        # Detect VM family for slab rails (use first tower shore's dist_beam)
        slab_tower_shores = [
            s for s in sr.shores
            if getattr(s, "support_type", None) == SupportType.TOWER
        ]
        slab_vm_layer = None
        if slab_tower_shores:
            dist_beam = getattr(slab_tower_shores[0], "distribution_beam", None)
            slab_vm_layer = _vm_layer_for(dist_beam, "Laje")
            _ensure_layer(doc, slab_vm_layer)

        # Group slab TOWER shores into rows by Y; rails conectam apenas
        # torres consecutivas e saltam pilares (exclusion zones). A viga
        # de distribuição (VM) física só existe de torre a torre — nunca
        # sobre o pilar —, então o desenho deve refletir isso.
        if slab_vm_layer and len(slab_tower_shores) >= 2:
            rows: dict = {}
            for s in slab_tower_shores:
                key = round(s.y / 0.5) * 0.5  # bin by 0.5m
                rows.setdefault(key, []).append(s)

            def _pair_crosses_pillar(x0, x1, y):
                for ex in sr.exclusions or []:
                    if y < ex.min_y or y > ex.max_y:
                        continue
                    lo, hi = min(x0, x1), max(x0, x1)
                    if hi >= ex.min_x and lo <= ex.max_x:
                        return True
                return False

            for key, row_shores in rows.items():
                if len(row_shores) < 2:
                    continue
                row_shores.sort(key=lambda s: s.x)
                y = _dx(key)
                # Segment by consecutive tower pairs. Skip the segment if
                # it would cross a pillar exclusion or span a gap > 1.8×
                # the average spacing (indicative of a pillar between).
                avg_gap = (row_shores[-1].x - row_shores[0].x) / max(
                    len(row_shores) - 1, 1)
                max_gap = max(avg_gap * 1.8, 2.5)
                for i in range(len(row_shores) - 1):
                    a, b = row_shores[i], row_shores[i + 1]
                    if abs(b.x - a.x) > max_gap:
                        continue
                    if _pair_crosses_pillar(a.x, b.x, a.y):
                        continue
                    xa, xb = _dx(a.x), _dx(b.x)
                    msp.add_line(
                        (xa, y - SLAB_RAIL_HALF), (xb, y - SLAB_RAIL_HALF),
                        dxfattribs={"layer": slab_vm_layer},
                    )
                    msp.add_line(
                        (xa, y + SLAB_RAIL_HALF), (xb, y + SLAB_RAIL_HALF),
                        dxfattribs={"layer": slab_vm_layer},
                    )

        # Draw VM50 travamento perpendicular to slab rows (vertical connectors)
        # This creates the Supplier-style grid connecting shore rows. Conectores
        # que cruzariam a exclusão de pilar são omitidos.
        if len(sr.shores) >= 4:
            vm50_slab_layer = "VM50_Laje"
            _ensure_layer(doc, vm50_slab_layer, 6)

            def _col_crosses_pillar(x, y0, y1):
                for ex in sr.exclusions or []:
                    if x < ex.min_x or x > ex.max_x:
                        continue
                    lo, hi = min(y0, y1), max(y0, y1)
                    if hi >= ex.min_y and lo <= ex.max_y:
                        return True
                return False

            # Group by X column (vertical travamento connecting horizontal rows)
            cols: dict = {}
            for s in sr.shores:
                ckey = round(s.x / 0.5) * 0.5
                cols.setdefault(ckey, []).append(s)
            for ckey, col_shores in cols.items():
                if len(col_shores) < 2:
                    continue
                col_shores.sort(key=lambda s: s.y)
                for ci in range(len(col_shores) - 1):
                    s1, s2 = col_shores[ci], col_shores[ci + 1]
                    if _col_crosses_pillar(s1.x, s1.y, s2.y):
                        continue
                    msp.add_line(
                        (_dx(s1.x), _dx(s1.y)), (_dx(s2.x), _dx(s2.y)),
                        dxfattribs={"layer": vm50_slab_layer},
                    )

        for shore in sr.shores:
            layer = _shore_layer_name(shore, "Laje")
            _ensure_layer(doc, layer)
            sx, sy = _dx(shore.x), _dx(shore.y)
            if getattr(shore, "support_type", None) == SupportType.TOWER:
                _draw_tower(sx, sy, layer)
            else:
                label = ""
                if shore.shore.id not in seen_models:
                    seen_models.add(shore.shore.id)
                    label = shore.shore.id
                _draw_telescopic(sx, sy, layer, label)

    # ----- Summary text + small legend ----------------------------------
    total_beam = sum(br.shore_count for br in calc.beam_results)
    total_slab = sum(len(sr.shores) for sr in calc.slab_results)
    all_pts = [p for br in calc.beam_results for p in br.beam.geometry]
    if all_pts:
        min_x = _dx(min(p[0] for p in all_pts))
        max_y = _dx(max(p[1] for p in all_pts))
        info = (
            f"ESCORA.AI — {len(calc.beam_results)} vigas ({total_beam} esc.), "
            f"{len(calc.slab_results)} lajes ({total_slab} esc.), total={total_beam + total_slab}"
        )
        msp.add_text(info, height=0.25, dxfattribs={
            "layer": "INFO_ESCORAS", "insert": (min_x, max_y + 1.5),
        })

        # Legend in top-left corner: hexagon = escora, double square = torre
        lx = min_x
        ly = max_y + 0.8
        _draw_telescopic(lx, ly, "INFO_ESCORAS", "")
        msp.add_text(
            "Escora telescópica",
            height=SHORE_LABEL_HEIGHT * 0.8,
            dxfattribs={"layer": "INFO_ESCORAS"},
        ).set_placement((lx + 0.4, ly - 0.05))
        _draw_tower(lx + 3.5, ly, "INFO_ESCORAS")
        msp.add_text(
            "Torre de escoramento",
            height=SHORE_LABEL_HEIGHT * 0.8,
            dxfattribs={"layer": "INFO_ESCORAS"},
        ).set_placement((lx + 3.9, ly - 0.05))

    # Bloco CONSUMO POR PÉ-DIREITO — orçamento interno na layer VOLUMES.
    if report_data is not None and getattr(report_data, "consumption_rows", None):
        try:
            from src.generator.dxf_writer import _write_consumption_block
            _ensure_layer(doc, "VOLUMES", 7)
            # Bbox de TODAS as escoras (vigas + lajes) para posicionamento.
            xs: list = []
            ys: list = []
            for br in calc.beam_results:
                for s in br.shores:
                    xs.append(_dx(s.x))
                    ys.append(_dx(s.y))
            for sr in calc.slab_results:
                for s in sr.shores:
                    xs.append(_dx(s.x))
                    ys.append(_dx(s.y))
            if xs and ys:
                origin_x = min(xs)
                origin_y = min(ys) - 1.0 * inv_scale
                _write_consumption_block(msp, report_data, origin_x, origin_y)
        except Exception as e:
            logger.debug(f"DXF consumption block skipped: {e}")

    doc.saveas(output_path)
