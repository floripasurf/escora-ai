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

    _generate_output_dxf(input_path, calc, output_dxf, scale=result.scale)

    # Build results summary
    beam_results = []
    for br in calc.beam_results:
        b = br.beam
        beam_results.append({
            "name": b.name,
            "length_m": round(b.length_m or 0, 2),
            "width_m": round(b.section_width_m or 0, 2),
            "height_m": round(b.section_height_m, 2) if b.section_height_m else None,
            "shore_count": br.shore_count,
            "spacing_m": round(br.spacing_m, 2),
        })

    slab_results = []
    for sr in calc.slab_results:
        slab_results.append({
            "area_m2": round(sr.area_m2, 1),
            "thickness_m": round(sr.thickness_m, 2),
            "shore_count": len(sr.shores),
            "grid": f"{sr.grid_nx}x{sr.grid_ny}",
        })

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
    _generate_bom_csv(calc, csv_path)

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
        metadata = ReportMetadata(
            project_name=stem,
            date=date.today().strftime("%d/%m/%Y"),
            scale=result.scale,
            dxf_filename=Path(input_path).name,
        )
        report_data = build_report_data(calc, metadata)

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

    return {
        "beam_count": len(calc.beam_results),
        "pillar_count": pillar_count,
        "slab_count": len(calc.slab_results),
        "total_shores": total_beam_shores + total_slab_shores,
        "beams": beam_results,
        "slabs": slab_results,
        "warnings": result.warnings[:20],  # Limit warnings
        "output_dxf_path": output_dxf,
        "dwg_path": dwg_path,
        "csv_path": csv_path,
        "ifc_path": ifc_path,
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
    """Return ({telescopic_id: count}, tower_count) from a CalculationResult.

    Single source of truth for both BOM CSV and report_data accessory rules.
    """
    from src.models.shore import SupportType
    telescopic_counts: dict = {}
    tower_count = 0
    for br in calc.beam_results:
        for s in br.shores:
            if getattr(s, "support_type", None) == SupportType.TOWER:
                tower_count += 1
            else:
                sid = s.shore.id
                telescopic_counts[sid] = telescopic_counts.get(sid, 0) + 1
    for sr in calc.slab_results:
        for s in sr.shores:
            if getattr(s, "support_type", None) == SupportType.TOWER:
                tower_count += 1
            else:
                sid = s.shore.id
                telescopic_counts[sid] = telescopic_counts.get(sid, 0) + 1
    return telescopic_counts, tower_count


def _generate_bom_csv(calc, output_path: str):
    """Generate Bill of Materials CSV from calculation results."""
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
    })

    # Accessories — cruzetas
    try:
        from src.engine.tower_selector import compute_cruzeta_bom, load_tower_catalog
        _, _, accessories = load_tower_catalog()
        telescopic_counts, tower_count = _count_shores_by_id(calc)
        for acc, qty in compute_cruzeta_bom(accessories, telescopic_counts, tower_count):
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

    fieldnames = ["Tipo", "Elemento", "Comprimento (m)", "Secao (cm)", "Qtd Escoras", "Espacamento (m)"]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _generate_output_dxf(input_path: str, calc, output_path: str, scale: float = 1.0):
    """Overlay shores onto the original DXF using Orguel layer naming.

    Symbology (Orguel convention):
    - Telescopic shore — filled hexagon (~0.30 m across) + label on first
      occurrence per cluster.
    - Tower — double square (outer 0.40 m, inner 0.28 m) + 4 corner ticks.
    - VM distribution beam — TWO parallel rails alongside the concrete beam,
      one each side of the web (real Orguel plans never draw a single
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
        # between consecutive telescopic shores — this creates the Orguel-style
        # grid pattern. Orguel places VM50-TRAV every ~0.45m perpendicular.
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

        # Group slab shores into rows by Y coordinate (to draw rails)
        if slab_vm_layer and len(sr.shores) >= 2:
            rows: dict = {}
            for s in sr.shores:
                key = round(s.y / 0.5) * 0.5  # bin by 0.5m
                rows.setdefault(key, []).append(s)
            for key, row_shores in rows.items():
                if len(row_shores) < 2:
                    continue
                row_shores.sort(key=lambda s: s.x)
                x0 = _dx(row_shores[0].x)
                x1 = _dx(row_shores[-1].x)
                y = _dx(key)
                # Two parallel lines (a thin rectangle along the row)
                msp.add_line(
                    (x0, y - SLAB_RAIL_HALF), (x1, y - SLAB_RAIL_HALF),
                    dxfattribs={"layer": slab_vm_layer},
                )
                msp.add_line(
                    (x0, y + SLAB_RAIL_HALF), (x1, y + SLAB_RAIL_HALF),
                    dxfattribs={"layer": slab_vm_layer},
                )

        # Draw VM50 travamento perpendicular to slab rows (vertical connectors)
        # This creates the Orguel-style grid connecting shore rows
        if len(sr.shores) >= 4:
            vm50_slab_layer = "VM50_Laje"
            _ensure_layer(doc, vm50_slab_layer, 6)
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

    doc.saveas(output_path)
