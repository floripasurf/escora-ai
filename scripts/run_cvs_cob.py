"""
Cálculo de escoramento para CVS-COB-FOR-006-R00.DXF
Dados extraídos do DXF: lajes, vigas, pilares, nível.

Uso: python scripts/run_cvs_cob.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from shapely.geometry import Polygon

from src.models.slab import Slab
from src.models.shore import PositionedShore
from src.models.project import ShoringResult
    calculate_self_weight, calculate_live_load, calculate_total_load,
)
    calculate_beam_self_weight, calculate_beam_total_linear_load,
    distribute_beam_shores, estimate_beam_shore_height,
)
from src.generator.dxf_writer import generate_output_dxf
from src.generator.bom_generator import write_bom_csv, generate_bom

console = Console()

# ============================================================
# DADOS EXTRAÍDOS DO DXF CVS-COB-FOR-006-R00
# Nível: +1330,40m (cobertura)
# Pé-direito padrão: 2.92m
# ============================================================

PE_DIREITO = 2.92  # metros

# Lajes com áreas reconstruídas por polygonize
SLABS = [
    {"name": "L1",  "thickness_cm": 18, "area_m2": 31.87, "width": 5.69, "height": 5.63},
    {"name": "L2",  "thickness_cm": 15, "area_m2": 29.57, "width": 6.47, "height": 4.57},
    {"name": "L3",  "thickness_cm": 10, "area_m2": 28.86, "width": 6.63, "height": 4.57},
    {"name": "L4",  "thickness_cm": 12, "area_m2": 19.04, "width": 8.01, "height": 2.39},
    {"name": "L5",  "thickness_cm": 12, "area_m2": 11.77, "width": 3.91, "height": 3.77},
    {"name": "L6",  "thickness_cm": 15, "area_m2": 17.24, "width": 6.83, "height": 3.02},
    {"name": "L7",  "thickness_cm": 10, "area_m2": 24.34, "width": 5.47, "height": 4.45},
    {"name": "L8",  "thickness_cm": 10, "area_m2": 28.42, "width": 17.12, "height": 1.66},
    {"name": "L9",  "thickness_cm": 10, "area_m2": 29.52, "width": 6.46, "height": 4.57},
    {"name": "L10", "thickness_cm": 15, "area_m2": 13.76, "width": 3.01, "height": 4.57},
]

# Vigas com comprimentos estimados pelas distâncias entre pilares
BEAMS = [
    # name, width_cm, height_cm, length_m (estimated from pillar distances)
    {"name": "V1a",  "w_cm": 14, "h_cm": 40, "length": 8.95},  # P3→P5→P4
    {"name": "V2a",  "w_cm": 14, "h_cm": 40, "length": 3.90},  # P8→P9
    {"name": "V3a",  "w_cm": 19, "h_cm": 40, "length": 5.00},  # P10→P11
    {"name": "V4a",  "w_cm": 14, "h_cm": 40, "length": 5.90},  # P11→P12
    {"name": "V5a",  "w_cm": 14, "h_cm": 40, "length": 8.40},  # P12→P13
    {"name": "V6a",  "w_cm": 14, "h_cm": 40, "length": 4.10},  # P18→P12
    {"name": "V7a",  "w_cm": 14, "h_cm": 60, "length": 8.10},  # P14→P7
    {"name": "V8a",  "w_cm": 14, "h_cm": 40, "length": 6.30},  # P19→P15
    {"name": "V9a",  "w_cm": 14, "h_cm": 60, "length": 2.20},  # P19→V10a (curta)
    {"name": "V10a", "w_cm": 14, "h_cm": 60, "length": 4.50},  # P24→P19
    {"name": "V11a", "w_cm": 14, "h_cm": 40, "length": 4.20},  # P25→P15 (horizontal)
    {"name": "V12a", "w_cm": 14, "h_cm": 40, "length": 4.70},  # P10→P16
    {"name": "V13a", "w_cm": 14, "h_cm": 40, "length": 7.00},  # P20→P16
    {"name": "V14a", "w_cm": 14, "h_cm": 40, "length": 5.00},  # P10→P11 (paralela)
    {"name": "V15a", "w_cm": 14, "h_cm": 40, "length": 6.60},  # P21→P20
    {"name": "V16a", "w_cm": 14, "h_cm": 40, "length": 5.90},  # P12→P8
    {"name": "V17a", "w_cm": 14, "h_cm": 40, "length": 3.50},  # P8→P9
    {"name": "V18a", "w_cm": 14, "h_cm": 40, "length": 7.10},  # P22→P17
    {"name": "V19a", "w_cm": 14, "h_cm": 40, "length": 8.10},  # P23→P13
]


def main():
    catalog = load_catalog()

    console.print()
    console.print(Panel.fit(
        "[bold]ESCORA.AI — CVS-COB-FOR-006-R00[/bold]\n"
        "Fôrma da Cobertura — Nível +1330,40m",
        border_style="red",
    ))
    console.print()

    all_slab_results = []
    total_slab_shores = 0
    total_beam_shores = 0

    # ============================================================
    # LAJES
    # ============================================================
    console.print(Panel("[bold]LAJES[/bold]", border_style="cyan"))

    slab_table = Table(title="Escoramento de Lajes")
    slab_table.add_column("Laje", style="cyan")
    slab_table.add_column("Esp.", style="white")
    slab_table.add_column("Área (m²)", style="white")
    slab_table.add_column("Carga (kN)", style="yellow")
    slab_table.add_column("Escoras", style="green")
    slab_table.add_column("Grid", style="white")
    slab_table.add_column("Espaç. (m)", style="white")
    slab_table.add_column("Modelo", style="white")
    slab_table.add_column("Utiliz.", style="white")

    for s in SLABS:
        thickness_m = s["thickness_cm"] / 100.0
        polygon = Polygon([
            (0, 0), (s["width"], 0), (s["width"], s["height"]), (0, s["height"]),
        ])
        slab = Slab.from_polygon(polygon, f"{s['name']}_h{s['thickness_cm']}", thickness_m)

        shore_height = PE_DIREITO - thickness_m
        total_load = calculate_total_load(slab)

        estimated = total_load / max(1, int(slab.area_m2 / 2.25))
        shore = select_shore(catalog, shore_height, estimated)
        if shore is None:
            shore = select_shore(catalog, shore_height, 5.0)

        shores, nx, ny, sx, sy = distribute_shores(slab, shore, total_load)
        load_per_shore = total_load / len(shores)

        if load_per_shore > shore.load_capacity_kn:
            shore = select_shore(catalog, shore_height, load_per_shore)
            shores, nx, ny, sx, sy = distribute_shores(slab, shore, total_load)
            load_per_shore = total_load / len(shores)

        utilization = load_per_shore / shore.load_capacity_kn
        total_slab_shores += len(shores)

        slab_table.add_row(
            s["name"],
            f"{s['thickness_cm']}cm",
            f"{slab.area_m2:.1f}",
            f"{total_load:.1f}",
            str(len(shores)),
            f"{nx}×{ny}",
            f"{sx:.2f}×{sy:.2f}",
            shore.model.split(" ")[1],
            f"{'[green]' if utilization <= 0.8 else '[yellow]'}{utilization:.0%}",
        )

        all_slab_results.append(ShoringResult(
            slab=slab,
            total_load_kn=round(total_load, 2),
            self_weight_kn=round(calculate_self_weight(slab), 2),
            live_load_kn=round(calculate_live_load(slab), 2),
            selected_shore=shore,
            shores=shores,
            grid_nx=nx, grid_ny=ny,
            spacing_x_m=round(sx, 4), spacing_y_m=round(sy, 4),
            load_per_shore_kn=round(load_per_shore, 2),
        ))

    console.print(slab_table)
    console.print()

    # ============================================================
    # VIGAS
    # ============================================================
    console.print(Panel("[bold]VIGAS[/bold]", border_style="red"))

    beam_table = Table(title="Escoramento de Vigas")
    beam_table.add_column("Viga", style="cyan")
    beam_table.add_column("Seção", style="white")
    beam_table.add_column("Compr.", style="white")
    beam_table.add_column("Carga (kN/m)", style="yellow")
    beam_table.add_column("Escoras", style="green")
    beam_table.add_column("Espaç.", style="white")
    beam_table.add_column("Modelo", style="white")
    beam_table.add_column("Utiliz.", style="white")

    all_beam_shores = []

    for b in BEAMS:
        w_m = b["w_cm"] / 100.0
        h_m = b["h_cm"] / 100.0
        length = b["length"]

        shore_height = estimate_beam_shore_height(PE_DIREITO, h_m)
        q_linear = calculate_beam_total_linear_load(w_m, h_m)

        # Escoras sob vigas: espaçamento máximo 1.0m (mais apertado que lajes)
        max_spacing_beam = 0.80 if b["h_cm"] >= 60 else 1.00

        estimated_load = q_linear * max_spacing_beam
        shore = select_shore(catalog, shore_height, estimated_load)
        if shore is None:
            shore = select_shore(catalog, shore_height, 5.0)

        shores, n, spacing = distribute_beam_shores(
            length, w_m, h_m, shore, q_linear,
            max_spacing=max_spacing_beam,
        )
        total_beam_shores += len(shores)
        all_beam_shores.extend(shores)

        load_per = q_linear * spacing
        utilization = load_per / shore.load_capacity_kn

        beam_table.add_row(
            b["name"],
            f"{b['w_cm']}/{b['h_cm']}",
            f"{length:.1f}m",
            f"{q_linear:.2f}",
            str(len(shores)),
            f"{spacing:.2f}m",
            shore.model.split(" ")[1],
            f"{'[green]' if utilization <= 0.8 else '[yellow]'}{utilization:.0%}",
        )

    console.print(beam_table)
    console.print()

    # ============================================================
    # RESUMO GERAL
    # ============================================================
    total = total_slab_shores + total_beam_shores
    total_weight_slabs = sum(
        len(r.shores) * r.selected_shore.weight_kg for r in all_slab_results
    )
    total_weight_beams = sum(s.shore.weight_kg for s in all_beam_shores)

    summary = Table(title="Resumo Geral", show_header=False)
    summary.add_column("", style="cyan")
    summary.add_column("", style="white")
    summary.add_row("Pé-direito", f"{PE_DIREITO:.2f} m")
    summary.add_row("Nível", "+1330,40 m")
    summary.add_row("", "")
    summary.add_row("Escoras em lajes", f"{total_slab_shores}")
    summary.add_row("Escoras em vigas", f"{total_beam_shores}")
    summary.add_row("[bold]Total de escoras", f"[bold]{total}")
    summary.add_row("", "")
    summary.add_row("Peso total (lajes)", f"{total_weight_slabs:.0f} kg")
    summary.add_row("Peso total (vigas)", f"{total_weight_beams:.0f} kg")
    summary.add_row("[bold]Peso total", f"[bold]{total_weight_slabs + total_weight_beams:.0f} kg")
    console.print(summary)
    console.print()

    # Gerar outputs
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    generate_output_dxf(all_slab_results, str(output_dir / "CVS-COB-lajes-escoras.dxf"))
    console.print(f"[green]DXF lajes:[/green] output/CVS-COB-lajes-escoras.dxf")

    write_bom_csv(all_slab_results, str(output_dir / "CVS-COB-bom-completo.csv"))
    console.print(f"[green]BOM:[/green] output/CVS-COB-bom-completo.csv")
    console.print()


if __name__ == "__main__":
    main()
