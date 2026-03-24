"""CLI do Escora.AI — entry point."""

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from typing import Optional

from src.parser.dxf_reader import read_dxf, find_slab_layers, get_document_info, get_polylines_by_layer
from src.parser.geometry_extractor import extract_polygons
from src.parser.metadata_extractor import extract_thickness_from_layer
from src.engine.load_calculator import calculate_self_weight, calculate_live_load, calculate_total_load
from src.engine.shore_selector import load_catalog, select_shore
from src.engine.grid_distributor import distribute_shores
from src.engine.validator import validate_result
from src.generator.dxf_writer import generate_output_dxf
from src.generator.report_generator import print_report
from src.generator.bom_generator import write_bom_csv
from src.models.slab import Slab
from src.models.project import ShoringResult
from src.utils.constants import (
    Q_SOBRECARGA_DEFAULT,
    ESPACAMENTO_MAX_DEFAULT,
    ALTURA_DEFAULT,
)

app = typer.Typer(
    name="escora-ai",
    help="Cálculo e posicionamento automático de escoramentos para construção civil.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def calcular(
    arquivo: str = typer.Argument(help="Arquivo DXF de entrada"),
    output: Optional[str] = typer.Option(None, "-o", "--output", help="Arquivo DXF de saída"),
    sobrecarga: float = typer.Option(
        Q_SOBRECARGA_DEFAULT, "--sobrecarga", help="Sobrecarga de trabalho (kN/m²)"
    ),
    espacamento_max: float = typer.Option(
        ESPACAMENTO_MAX_DEFAULT, "--espacamento-max", help="Espaçamento máximo entre escoras (m)"
    ),
    catalogo: Optional[str] = typer.Option(None, "--catalogo", help="Caminho para catálogo JSON customizado"),
    altura: float = typer.Option(
        ALTURA_DEFAULT, "--altura", help="Altura do pé-direito (m)"
    ),
    bom: Optional[str] = typer.Option(None, "--bom", help="Caminho para CSV da lista de materiais"),
):
    """Calcula escoramento para um arquivo DXF."""
    input_path = Path(arquivo)
    if not input_path.exists():
        console.print(f"[red]Erro: arquivo não encontrado: {arquivo}[/red]")
        raise typer.Exit(1)

    if not input_path.suffix.lower() == ".dxf":
        console.print("[red]Erro: apenas arquivos .dxf são suportados[/red]")
        raise typer.Exit(1)

    # 1. Ler DXF
    console.print(f"\n[bold]Lendo:[/bold] {arquivo}")
    doc = read_dxf(str(input_path))

    # 2. Encontrar layers de laje
    slab_layers = find_slab_layers(doc)
    if not slab_layers:
        console.print("[red]Nenhum layer de laje encontrado (padrão: LAJE_XXcm)[/red]")
        console.print("Layers disponíveis:")
        info = get_document_info(doc)
        for layer in info["layers"]:
            console.print(f"  - {layer}")
        raise typer.Exit(1)

    console.print(f"[green]Layers de laje encontrados:[/green] {', '.join(slab_layers)}")

    # 3. Carregar catálogo
    catalog = load_catalog(catalogo)
    console.print(f"[green]Catálogo:[/green] {len(catalog)} modelos de escoras")

    # 4. Processar cada laje
    results: list[ShoringResult] = []

    for layer_name in slab_layers:
        polylines = get_polylines_by_layer(doc, layer_name)
        polygons = extract_polygons(polylines)

        if not polygons:
            console.print(f"[yellow]Aviso: nenhum polígono fechado no layer {layer_name}[/yellow]")
            continue

        thickness = extract_thickness_from_layer(layer_name)

        for polygon in polygons:
            slab = Slab.from_polygon(polygon, layer_name, thickness)

            # Calcular cargas
            self_weight = calculate_self_weight(slab)
            live_load = calculate_live_load(slab, sobrecarga)
            total_load = calculate_total_load(slab, sobrecarga)

            # Selecionar escora
            # Estimar carga por escora para seleção inicial
            estimated_load = total_load / max(1, int(slab.area_m2 / (espacamento_max ** 2)))
            shore = select_shore(catalog, altura, estimated_load)

            if shore is None:
                console.print(
                    f"[red]Erro: nenhuma escora no catálogo suporta a carga "
                    f"({estimated_load:.1f} kN) na altura {altura:.1f}m[/red]"
                )
                raise typer.Exit(1)

            # Distribuir escoras
            shores, nx, ny, sx, sy = distribute_shores(
                slab, shore, total_load, espacamento_max
            )

            load_per_shore = total_load / len(shores)

            # Verificar se precisa de escora mais forte
            if load_per_shore > shore.load_capacity_kn:
                shore = select_shore(catalog, altura, load_per_shore)
                if shore is None:
                    console.print(
                        f"[red]Erro: carga por escora ({load_per_shore:.1f} kN) "
                        f"excede capacidade de todos os modelos[/red]"
                    )
                    raise typer.Exit(1)
                shores, nx, ny, sx, sy = distribute_shores(
                    slab, shore, total_load, espacamento_max
                )
                load_per_shore = total_load / len(shores)

            # Validar
            is_valid, errors = validate_result(shores, sx, sy, espacamento_max)
            if not is_valid:
                for error in errors:
                    console.print(f"[yellow]Aviso: {error}[/yellow]")

            results.append(
                ShoringResult(
                    slab=slab,
                    total_load_kn=round(total_load, 2),
                    self_weight_kn=round(self_weight, 2),
                    live_load_kn=round(live_load, 2),
                    selected_shore=shore,
                    shores=shores,
                    grid_nx=nx,
                    grid_ny=ny,
                    spacing_x_m=round(sx, 4),
                    spacing_y_m=round(sy, 4),
                    load_per_shore_kn=round(load_per_shore, 2),
                )
            )

    if not results:
        console.print("[red]Nenhuma laje processada[/red]")
        raise typer.Exit(1)

    # 5. Relatório
    print_report(results, console)

    # 6. Gerar DXF de saída
    if output is None:
        output = str(input_path.stem) + "_escoras.dxf"

    generate_output_dxf(results, output)
    console.print(f"[green]DXF gerado:[/green] {output}")

    # 7. Gerar BOM
    if bom is None:
        bom = str(input_path.stem) + "_bom.csv"

    write_bom_csv(results, bom)
    console.print(f"[green]Lista de materiais:[/green] {bom}")

    console.print(
        f"\n[bold green]Concluído! {sum(len(r.shores) for r in results)} "
        f"escoras posicionadas.[/bold green]\n"
    )


