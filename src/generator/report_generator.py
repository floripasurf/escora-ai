"""Geração de relatório formatado no terminal via Rich."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from typing import List
from src.models.project import ShoringResult


def print_report(results: List[ShoringResult], console: Console | None = None) -> None:
    """Imprime relatório completo no terminal."""
    if console is None:
        console = Console()

    console.print()
    console.print(
        Panel.fit(
            "[bold]ESCORA.AI[/bold] — Relatório de Escoramento",
            border_style="red",
        )
    )
    console.print()

    for i, result in enumerate(results, 1):
        slab = result.slab

        # Dados da laje
        slab_table = Table(title=f"Laje #{i}: {slab.layer_name}", show_header=False)
        slab_table.add_column("Parâmetro", style="cyan")
        slab_table.add_column("Valor", style="white")

        bb = slab.bounding_box
        slab_table.add_row("Dimensões", f"{bb.width:.2f} x {bb.height:.2f} m")
        slab_table.add_row("Área", f"{slab.area_m2:.2f} m²")
        slab_table.add_row("Perímetro", f"{slab.perimeter_m:.2f} m")
        slab_table.add_row("Espessura", f"{slab.thickness_m*100:.0f} cm")
        console.print(slab_table)
        console.print()

        # Cargas
        load_table = Table(title="Cargas Calculadas", show_header=False)
        load_table.add_column("Parâmetro", style="cyan")
        load_table.add_column("Valor", style="white")

        load_table.add_row("Peso próprio", f"{result.self_weight_kn:.2f} kN")
        load_table.add_row("Sobrecarga", f"{result.live_load_kn:.2f} kN")
        load_table.add_row(
            "Carga total (×γf)",
            f"[bold]{result.total_load_kn:.2f} kN[/bold]",
        )
        load_table.add_row("Carga por escora", f"{result.load_per_shore_kn:.2f} kN")
        console.print(load_table)
        console.print()

        # Escoras
        shore_table = Table(title="Escoramento")
        shore_table.add_column("Parâmetro", style="cyan")
        shore_table.add_column("Valor", style="white")

        shore_table.add_row("Modelo", result.selected_shore.model)
        shore_table.add_row("Fabricante", result.selected_shore.manufacturer)
        shore_table.add_row(
            "Capacidade",
            f"{result.selected_shore.load_capacity_kn:.1f} kN",
        )
        shore_table.add_row("Quantidade", f"[bold]{len(result.shores)}[/bold]")
        shore_table.add_row("Grid", f"{result.grid_nx} × {result.grid_ny}")
        shore_table.add_row(
            "Espaçamento",
            f"{result.spacing_x_m:.2f} × {result.spacing_y_m:.2f} m",
        )

        utilization = result.load_per_shore_kn / result.selected_shore.load_capacity_kn
        color = "green" if utilization <= 0.8 else "yellow" if utilization <= 1.0 else "red"
        shore_table.add_row("Utilização", f"[{color}]{utilization:.1%}[/{color}]")
        console.print(shore_table)
        console.print()

    # Resumo total
    total_shores = sum(len(r.shores) for r in results)
    total_weight = sum(
        len(r.shores) * r.selected_shore.weight_kg for r in results
    )
    console.print(
        Panel(
            f"[bold]Total: {total_shores} escoras | "
            f"Peso total: {total_weight:.1f} kg[/bold]",
            border_style="green",
        )
    )
    console.print()
