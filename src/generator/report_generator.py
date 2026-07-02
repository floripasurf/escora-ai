"""Geração de relatório formatado no terminal via Rich."""

from dataclasses import dataclass
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.models.project import ShoringResult


# ---------------------------------------------------------------------------
# §4.1 BLOCO OBRIGATORIO DA MEMORIA DE CALCULO
# Manual §4.1 / Orguel p.25 — 13 campos minimos que toda memoria de calculo
# deve trazer (preenchidos OU explicitamente marcados como "nao informado").
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MemoriaCalculoFields:
    """Bloco obrigatorio da memoria de calculo (manual §4.1)."""
    espessura_compensado_mm: Optional[float] = None       # 1
    formato_chapa: Optional[str] = None                   # 1 (cont)
    espessura_laje_cm: Optional[float] = None             # 2
    peso_especifico_concreto_kgf_m3: float = 2550.0       # 3 (NBR 6120)
    sobrecarga_kgf_m2: float = 204.0                      # 4 (NBR 15696 §4.2.e: 2.0 kN/m²)
    peso_proprio_laje_kgf_m2: Optional[float] = None      # 5
    carga_escoramento_kgf_m2: Optional[float] = None      # 6
    pe_direito_m: Optional[float] = None                  # 7
    carga_max_admissivel_poste_kgf: Optional[float] = None  # 8
    momento_adm_vm80_tf_m: float = 0.212                  # 9 (212 kgf.m)
    momento_adm_vm130_tf_m: float = 0.516                 # 10 (516 kgf.m)
    momento_adm_h20_aluminio_tf_m: float = 0.500          # 11 (500 kgf.m default)
    tensao_min_apoio_kgf_cm2: Optional[float] = None      # 12 (depende do equipamento)
    notas: str = ""                                       # 13 (observacoes)


def build_memoria_calculo_fields(
    espessura_laje_m: float,
    pe_direito_m: float,
    sobrecarga_kn_m2: float,
    carga_poste_kn: Optional[float] = None,
    tensao_min_apoio_kgf_cm2: Optional[float] = None,
    espessura_compensado_mm: Optional[float] = None,
    formato_chapa: Optional[str] = None,
) -> MemoriaCalculoFields:
    """Constroi o bloco §4.1 da memoria de calculo.

    Manual §4.1. Conversoes:
    - sobrecarga_kn_m2 * 101.97 -> kgf/m²
    - espessura_laje_m * 100 -> cm
    - peso_proprio = espessura_m * 2550 kgf/m³
    - carga_escoramento = peso_proprio + 50 (forma) + sobrecarga
    - carga_poste_kn * 101.97 -> kgf
    """
    peso_proprio_kgf_m2 = espessura_laje_m * 2550.0
    sobrecarga_kgf_m2 = sobrecarga_kn_m2 * 101.97
    carga_escoramento = peso_proprio_kgf_m2 + 50.0 + sobrecarga_kgf_m2
    carga_poste_kgf = carga_poste_kn * 101.97 if carga_poste_kn is not None else None

    return MemoriaCalculoFields(
        espessura_compensado_mm=espessura_compensado_mm,
        formato_chapa=formato_chapa,
        espessura_laje_cm=round(espessura_laje_m * 100.0, 1),
        peso_especifico_concreto_kgf_m3=2550.0,
        sobrecarga_kgf_m2=round(sobrecarga_kgf_m2, 1),
        peso_proprio_laje_kgf_m2=round(peso_proprio_kgf_m2, 1),
        carga_escoramento_kgf_m2=round(carga_escoramento, 1),
        pe_direito_m=round(pe_direito_m, 2),
        carga_max_admissivel_poste_kgf=(
            round(carga_poste_kgf, 1) if carga_poste_kgf is not None else None
        ),
        momento_adm_vm80_tf_m=0.212,
        momento_adm_vm130_tf_m=0.516,
        momento_adm_h20_aluminio_tf_m=0.500,
        tensao_min_apoio_kgf_cm2=tensao_min_apoio_kgf_cm2,
    )


