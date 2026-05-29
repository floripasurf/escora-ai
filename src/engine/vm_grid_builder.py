"""Gerador de grid de Vigas Metalicas (VMs) primarias e secundarias.

Implementacao da §28 do manual de normas (gap critico identificado em
2026-05-28). Em projetos reais Orguel/SH/Mills, TODAS as escoras
(telescopicas e torres) recebem um grid completo de VMs no topo:

1. **Vigas primarias (guias)** - apoiadas sobre os forcados; conectam
   linhas de escoras no eixo principal do painel. Modelo padrao: VM130.
2. **Vigas secundarias (barrotes)** - perpendiculares as primarias;
   apoiam o compensado diretamente. Modelo padrao: VM80. Espacamento
   multiplo da largura util da chapa de compensado (244mm para 1220mm,
   220mm para 1100mm).

Referencias visuais: UTFPR TCC Bedenaroski 2021 Figura 28 (Projeto 2 -
escoras telescopicas com vigas H20-Eco longitudinais + secundarias
perpendiculares densas).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, List, Literal, Optional, Sequence, Tuple

from src.models.plywood import (
    DEFAULT_PLYWOOD_FORMAT_MM,
    PlywoodSpec,
    default_plywood_spec,
)


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

VMRole = Literal["primaria", "secundaria"]


@dataclass(frozen=True)
class VMSegment:
    """Um segmento individual de viga metalica no grid."""

    role: VMRole                       # "primaria" ou "secundaria"
    model: str                         # "VM130", "VM80", "H20", "ALU14"...
    length_mm: int                     # Comprimento real do segmento (mm)
    start: Tuple[float, float]         # (x, y) em metros
    end: Tuple[float, float]           # (x, y) em metros
    axis: Literal["x", "y"]            # Direcao do segmento
    load_kn_m: float = 0.0             # Carga linear estimada (kN/m)
    span_m: float = 0.0                # Vao geometrico (entre apoios)
    moment_kn_m: float = 0.0           # Momento aplicado (kN.m)
    moment_adm_kn_m: float = 0.0       # Momento admissivel do modelo
    flecha_mm: float = 0.0             # Flecha calculada (mm)
    flecha_adm_mm: float = 0.0         # Flecha admissivel (mm)
    passes_moment: bool = True
    passes_deflection: bool = True
    notes: str = ""

    @property
    def utilization(self) -> float:
        """Maior entre utilizacao por momento e por flecha."""
        u_m = self.moment_kn_m / self.moment_adm_kn_m if self.moment_adm_kn_m > 0 else 0.0
        u_d = self.flecha_mm / self.flecha_adm_mm if self.flecha_adm_mm > 0 else 0.0
        return max(u_m, u_d)


@dataclass
class VMGrid:
    """Grid completo de VMs para um painel de laje.

    Atributos:
    - primaria_axis: eixo da viga primaria ("x" ou "y").
    - segments: lista de VMSegment (primarias + secundarias).
    - bom: dicionario {model: {length_mm: quantidade}} para gerar BOM.
    - issues: avisos/erros (segmentos que nao passam, etc).
    """

    primaria_axis: Literal["x", "y"] = "x"
    segments: List[VMSegment] = field(default_factory=list)
    bom: dict = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)

    def add_segment(self, seg: VMSegment) -> None:
        self.segments.append(seg)
        self.bom.setdefault(seg.model, {}).setdefault(seg.length_mm, 0)
        self.bom[seg.model][seg.length_mm] += 1

    def primarias(self) -> List[VMSegment]:
        return [s for s in self.segments if s.role == "primaria"]

    def secundarias(self) -> List[VMSegment]:
        return [s for s in self.segments if s.role == "secundaria"]

    def total_length_m(self, model: Optional[str] = None) -> float:
        total = 0.0
        for s in self.segments:
            if model is not None and s.model != model:
                continue
            total += s.length_mm / 1000.0
        return total


# ---------------------------------------------------------------------------
# Selecao de comprimento de VM (catalog-aware)
# ---------------------------------------------------------------------------

# Comprimentos padrao Orguel (manual §13.3 / Orguel p.20). Substituidos pelo
# catalog real se equipment.yaml estiver disponivel.
DEFAULT_VM_LENGTHS_MM = {
    "VM80": [1000, 1550, 2050, 2550, 3100, 3600, 4100],
    "VM130": [1550, 2050, 2550, 3100, 3600, 4100],
    "VM50": [650, 1000, 1550, 2050, 2550, 3100, 3600, 4100],
}


def select_vm_length_mm(
    requested_length_m: float,
    model: str,
    available_lengths_mm: Optional[Sequence[int]] = None,
    splice_allowed: bool = False,
) -> int:
    """Seleciona o comprimento de VM mais economico que cobre o vao.

    Estrategia:
    1. Procura o menor comprimento >= requested em ``available_lengths_mm``.
    2. Se nenhum cobre e ``splice_allowed`` for True, retorna o maior
       disponivel (caller deve emendar).
    3. Caso contrario, retorna o maior disponivel.

    Args:
        requested_length_m: vao geometrico desejado (m).
        model: "VM80", "VM130", "VM50", etc.
        available_lengths_mm: lista de comprimentos disponiveis (mm). Se
            None, usa DEFAULT_VM_LENGTHS_MM[model].
        splice_allowed: se True, permite que retorne o maior e o caller
            emende; default False (retorna o maior mesmo assim).
    """
    lengths = list(available_lengths_mm) if available_lengths_mm else DEFAULT_VM_LENGTHS_MM.get(model, [])
    if not lengths:
        # Fallback: arredonda para multiplo de 500 mm
        return int(math.ceil(requested_length_m * 2) * 500)
    target_mm = int(math.ceil(requested_length_m * 1000))
    fitting = [L for L in lengths if L >= target_mm]
    if fitting:
        return min(fitting)
    return max(lengths)


# ---------------------------------------------------------------------------
# Construcao do grid a partir das escoras posicionadas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ShorePoint:
    """Posicao 2D minima de escora para o builder (desacopla de PositionedShore)."""
    x: float
    y: float


def _detect_primary_axis(
    shore_points: Sequence[ShorePoint],
    polygon_bbox: Optional[Tuple[float, float, float, float]] = None,
) -> Literal["x", "y"]:
    """Decide a direcao da viga primaria (maior eixo do painel).

    Manual §28.4: VM primaria corre no eixo maior do painel para minimizar
    quantidade de cortes e emendas.

    Se o bbox e fornecido, usa-o; senao deriva dos shore_points.
    """
    if polygon_bbox is not None:
        min_x, min_y, max_x, max_y = polygon_bbox
    else:
        xs = [s.x for s in shore_points]
        ys = [s.y for s in shore_points]
        if not xs:
            return "x"
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y
    # Primaria corre PERPENDICULAR ao eixo maior do painel:
    # se painel e largo em X (width > height), primarias correm em Y
    # para que cada primaria seja curta e os barrotes (secundarias)
    # densos atravessem o lado longo.
    # Manual §28.1: primarias = guias mais robustas (VM130), secundarias
    # = barrotes densos (VM80) com espacamento do compensado.
    return "y" if width >= height else "x"


def _group_shores_by_row(
    shore_points: Sequence[ShorePoint],
    axis: Literal["x", "y"],
    tolerance_m: float = 0.30,
) -> List[List[ShorePoint]]:
    """Agrupa escoras em linhas (rows) perpendiculares ao eixo dado.

    Se axis="x", agrupa por Y (linhas horizontais de escoras).
    Se axis="y", agrupa por X (linhas verticais de escoras).
    """
    coord = (lambda s: s.y) if axis == "x" else (lambda s: s.x)
    sorted_shores = sorted(shore_points, key=coord)
    if not sorted_shores:
        return []
    rows: List[List[ShorePoint]] = []
    current = [sorted_shores[0]]
    for s in sorted_shores[1:]:
        if abs(coord(s) - coord(current[0])) <= tolerance_m:
            current.append(s)
        else:
            rows.append(current)
            current = [s]
    rows.append(current)
    # Sort each row by the axis coordinate
    sort_key = (lambda s: s.x) if axis == "x" else (lambda s: s.y)
    return [sorted(r, key=sort_key) for r in rows]


def _compute_segment_load_and_moment(
    span_m: float,
    q_kn_m: float,
    moment_adm_kn_m: float,
    ei_kn_m2: float,
    deflection_limit_denominator: int = 500,
) -> Tuple[float, float, float, float, bool, bool]:
    """Retorna (M, M_adm, flecha_mm, flecha_adm_mm, passes_M, passes_flecha).

    Manual §22.2 (M=qL²/8) + §22.3 (flecha = 5qL⁴/384EI).
    """
    M = q_kn_m * span_m * span_m / 8.0
    # Flecha bi-apoiada: f = 5qL^4 / (384 EI) -> em metros, converter mm
    if ei_kn_m2 > 0:
        flecha_m = 5 * q_kn_m * span_m ** 4 / (384.0 * ei_kn_m2)
    else:
        flecha_m = 0.0
    flecha_mm = flecha_m * 1000.0
    # Flecha admissivel: 1 + L/X (manual §22.3, NBR 15696 §4.3.2)
    flecha_adm_mm = 1.0 + (span_m * 1000.0) / deflection_limit_denominator
    passes_M = moment_adm_kn_m <= 0 or M <= moment_adm_kn_m
    passes_flecha = flecha_adm_mm <= 0 or flecha_mm <= flecha_adm_mm
    return M, moment_adm_kn_m, flecha_mm, flecha_adm_mm, passes_M, passes_flecha


def build_vm_grid(
    shore_points: Sequence[ShorePoint],
    *,
    primaria_model: str = "VM130",
    secundaria_model: str = "VM80",
    primaria_moment_adm_kn_m: float = 5.06,    # VM130: 516 kgf.m
    primaria_ei_kn_m2: float = 461.8,
    secundaria_moment_adm_kn_m: float = 2.08,  # VM80: 212 kgf.m
    secundaria_ei_kn_m2: float = 146.8,
    plywood: Optional[PlywoodSpec] = None,
    polygon_bbox: Optional[Tuple[float, float, float, float]] = None,
    load_kn_m2: float = 7.7,                   # padrao: laje 12cm + sobrec.
    available_primaria_lengths_mm: Optional[Sequence[int]] = None,
    available_secundaria_lengths_mm: Optional[Sequence[int]] = None,
    row_tolerance_m: float = 0.30,
) -> VMGrid:
    """Constroi o grid completo de VMs sobre um conjunto de escoras.

    Algoritmo (manual §28.4):
    1. Detecta eixo da primaria pelo bbox do painel (perpendicular ao
       lado maior).
    2. Agrupa escoras em linhas perpendiculares ao eixo da primaria.
    3. Para cada linha: gera VM primaria conectando escoras adjacentes.
       Vao = espacamento entre escoras. Comprimento real = seleciona do
       catalogo (`select_vm_length_mm`).
    4. Calcula barrote espacamento = `seam_multiple_mm` do compensado.
    5. Gera VM secundaria perpendicular, cobrindo o bbox da laje a cada
       passo de barrote. Vao = espacamento entre linhas primarias.
    6. Verifica momento e flecha por segmento.
    """
    plywood = plywood or default_plywood_spec()
    seam_mm = plywood.effective_seam_multiple_mm()
    grid = VMGrid()

    if len(shore_points) < 2:
        grid.issues.append("Menos de 2 escoras: nenhum grid de VM gerado.")
        return grid

    primary_axis = _detect_primary_axis(shore_points, polygon_bbox)
    grid.primaria_axis = primary_axis

    # Direcao perpendicular = direcao das secundarias (barrotes)
    secondary_axis: Literal["x", "y"] = "y" if primary_axis == "x" else "x"

    # 1) Vigas PRIMARIAS: agrupar escoras em linhas perpendiculares ao
    # eixo primario, e conectar adjacentes.
    rows = _group_shores_by_row(shore_points, primary_axis, row_tolerance_m)

    # Carga linear na primaria = carga distribuida x faixa de influencia
    # (espacamento entre linhas perpendiculares). Aproximacao: usar
    # espacamento medio entre rows.
    if len(rows) >= 2:
        coord_row = (lambda r: r[0].y) if primary_axis == "x" else (lambda r: r[0].x)
        row_coords = sorted(coord_row(r) for r in rows)
        gaps = [row_coords[i + 1] - row_coords[i] for i in range(len(row_coords) - 1)]
        avg_row_spacing = sum(gaps) / len(gaps)
    else:
        avg_row_spacing = 1.0
    influence_width_primaria_m = avg_row_spacing
    q_primaria_kn_m = load_kn_m2 * influence_width_primaria_m

    for row in rows:
        if len(row) < 2:
            continue
        for s1, s2 in zip(row, row[1:]):
            span_m = math.hypot(s2.x - s1.x, s2.y - s1.y)
            L_mm = select_vm_length_mm(
                span_m, primaria_model, available_primaria_lengths_mm,
            )
            M, Madm, f, fadm, passM, passF = _compute_segment_load_and_moment(
                span_m, q_primaria_kn_m,
                primaria_moment_adm_kn_m, primaria_ei_kn_m2,
            )
            seg = VMSegment(
                role="primaria",
                model=primaria_model,
                length_mm=L_mm,
                start=(s1.x, s1.y),
                end=(s2.x, s2.y),
                axis=primary_axis,
                load_kn_m=round(q_primaria_kn_m, 2),
                span_m=round(span_m, 3),
                moment_kn_m=round(M, 3),
                moment_adm_kn_m=Madm,
                flecha_mm=round(f, 2),
                flecha_adm_mm=round(fadm, 2),
                passes_moment=passM,
                passes_deflection=passF,
            )
            grid.add_segment(seg)
            if not passM:
                grid.issues.append(
                    f"VM primaria ({s1.x:.2f},{s1.y:.2f})->({s2.x:.2f},{s2.y:.2f}): "
                    f"momento {M:.2f} > {Madm:.2f} kN.m"
                )
            if not passF:
                grid.issues.append(
                    f"VM primaria ({s1.x:.2f},{s1.y:.2f})->({s2.x:.2f},{s2.y:.2f}): "
                    f"flecha {f:.1f}mm > {fadm:.1f}mm"
                )

    # 2) Vigas SECUNDARIAS (barrotes): perpendiculares as primarias, com
    # espacamento = seam_multiple_mm do compensado. Cobrem o bbox da laje.
    if polygon_bbox is not None:
        min_x, min_y, max_x, max_y = polygon_bbox
    else:
        xs = [s.x for s in shore_points]
        ys = [s.y for s in shore_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

    seam_m = seam_mm / 1000.0
    span_secundaria_m = avg_row_spacing  # apoia em duas primarias adjacentes
    q_secundaria_kn_m = load_kn_m2 * seam_m

    if secondary_axis == "x":
        # Secundarias correm em X; uma a cada passo em Y
        n_barrotes = max(2, int(round((max_y - min_y) / seam_m)) + 1)
        actual_step = (max_y - min_y) / max(n_barrotes - 1, 1)
        for i in range(n_barrotes):
            y = min_y + i * actual_step
            length_geom_m = max_x - min_x
            L_mm = select_vm_length_mm(
                span_secundaria_m, secundaria_model,
                available_secundaria_lengths_mm,
            )
            M, Madm, f, fadm, passM, passF = _compute_segment_load_and_moment(
                span_secundaria_m, q_secundaria_kn_m,
                secundaria_moment_adm_kn_m, secundaria_ei_kn_m2,
            )
            seg = VMSegment(
                role="secundaria",
                model=secundaria_model,
                length_mm=L_mm,
                start=(min_x, y),
                end=(max_x, y),
                axis="x",
                load_kn_m=round(q_secundaria_kn_m, 2),
                span_m=round(span_secundaria_m, 3),
                moment_kn_m=round(M, 3),
                moment_adm_kn_m=Madm,
                flecha_mm=round(f, 2),
                flecha_adm_mm=round(fadm, 2),
                passes_moment=passM,
                passes_deflection=passF,
                notes=(
                    f"barrote (compensado {plywood.format_label()}, "
                    f"passo {seam_mm}mm)"
                ),
            )
            grid.add_segment(seg)
    else:  # secondary_axis == "y"
        n_barrotes = max(2, int(round((max_x - min_x) / seam_m)) + 1)
        actual_step = (max_x - min_x) / max(n_barrotes - 1, 1)
        for i in range(n_barrotes):
            x = min_x + i * actual_step
            L_mm = select_vm_length_mm(
                span_secundaria_m, secundaria_model,
                available_secundaria_lengths_mm,
            )
            M, Madm, f, fadm, passM, passF = _compute_segment_load_and_moment(
                span_secundaria_m, q_secundaria_kn_m,
                secundaria_moment_adm_kn_m, secundaria_ei_kn_m2,
            )
            seg = VMSegment(
                role="secundaria",
                model=secundaria_model,
                length_mm=L_mm,
                start=(x, min_y),
                end=(x, max_y),
                axis="y",
                load_kn_m=round(q_secundaria_kn_m, 2),
                span_m=round(span_secundaria_m, 3),
                moment_kn_m=round(M, 3),
                moment_adm_kn_m=Madm,
                flecha_mm=round(f, 2),
                flecha_adm_mm=round(fadm, 2),
                passes_moment=passM,
                passes_deflection=passF,
                notes=(
                    f"barrote (compensado {plywood.format_label()}, "
                    f"passo {seam_mm}mm)"
                ),
            )
            grid.add_segment(seg)

    return grid


def vm_grid_bom_summary(grid: VMGrid) -> List[Tuple[str, int, int]]:
    """Resumo do BOM em lista [(model, length_mm, qty), ...]."""
    out: List[Tuple[str, int, int]] = []
    for model, lengths in grid.bom.items():
        for L_mm, qty in sorted(lengths.items()):
            out.append((model, L_mm, qty))
    return out