@app.command()
def info(
    arquivo: str = typer.Argument(help="Arquivo DXF para inspecionar"),
):
    """Mostra informações de um arquivo DXF (layers, entidades)."""
    input_path = Path(arquivo)
    if not input_path.exists():
        console.print(f"[red]Erro: arquivo não encontrado: {arquivo}[/red]")
        raise typer.Exit(1)

    doc = read_dxf(str(input_path))
    doc_info = get_document_info(doc)

    console.print(f"\n[bold]Arquivo:[/bold] {arquivo}")
    console.print(f"[bold]Versão DXF:[/bold] {doc_info['version']}")
    console.print(f"[bold]Total de entidades:[/bold] {doc_info['total_entities']}")
    console.print()

    # Layers
    table = Table(title="Layers")
    table.add_column("Layer", style="cyan")
    table.add_column("É laje?", style="green")

    slab_layers = find_slab_layers(doc)
    for layer in doc_info["layers"]:
        is_slab = "Sim" if layer in slab_layers else ""
        table.add_row(layer, is_slab)

    console.print(table)
    console.print()

    # Tipos de entidades
    if doc_info["entity_counts"]:
        ent_table = Table(title="Entidades por tipo")
        ent_table.add_column("Tipo", style="cyan")
        ent_table.add_column("Quantidade", style="white")

        for etype, count in sorted(doc_info["entity_counts"].items()):
            ent_table.add_row(etype, str(count))

        console.print(ent_table)
    console.print()


@app.command(name="catalogo")
def catalogo_cmd(
    arquivo: Optional[str] = typer.Option(None, "--arquivo", help="Caminho do catálogo JSON"),
):
    """Lista escoras disponíveis no catálogo."""
    catalog = load_catalog(arquivo)

    table = Table(title="Catálogo de Escoras")
    table.add_column("ID", style="cyan")
    table.add_column("Modelo", style="white")
    table.add_column("Altura (m)", style="white")
    table.add_column("Capacidade (kN)", style="green")
    table.add_column("Peso (kg)", style="white")
    table.add_column("Preço (R$)", style="yellow")

    for shore in catalog:
        table.add_row(
            shore.id,
            shore.model,
            f"{shore.height_min_m:.1f} - {shore.height_max_m:.1f}",
            f"{shore.load_capacity_kn:.1f}",
            f"{shore.weight_kg:.1f}",
            f"{shore.price_reference_brl:.2f}",
        )

    console.print()
    console.print(table)
    console.print()


if __name__ == "__main__":
    app()
