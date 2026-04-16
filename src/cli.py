"""CLI do Escora.AI — entry point."""

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from typing import Optional

from src.parser.dxf_reader import read_dxf, find_slab_layers, get_document_info, get_polylines_by_layer
from src.parser.geometry_extractor import extract_polygons
from src.parser.metadata_extractor import extract_thickness_from_layer
from src.generator.dxf_writer import generate_output_dxf
from src.generator.report_generator import print_report
from src.generator.bom_generator import write_bom_csv
from src.output.csv_generator import write_consumption_csv
from src.output.report_data import ConsumptionByHeightRow, ReportData, SummaryData
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


def _build_cli_consumption_report(results: list) -> ReportData:
    """Constrói um `ReportData` mínimo (apenas consumption_rows) a partir
    de `ShoringResult`s simples do CLI — sem acessórios, sem deduções de
    vigas/pilares (cobertura limitada do CLI vs API).
    """
    groups: dict = {}
    for r in results:
        key = round(r.pe_direito_m or 0.0, 2)
        g = groups.setdefault(
            key,
            {"area_m2": 0.0, "volume_m3": 0.0, "shores_kg": 0.0},
        )
        g["area_m2"] += r.slab.area_m2
        g["volume_m3"] += r.volume_m3 or (r.slab.area_m2 * (r.pe_direito_m or 0.0))
        weight_unit = getattr(r.selected_shore, "weight_kg", 0.0) or 0.0
        g["shores_kg"] += weight_unit * len(r.shores)

    rows: list[ConsumptionByHeightRow] = []
    for pe_key in sorted(groups.keys()):
        g = groups[pe_key]
        bruto = g["volume_m3"]
        area = g["area_m2"]
        shores_kg = g["shores_kg"]
        liquido = bruto  # CLI não tem deduções de vigas/pilares
        rows.append(ConsumptionByHeightRow(
            pe_direito_m=pe_key,
            area_m2=round(area, 2),
            volume_bruto_m3=round(bruto, 2),
            volume_liquido_m3=round(liquido, 2),
            shores_weight_kg=round(shores_kg, 2),
            accessories_weight_kg=0.0,
            total_weight_kg=round(shores_kg, 2),
            rate_kg_m3_bruto=round(shores_kg / bruto, 2) if bruto > 0 else 0.0,
            rate_kg_m3_liquido=round(shores_kg / liquido, 2) if liquido > 0 else 0.0,
            rate_kg_m2=round(shores_kg / area, 2) if area > 0 else 0.0,
            category_label="Laje",
        ))

    sum_area = sum(r.area_m2 for r in rows)
    sum_bruto = sum(r.volume_bruto_m3 for r in rows)
    sum_liquido = sum(r.volume_liquido_m3 for r in rows)
    sum_shores = sum(r.shores_weight_kg for r in rows)
    totals = {
        "area_m2": round(sum_area, 2),
        "volume_bruto_m3": round(sum_bruto, 2),
        "volume_liquido_m3": round(sum_liquido, 2),
        "shores_kg": round(sum_shores, 2),
        "accessories_kg": 0.0,
        "total_kg": round(sum_shores, 2),
        "rate_kg_m3_bruto": round(sum_shores / sum_bruto, 2) if sum_bruto > 0 else 0.0,
        "rate_kg_m3_liquido": round(sum_shores / sum_liquido, 2) if sum_liquido > 0 else 0.0,
        "rate_kg_m2": round(sum_shores / sum_area, 2) if sum_area > 0 else 0.0,
    }

    summary = SummaryData(
        total_shores=sum(len(r.shores) for r in results),
        total_load_kn=sum(r.total_load_kn for r in results),
        pe_direito_m=results[0].pe_direito_m if results else 0.0,
        pe_direito_is_default=False,
        slab_thickness_m=results[0].slab.thickness_m if results else 0.0,
        thickness_is_default=False,
        beam_count=0,
        slab_count=len(results),
        is_valid=True,
    )
    return ReportData(
        project_name="cli",
        date="",
        summary=summary,
        consumption_rows=rows,
        consumption_totals=totals,
    )


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
    consumo: Optional[str] = typer.Option(None, "--consumo", help="Caminho para CSV de consumo por pé-direito (orçamento interno)"),
    layer: Optional[str] = typer.Option(None, "--layer", help="Layer específico da laje (ignora detecção automática)"),
    espessura: Optional[float] = typer.Option(None, "--espessura", help="Espessura da laje em cm (override da detecção automática)"),
    area_min: float = typer.Option(1.0, "--area-min", help="Área mínima de polígono para considerar como laje (m²)"),
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
    if layer:
        slab_layers = [layer]
        console.print(f"[green]Layer especificado:[/green] {layer}")
    else:
        slab_layers = find_slab_layers(doc)
        if not slab_layers:
            console.print("[red]Nenhum layer de laje detectado automaticamente (padrão: LAJE_XXcm)[/red]")
            console.print("[yellow]Use --layer NOME para especificar o layer manualmente.[/yellow]")
            console.print("Layers disponíveis:")
            info = get_document_info(doc)
            for l in info["layers"]:
                console.print(f"  - {l}")
            raise typer.Exit(1)
        console.print(f"[green]Layers de laje encontrados:[/green] {', '.join(slab_layers)}")

    # 3. Carregar catálogo
    catalog = load_catalog(catalogo)
    console.print(f"[green]Catálogo:[/green] {len(catalog)} modelos de escoras")

    # 4. Processar cada laje
    results: list[ShoringResult] = []

    for layer_name in slab_layers:
        polylines = get_polylines_by_layer(doc, layer_name)
        polygons = extract_polygons(polylines, min_area=area_min)

        if not polygons:
            console.print(f"[yellow]Aviso: nenhum polígono fechado no layer {layer_name}[/yellow]")
            continue

        if espessura is not None:
            thickness = espessura / 100.0  # cm → m
        else:
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
                    pe_direito_m=altura,
                    volume_m3=round(slab.area_m2 * altura, 2),
                    category="laje",
                    label=f"Laje {len(results) + 1}",
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

    # 8. Consumo por pé-direito (opcional). Por padrão, gera ao lado do BOM.
    if consumo is None:
        consumo = str(Path(bom).with_name(Path(bom).stem + "_consumo.csv"))
    consumption_report = _build_cli_consumption_report(results)
    write_consumption_csv(consumption_report, consumo)
    console.print(f"[green]Consumo por pé-direito:[/green] {consumo}")

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