def render_memoria_calculo_table(
    fields: MemoriaCalculoFields,
    title: str = "Bloco Obrigatório — Memória de Cálculo (manual §4.1)",
) -> Table:
    """Renderiza o bloco §4.1 em uma Rich Table.

    Cada campo nao informado e mostrado como "nao informado" conforme exigido
    pelo manual §4.1.
    """
    table = Table(title=title, show_header=True)
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Campo", style="cyan")
    table.add_column("Valor", style="white")

    def _fmt(value, suffix=""):
        if value is None:
            return "[red]nao informado[/red]"
        if isinstance(value, float):
            return f"{value:g}{suffix}"
        return f"{value}{suffix}"

    rows = [
        ("1", "Espessura do compensado", _fmt(fields.espessura_compensado_mm, " mm")),
        ("1", "Formato da chapa", _fmt(fields.formato_chapa)),
        ("2", "Espessura da laje", _fmt(fields.espessura_laje_cm, " cm")),
        ("3", "Peso específico do concreto", _fmt(fields.peso_especifico_concreto_kgf_m3, " kgf/m³")),
        ("4", "Sobrecarga considerada", _fmt(fields.sobrecarga_kgf_m2, " kgf/m²")),
        ("5", "Peso próprio da laje", _fmt(fields.peso_proprio_laje_kgf_m2, " kgf/m²")),
        ("6", "Carga de escoramento", _fmt(fields.carga_escoramento_kgf_m2, " kgf/m²")),
        ("7", "Pé-direito do pavimento", _fmt(fields.pe_direito_m, " m")),
        ("8", "Carga máx. admissível p/ poste", _fmt(fields.carga_max_admissivel_poste_kgf, " kgf")),
        ("9", "Momento admissível VM80", _fmt(fields.momento_adm_vm80_tf_m, " tf·m")),
        ("10", "Momento admissível VM130", _fmt(fields.momento_adm_vm130_tf_m, " tf·m")),
        ("11", "Momento admissível H20/Alumínio", _fmt(fields.momento_adm_h20_aluminio_tf_m, " tf·m")),
        ("12", "Tensão mínima no apoio", _fmt(fields.tensao_min_apoio_kgf_cm2, " kgf/cm²")),
        ("13", "Notas", _fmt(fields.notas or None)),
    ]
    for n, label, value in rows:
        table.add_row(n, label, value)
    return table


def print_memoria_calculo(
    fields: MemoriaCalculoFields,
    console: Optional[Console] = None,
) -> None:
    """Imprime o bloco obrigatorio §4.1 no terminal."""
    if console is None:
        console = Console()
    console.print()
    console.print(render_memoria_calculo_table(fields))
    console.print()


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
        if result.volume_m3 > 0:
            slab_table.add_row("Volume escorado", f"{result.volume_m3:.2f} m³")
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
    total_volume = sum(r.volume_m3 for r in results)
    summary_lines = [
        f"[bold]Total: {total_shores} escoras | "
        f"Peso total: {total_weight:.1f} kg[/bold]"
    ]
    if total_volume > 0:
        summary_lines.append(f"[bold]Volume total: {total_volume:.2f} m³[/bold]")
    console.print(
        Panel(
            "\n".join(summary_lines),
            border_style="green",
        )
    )
    console.print()


def print_calculation_summary(
    calc_result,
    console: Console | None = None,
) -> None:
    """Imprime bloco resumo de volume do pipeline completo (com deduções)."""
    if console is None:
        console = Console()

    if calc_result.slab_volume_gross_m3 <= 0:
        return

    table = Table(title="Volume Escorado", show_header=False)
    table.add_column("Componente", style="cyan")
    table.add_column("Valor", style="white")
    table.add_row(
        "Volume bruto (lajes × pé-direito)",
        f"{calc_result.slab_volume_gross_m3:.2f} m³",
    )
    table.add_row(
        "(−) Vigas",
        f"{calc_result.beam_volume_deducted_m3:.2f} m³",
    )
    table.add_row(
        "(−) Pilares",
        f"{calc_result.pillar_volume_deducted_m3:.2f} m³",
    )
    table.add_row(
        "Volume líquido",
        f"[bold]{calc_result.total_volume_m3:.2f} m³[/bold]",
    )
    console.print(table)
    console.print()
