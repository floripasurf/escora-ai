"""Pipeline execution service — runs the shoring calculation and generates output DXF."""

import csv
import logging
from pathlib import Path
from typing import Optional

import ezdxf

from src.pipeline.runner import run_pipeline
from src.models.pipeline_models import ElementType
from api.config import settings

logger = logging.getLogger(__name__)


def process_dxf(input_path: str, job_id: str) -> dict:
    """Run the full pipeline on a DXF file and generate output.

    Returns a dict with results summary and output file path.
    """
    result = run_pipeline(input_path)
    calc = result.calculation

    if calc is None:
        return {"error": "Pipeline falhou — nenhum resultado de calculo"}

    # Generate output DXF
    output_dir = Path(settings.output_dir) / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dxf = str(output_dir / f"{Path(input_path).stem}_escoras.dxf")

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
    csv_path = str(output_dir / f"{Path(input_path).stem}_BOM.csv")
    _generate_bom_csv(calc, csv_path)

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
    }


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
        ("INFO_ESCORAS", 5), ("VIGAS_DET", 6), ("LAJES_DET", 4),
    ]:
        if layer_name not in doc.layers:
            doc.layers.add(layer_name, color=color)

    # Draw beam centerlines
    for br in calc.beam_results:
        b = br.beam
        if len(b.geometry) >= 2:
            p1, p2 = b.geometry[0], b.geometry[1]
            msp.add_line(p1, p2, dxfattribs={"layer": "VIGAS_DET", "lineweight": 50})
            mx = (p1[0] + p2[0]) / 2
            my = (p1[1] + p2[1]) / 2
            name = b.name or "?"
            w = b.section_width_m or 0
            h = b.section_height_m or "?"
            msp.add_text(
                f"{name} {w}x{h}", height=0.15,
                dxfattribs={"layer": "INFO_ESCORAS", "insert": (mx + 0.1, my + 0.1)},
            )

    # Draw beam shores
    shore_radius = 0.08
    for br in calc.beam_results:
        for shore in br.shores:
            msp.add_circle(
                center=(shore.x, shore.y), radius=shore_radius,
                dxfattribs={"layer": "ESCORAS_VIGA"},
            )

    # Draw slab contours and shores
    for sr in calc.slab_results:
        if hasattr(sr.polygon, "exterior"):
            coords = list(sr.polygon.exterior.coords)
            for k in range(len(coords) - 1):
                msp.add_line(coords[k], coords[k + 1], dxfattribs={"layer": "LAJES_DET"})
        for shore in sr.shores:
            msp.add_circle(
                center=(shore.x, shore.y), radius=shore_radius,
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
