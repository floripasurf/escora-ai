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

    _generate_output_dxf(input_path, calc, output_dxf)

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

    fieldnames = ["Tipo", "Elemento", "Comprimento (m)", "Secao (cm)", "Qtd Escoras", "Espacamento (m)"]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _generate_output_dxf(input_path: str, calc, output_path: str):
    """Overlay shores onto the original DXF."""
    doc = ezdxf.readfile(input_path)
    msp = doc.modelspace()

    for layer_name, color in [
        ("ESCORAS_VIGA", 1), ("ESCORAS_LAJE", 3),
        ("INFO_ESCORAS", 5),
    ]:
        if layer_name not in doc.layers:
            doc.layers.add(layer_name, color=color)

    # Draw beam shores — crosshair + circle for visibility
    shore_radius = 0.12  # 12cm radius — clear but compact
    cross_size = 0.15    # 15cm crosshair arm length
    for br in calc.beam_results:
        for shore in br.shores:
            cx, cy = shore.x, shore.y
            msp.add_circle(
                center=(cx, cy), radius=shore_radius,
                dxfattribs={"layer": "ESCORAS_VIGA"},
            )
            msp.add_line(
                (cx - cross_size, cy), (cx + cross_size, cy),
                dxfattribs={"layer": "ESCORAS_VIGA"},
            )
            msp.add_line(
                (cx, cy - cross_size), (cx, cy + cross_size),
                dxfattribs={"layer": "ESCORAS_VIGA"},
            )

    # Draw slab shores
    for sr in calc.slab_results:
        for shore in sr.shores:
            cx, cy = shore.x, shore.y
            msp.add_circle(
                center=(cx, cy), radius=shore_radius,
                dxfattribs={"layer": "ESCORAS_LAJE"},
            )
            msp.add_line(
                (cx - cross_size, cy), (cx + cross_size, cy),
                dxfattribs={"layer": "ESCORAS_LAJE"},
            )
            msp.add_line(
                (cx, cy - cross_size), (cx, cy + cross_size),
                dxfattribs={"layer": "ESCORAS_LAJE"},
            )

    # Summary text
    total_beam = sum(br.shore_count for br in calc.beam_results)
    total_slab = sum(len(sr.shores) for sr in calc.slab_results)
    all_pts = [p for br in calc.beam_results for p in br.beam.geometry]
    if all_pts:
        min_x = min(p[0] for p in all_pts)
        max_y = max(p[1] for p in all_pts)
        info = (
            f"ESCORA.AI — {len(calc.beam_results)} vigas ({total_beam} esc.), "
            f"{len(calc.slab_results)} lajes ({total_slab} esc.), total={total_beam + total_slab}"
        )
        msp.add_text(info, height=0.25, dxfattribs={
            "layer": "INFO_ESCORAS", "insert": (min_x, max_y + 1.5),
        })

    doc.saveas(output_path)
