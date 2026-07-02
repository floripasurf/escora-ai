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
from typing import List, Literal, Optional, Sequence, Tuple

from src.engine.vm_checks import (
    check_shear,
    seam_positions,
    snapped_positions as _snapped_positions,
    # Re-export retro-compat: pipeline/stage_calculate importa este nome
    # daqui (manual §28.5); implementacao movida para vm_checks (<500 linhas).
    compute_segment_load_and_moment as _compute_segment_load_and_moment,
)
from src.models.plywood import (
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
    # Pendencia 17 (NBR 15696 Anexo B/4.4): cortante. shear_adm_kn = 0.0
    # significa "catalogo sem valor publicado" -> verificacao pulada.
    shear_kn: float = 0.0
    shear_adm_kn: float = 0.0
    passes_shear: bool = True

    @property
    def utilization(self) -> float:
        """Maior entre utilizacao por momento, flecha e cortante."""
        u_m = self.moment_kn_m / self.moment_adm_kn_m if self.moment_adm_kn_m > 0 else 0.0
        u_d = self.flecha_mm / self.flecha_adm_mm if self.flecha_adm_mm > 0 else 0.0
        u_v = self.shear_kn / self.shear_adm_kn if self.shear_adm_kn > 0 else 0.0
        return max(u_m, u_d, u_v)


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
    # Pendencia 18 (manual §11.2): coordenadas das linhas de emenda de
    # compensado (ao longo do eixo de distribuicao dos barrotes). Cada
    # linha recebe +1 barrote extra (transpasse, Orguel p.115).
    seam_lines: List[float] = field(default_factory=list)

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


def build_vm_grid(
    shore_points: Sequence[ShorePoint],
    *,
    primaria_model: str = "VM130",
    secundaria_model: str = "VM80",
    primaria_moment_adm_kn_m: float = 5.06,    # VM130: 516 kgf.m
    primaria_ei_kn_m2: float = 461.8,
    secundaria_moment_adm_kn_m: float = 2.08,  # VM80: 212 kgf.m
    secundaria_ei_kn_m2: float = 146.8,
    # Pendencia 17: cortante admissivel do FABRICANTE (kN). Default 0.0 =
    # sem valor publicado -> verificacao pulada (VM130/VM80 Orguel/Mecanor
    # nao publicam cortante; ALU14 = 20.6 kN via JAU VA140, manual §13.3).
    primaria_shear_adm_kn: float = 0.0,
    secundaria_shear_adm_kn: float = 0.0,
    plywood: Optional[PlywoodSpec] = None,
    polygon_bbox: Optional[Tuple[float, float, float, float]] = None,
    load_kn_m2: float = 7.7,                   # padrao: laje 12cm + sobrec.
    secondary_spacing_m: Optional[float] = None,
    available_primaria_lengths_mm: Optional[Sequence[int]] = None,
    available_secundaria_lengths_mm: Optional[Sequence[int]] = None,
    row_tolerance_m: float = 0.30,
    global_origin: Optional[Tuple[float, float]] = None,
    primary_axis_override: Optional[Literal["x", "y"]] = None,
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
    5. Gera VM secundaria perpendicular, snap-ada a um grid GLOBAL
       (manual §28.7 / 2026-05-30, fix do bug 'VMs proximas demais').
       Sem ``global_origin``, cai no comportamento anterior (por painel,
       que sobrepoe barrotes entre lajes adjacentes).
    6. Verifica momento e flecha por segmento.

    Args:
        global_origin: (ox, oy) em metros. Quando fornecido, todas as
            posicoes de barrotes secundarios sao snap-adas a multiplos
            de seam_m a partir desse ponto: y_k = oy + k * seam_m.
            Isso garante que paineis adjacentes usam a MESMA grade,
            eliminando barrotes sobrepostos nas bordas.
    """
    plywood = plywood or default_plywood_spec()
    seam_mm = plywood.effective_seam_multiple_mm()
    grid = VMGrid()

    if len(shore_points) < 2:
        grid.issues.append("Menos de 2 escoras: nenhum grid de VM gerado.")
        return grid

    primary_axis = primary_axis_override or _detect_primary_axis(shore_points, polygon_bbox)
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
        # Manual §28.7 fix (2026-05-31): forcar primaria ORTOGONAL ao eixo,
        # snap-ando a coordenada perpendicular para a media da row. Antes,
        # escoras de uma 'row' com Y ligeiramente diferentes (densificacao
        # de capitel, alinhamento adaptativo) produziam primarias diagonais.
        if primary_axis == "x":
            # Primaria corre em X -> Y fixo na media
            row_y_avg = sum(s.y for s in row) / len(row)
        else:
            # Primaria corre em Y -> X fixo na media
            row_x_avg = sum(s.x for s in row) / len(row)
        for s1, s2 in zip(row, row[1:]):
            if primary_axis == "x":
                start_pt = (s1.x, row_y_avg)
                end_pt = (s2.x, row_y_avg)
            else:
                start_pt = (row_x_avg, s1.y)
                end_pt = (row_x_avg, s2.y)
            span_m = math.hypot(end_pt[0] - start_pt[0], end_pt[1] - start_pt[1])
            L_mm = select_vm_length_mm(
                span_m, primaria_model, available_primaria_lengths_mm,
            )
            M, Madm, f, fadm, passM, passF = _compute_segment_load_and_moment(
                span_m, q_primaria_kn_m,
                primaria_moment_adm_kn_m, primaria_ei_kn_m2,
            )
            # Pendencia 17: cortante. Cada peca de VM primaria apoia-se
            # bi-apoiada entre duas escoras adjacentes (V = qL/2).
            V, Vadm, passV = check_shear(
                span_m, q_primaria_kn_m, primaria_shear_adm_kn,
                continuous=False,
            )
            seg = VMSegment(
                role="primaria",
                model=primaria_model,
                length_mm=L_mm,
                start=start_pt,
                end=end_pt,
                axis=primary_axis,
                load_kn_m=round(q_primaria_kn_m, 2),
                span_m=round(span_m, 3),
                moment_kn_m=round(M, 3),
                moment_adm_kn_m=Madm,
                flecha_mm=round(f, 2),
                flecha_adm_mm=round(fadm, 2),
                passes_moment=passM,
                passes_deflection=passF,
                shear_kn=round(V, 3),
                shear_adm_kn=Vadm,
                passes_shear=passV,
            )
            grid.add_segment(seg)
            if not passM:
                grid.issues.append(
                    f"VM primaria ({start_pt[0]:.2f},{start_pt[1]:.2f})->({end_pt[0]:.2f},{end_pt[1]:.2f}): "
                    f"momento {M:.2f} > {Madm:.2f} kN.m"
                )
            if not passF:
                grid.issues.append(
                    f"VM primaria ({start_pt[0]:.2f},{start_pt[1]:.2f})->({end_pt[0]:.2f},{end_pt[1]:.2f}): "
                    f"flecha {f:.1f}mm > {fadm:.1f}mm"
                )
            if not passV:
                grid.issues.append(
                    f"VM primaria ({start_pt[0]:.2f},{start_pt[1]:.2f})->({end_pt[0]:.2f},{end_pt[1]:.2f}): "
                    f"cortante {V:.2f} > {Vadm:.2f} kN"
                )

    # Limites do painel (usados pelas extensoes de primaria e secundarias)
    if polygon_bbox is not None:
        min_x, min_y, max_x, max_y = polygon_bbox
    else:
        xs = [s.x for s in shore_points]
        ys = [s.y for s in shore_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

    # 1b) EXTENSAO das primarias ate as bordas do painel (inspecao visual
    # 2026-06-12): a guia deve estender ate a viga de concreto que delimita
    # a laje — nao pode morrer na ultima escora. O trecho alem da ultima
    # escora trabalha em BALANCO (M = qL^2/2; flecha = qL^4/8EI).
    _EXT_MIN_M = 0.05  # extensoes menores que 5 cm sao irrelevantes
    if primary_axis == "x":
        axis_lo, axis_hi = min_x, max_x
    else:
        axis_lo, axis_hi = min_y, max_y

    for row in rows:
        if len(row) < 2:
            continue
        if primary_axis == "x":
            perp = sum(s.y for s in row) / len(row)
            first_c, last_c = row[0].x, row[-1].x
        else:
            perp = sum(s.x for s in row) / len(row)
            first_c, last_c = row[0].y, row[-1].y
        for ext_lo, ext_hi in ((axis_lo, first_c), (last_c, axis_hi)):
            ext_len = ext_hi - ext_lo
            if ext_len < _EXT_MIN_M:
                continue
            if primary_axis == "x":
                start_pt, end_pt = (ext_lo, perp), (ext_hi, perp)
            else:
                start_pt, end_pt = (perp, ext_lo), (perp, ext_hi)
            # Balanco: M = qL^2/2 ; flecha = qL^4/(8EI)
            M_ext = q_primaria_kn_m * ext_len * ext_len / 2.0
            if primaria_ei_kn_m2 > 0:
                f_ext_mm = (q_primaria_kn_m * ext_len ** 4
                            / (8.0 * primaria_ei_kn_m2)) * 1000.0
            else:
                f_ext_mm = 0.0
            fadm_ext = 1.0 + ext_len * 1000.0 / 500.0
            passM_ext = (primaria_moment_adm_kn_m <= 0
                         or M_ext <= primaria_moment_adm_kn_m)
            passF_ext = f_ext_mm <= fadm_ext
            grid.add_segment(VMSegment(
                role="primaria",
                model=primaria_model,
                length_mm=select_vm_length_mm(
                    ext_len, primaria_model, available_primaria_lengths_mm,
                ),
                start=start_pt,
                end=end_pt,
                axis=primary_axis,
                load_kn_m=round(q_primaria_kn_m, 2),
                span_m=round(ext_len, 3),
                moment_kn_m=round(M_ext, 3),
                moment_adm_kn_m=primaria_moment_adm_kn_m,
                flecha_mm=round(f_ext_mm, 2),
                flecha_adm_mm=round(fadm_ext, 2),
                passes_moment=passM_ext,
                passes_deflection=passF_ext,
                notes="extensao da guia ate a borda do painel (balanco)",
            ))
            if not passM_ext:
                grid.issues.append(
                    f"VM primaria em balanco ate a borda "
                    f"({start_pt[0]:.2f},{start_pt[1]:.2f}): momento "
                    f"{M_ext:.2f} > {primaria_moment_adm_kn_m:.2f} kN.m — "
                    f"adicionar escora junto a borda"
                )

    # 2) Vigas SECUNDARIAS (barrotes): perpendiculares as primarias, com
    # espacamento = seam_multiple_mm do compensado. Cobrem o bbox da laje.

    seam_m = seam_mm / 1000.0
    secondary_step_m = secondary_spacing_m if secondary_spacing_m and secondary_spacing_m > 0 else seam_m
    span_secundaria_m = avg_row_spacing  # apoia em duas primarias adjacentes
    q_secundaria_kn_m = load_kn_m2 * secondary_step_m

    # Eixo de DISTRIBUICAO dos barrotes (perpendicular a eles):
    # secundarias em X distribuem-se em Y, e vice-versa.
    if secondary_axis == "x":
        dist_lo, dist_hi = min_y, max_y
        dist_origin = global_origin[1] if global_origin is not None else None
    else:
        dist_lo, dist_hi = min_x, max_x
        dist_origin = global_origin[0] if global_origin is not None else None

    if dist_origin is not None:
        positions = _snapped_positions(dist_lo, dist_hi, dist_origin, secondary_step_m)
    else:
        # Passo FIXO e uniforme (inspecao visual 2026-06-12): o passo nao
        # pode ser "esticado" para caber no painel (cada painel ficava com
        # um espacamento diferente -> grid irregular entre secoes). Barrote
        # na borda inicial, passo constante e barrote final na borda; o
        # ULTIMO vao pode ser menor (pratica real de obra).
        positions = []
        p = dist_lo
        while p < dist_hi - 1e-6:
            positions.append(p)
            p += secondary_step_m
        positions.append(dist_hi)

    # Pendencia 18 (manual §11.2 / Orguel p.115): +1 barrote POR LINHA DE
    # EMENDA de compensado (transpasse lado a lado). As chapas assentam a
    # partir da borda do painel; emendas em multiplos do COMPRIMENTO da
    # chapa. O barrote extra existe MESMO quando a emenda coincide com um
    # barrote do grid regular.
    seam_coords = seam_positions(dist_lo, dist_hi, plywood.length_mm / 1000.0)
    grid.seam_lines = list(seam_coords)

    # Verificacoes identicas para todos os barrotes (mesmo vao/carga):
    L_mm = select_vm_length_mm(
        span_secundaria_m, secundaria_model, available_secundaria_lengths_mm,
    )
    M, Madm, f, fadm, passM, passF = _compute_segment_load_and_moment(
        span_secundaria_m, q_secundaria_kn_m,
        secundaria_moment_adm_kn_m, secundaria_ei_kn_m2,
    )
    # Pendencia 17: barrote corre continuo sobre as primarias; com >= 3
    # apoios usar o caso mais desfavoravel (V = 0.625qL, NBR Anexo B).
    secundaria_continuous = len(rows) >= 3
    V, Vadm, passV = check_shear(
        span_secundaria_m, q_secundaria_kn_m, secundaria_shear_adm_kn,
        continuous=secundaria_continuous,
    )
    base_note = (
        f"barrote (compensado {plywood.format_label()}, "
        f"passo {int(round(secondary_step_m * 1000))}mm)"
    )
    seam_note = "barrote extra de emenda (transpasse, Orguel p.115; manual §11.2)"

    all_positions = [(c, base_note) for c in positions]
    all_positions += [(c, seam_note) for c in seam_coords]
    for coord, note in all_positions:
        if secondary_axis == "x":
            start_pt, end_pt = (min_x, coord), (max_x, coord)
        else:
            start_pt, end_pt = (coord, min_y), (coord, max_y)
        seg = VMSegment(
            role="secundaria",
            model=secundaria_model,
            length_mm=L_mm,
            start=start_pt,
            end=end_pt,
            axis=secondary_axis,
            load_kn_m=round(q_secundaria_kn_m, 2),
            span_m=round(span_secundaria_m, 3),
            moment_kn_m=round(M, 3),
            moment_adm_kn_m=Madm,
            flecha_mm=round(f, 2),
            flecha_adm_mm=round(fadm, 2),
            passes_moment=passM,
            passes_deflection=passF,
            shear_kn=round(V, 3),
            shear_adm_kn=Vadm,
            passes_shear=passV,
            notes=note,
        )
        grid.add_segment(seg)
    if not passV:
        grid.issues.append(
            f"VM secundaria ({secundaria_model}) vao {span_secundaria_m:.2f}m: "
            f"cortante {V:.2f} > {Vadm:.2f} kN"
        )

    return grid


def vm_grid_bom_summary(grid: VMGrid) -> List[Tuple[str, int, int]]:
    """Resumo do BOM em lista [(model, length_mm, qty), ...]."""
    out: List[Tuple[str, int, int]] = []
    for model, lengths in grid.bom.items():
        for L_mm, qty in sorted(lengths.items()):
            out.append((model, L_mm, qty))
    return out