@app.command()
def manual(
    comprimento: float = typer.Argument(help="Comprimento da laje em metros"),
    largura: float = typer.Argument(help="Largura da laje em metros"),
    espessura_cm: float = typer.Argument(help="Espessura da laje em centímetros"),
    output: Optional[str] = typer.Option(None, "-o", "--output", help="Arquivo DXF de saída"),
    sobrecarga: float = typer.Option(
        Q_SOBRECARGA_DEFAULT, "--sobrecarga", help="Sobrecarga de trabalho (kN/m²)"
    ),
    espacamento_max: float = typer.Option(
        ESPACAMENTO_MAX_DEFAULT, "--espacamento-max", help="Espaçamento máximo entre escoras (m)"
    ),
    catalogo_path: Optional[str] = typer.Option(None, "--catalogo", help="Caminho para catálogo JSON"),
    altura: float = typer.Option(
        ALTURA_DEFAULT, "--altura", help="Altura do pé-direito (m)"
    ),
    bom_path: Optional[str] = typer.Option(None, "--bom", help="Caminho para CSV da lista de materiais"),
):
    """Calcula escoramento informando dimensões manualmente (sem DXF)."""
    from shapely.geometry import Polygon as ShapelyPolygon

    thickness_m = espessura_cm / 100.0
    polygon = ShapelyPolygon([
        (0, 0), (comprimento, 0), (comprimento, largura), (0, largura),
    ])
    slab = Slab.from_polygon(polygon, f"LAJE_{espessura_cm:.0f}CM", thickness_m)

    console.print(f"\n[bold]Laje:[/bold] {comprimento} x {largura} m, espessura {espessura_cm:.0f} cm")

    catalog = load_catalog(catalogo_path)

    self_weight = calculate_self_weight(slab)
    live_load = calculate_live_load(slab, sobrecarga)
    total_load = calculate_total_load(slab, sobrecarga)

    estimated_load = total_load / max(1, int(slab.area_m2 / (espacamento_max ** 2)))
    shore = select_shore(catalog, altura, estimated_load)

    if shore is None:
        console.print(f"[red]Erro: nenhuma escora suporta a carga na altura {altura:.1f}m[/red]")
        raise typer.Exit(1)

    shores, nx, ny, sx, sy = distribute_shores(slab, shore, total_load, espacamento_max)
    load_per_shore = total_load / len(shores)

    if load_per_shore > shore.load_capacity_kn:
        shore = select_shore(catalog, altura, load_per_shore)
        if shore is None:
            console.print(f"[red]Erro: carga por escora excede todos os modelos[/red]")
            raise typer.Exit(1)
        shores, nx, ny, sx, sy = distribute_shores(slab, shore, total_load, espacamento_max)
        load_per_shore = total_load / len(shores)

    is_valid, errors = validate_result(shores, sx, sy, espacamento_max)
    if not is_valid:
        for error in errors:
            console.print(f"[yellow]Aviso: {error}[/yellow]")

    result = ShoringResult(
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
        pe_direito_m=altura,
        volume_m3=round(slab.area_m2 * altura, 2),
        category="laje",
        label="Laje 1",
    )

    print_report([result], console)

    if output:
        generate_output_dxf([result], output)
        console.print(f"[green]DXF gerado:[/green] {output}")

    bom_out = bom_path or "bom.csv"
    write_bom_csv([result], bom_out)
    console.print(f"[green]Lista de materiais:[/green] {bom_out}")

    console.print(
        f"\n[bold green]Concluído! {len(shores)} escoras posicionadas.[/bold green]\n"
    )


@app.command()
def inspecionar(
    arquivo: str = typer.Argument(help="Arquivo DXF a inspecionar"),
):
    """Lista polígonos candidatos a laje com bounds, área e categoria proposta.

    Diagnóstico para DXFs onde a classificação de beiral/platibanda/balanço
    não dispara por layer keyword (ex.: arquivos TQS com layers numéricos).
    Reutiliza o mesmo pipeline de extração do estágio de cálculo (hatches +
    polylines fechados) e aplica as heurísticas geométricas de categoria.
    """
    from src.pipeline.stage_parse import parse_dxf
    from src.pipeline.runner import _detect_coordinate_scale
    from src.utils.labels import classify_layer, CATEGORY_DEFAULT, CATEGORY_LABELS_PT

    input_path = Path(arquivo)
    if not input_path.exists():
        console.print(f"[red]Erro: arquivo não encontrado: {arquivo}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Inspecionando:[/bold] {arquivo}")
    parse = parse_dxf(str(input_path))
    scale = _detect_coordinate_scale(parse)
    console.print(f"[green]Escala detectada:[/green] {scale}")

    all_hatches = [
        {
            "points": [(x * scale, y * scale) for x, y in h.points],
            "layer": h.layer,
            "pattern_name": h.pattern_name,
            "is_solid": h.is_solid,
            "area": h.area * scale * scale,
        }
        for h in parse.hatches
    ]
    all_polylines = [
        {
            "points": [(x * scale, y * scale) for x, y in pl.points],
            "layer": pl.layer,
            "is_closed": pl.is_closed,
        }
        for pl in parse.polylines
    ]

    polygons = derive_slabs_from_boundaries(all_hatches, all_polylines, scale=1.0)

    if not polygons:
        console.print("[yellow]Nenhum polígono candidato a laje encontrado.[/yellow]")
        return

    def _propose_category(poly, layer_name: str, all_polys) -> str:
        cat = classify_layer(layer_name)
        if cat:
            return cat
        try:
            minx_, miny_, maxx_, maxy_ = poly.bounds
            w_ = maxx_ - minx_
            h_ = maxy_ - miny_
            short_ = min(w_, h_)
            long_ = max(w_, h_)
            if short_ > 0:
                ratio_ = long_ / short_
                if short_ <= 0.5 and ratio_ >= 3.0:
                    rep = poly.representative_point()
                    for other in all_polys:
                        if other is poly:
                            continue
                        if other.area < poly.area * 5.0:
                            continue
                        try:
                            if other.boundary.buffer(0.30).contains(rep):
                                return "platibanda"
                        except Exception:
                            continue
        except Exception:
            pass
        return CATEGORY_DEFAULT

    def _layer_for(poly) -> str:
        best_layer = ""
        best_score = 0.0
        for raw in list(all_polylines) + list(all_hatches):
            pts = raw.get("points") or []
            if len(pts) < 3:
                continue
            try:
                from shapely.geometry import Polygon as _P
                cand = _P(pts)
                if not cand.is_valid or cand.is_empty:
                    continue
                inter = poly.intersection(cand).area
                if inter <= 0 or poly.area <= 0:
                    continue
                score = inter / poly.area
                if score > best_score:
                    best_score = score
                    best_layer = raw.get("layer", "") or ""
            except Exception:
                continue
        return best_layer

    table = Table(title=f"Polígonos candidatos ({len(polygons)})")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Layer", style="white")
    table.add_column("Área (m²)", justify="right")
    table.add_column("Bounds (min_x, min_y, max_x, max_y)", style="white")
    table.add_column("Lado curto (m)", justify="right")
    table.add_column("Ratio", justify="right")
    table.add_column("Categoria proposta", style="green")

    for i, poly in enumerate(polygons, start=1):
        minx, miny, maxx, maxy = poly.bounds
        w = maxx - minx
        h = maxy - miny
        short = min(w, h)
        long = max(w, h)
        ratio = long / short if short > 0 else float("inf")
        layer = _layer_for(poly)
        category = _propose_category(poly, layer, polygons)
        table.add_row(
            str(i),
            layer or "—",
            f"{poly.area:.2f}",
            f"({minx:.2f}, {miny:.2f}, {maxx:.2f}, {maxy:.2f})",
            f"{short:.2f}",
            f"{ratio:.2f}",
            CATEGORY_LABELS_PT.get(category, category),
        )

    console.print(table)
    console.print()


if __name__ == "__main__":
    app()
