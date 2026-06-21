"""Gerador line-first de escoramento de lajes (padrao gold-standard Orguel).

Fonte: docs/research/orguel_gold_standard.md (11 projetos executivos Orguel,
2026-06-12) + manual §28.8. A laje NAO e um grid xadrez de pontos de escora:
e um sistema de LINHAS de guia metalica (VM80/VM130/ALU14) sobre forcados,
com escoras AO LONGO de cada linha. Os barrotes de madeira por cima sao do
cliente (nota 15 Orguel) e NAO sao desenhados nem quantificados.

Regras implementadas: direcao da guia POR PAINEL (perpendicular ao vao
menor; em paineis nao-ortogonais segue a aresta/viga dominante); pitch
entre linhas = vao/n alvo 1.10-1.80 m (moda 1.20-1.55) verificado por
capacidade (pitch x passo <= cap derateada / q); passo de escora alvo
1.20-1.55 m verificado pela capacidade E pelo vao admissivel da guia
(M = qL^2/8; flecha 5qL^4/384EI <= 1 + L/500 — formulas de vm_checks);
gap de 0-0.40 m nas extremidades (default 0.30) com escora na ponta;
emendas por TRANSPASSE de 0.45-0.70 m (default 0.65) com escora extra em
cada ponta; BOM com guias por modelo+comprimento, escoras e tripes = 30%
das escoras arredondado para cima (nota 17 Orguel).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from shapely import affinity
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from src.engine.vm_checks import compute_segment_load_and_moment
from src.engine.vm_grid_builder import (
    DEFAULT_VM_LENGTHS_MM,
    VMGrid,
    VMSegment,
)

# ---------------------------------------------------------------------------
# Constantes do gold standard (orguel_gold_standard.md, sintese 11 projetos)
# ---------------------------------------------------------------------------

# Gap guia -> borda do painel. Gold standard Orguel: 0-0.40 m (moda 0.30).
# DECISAO DO REVISOR (2026-06-12, v10): a guia deve CHEGAR ate a face da
# viga -> default 0.05 m; o alinhamento atravessa vigas internas via
# conectores (stage_calculate._merge_collinear_line_first_guides).
EDGE_GAP_DEFAULT_M = 0.05
EDGE_GAP_MAX_M = 0.40            # faixa observada: 0 a +0.40, nunca atravessar
SPLICE_OVERLAP_DEFAULT_M = 0.65  # transpasse modal de emenda
SPLICE_OVERLAP_RANGE_M = (0.45, 0.70)
PITCH_RANGE_M = (1.10, 1.80)     # pitch entre linhas de guia (vao/n)
PITCH_TARGET_MAX_M = 1.55        # moda 1.20-1.55
STEP_RANGE_M = (1.20, 1.55)      # passo de escora ao longo da guia (moda)
TRIPOD_RATIO = 0.30              # tripes = 30% das escoras (nota 17)
MIN_RUN_M = 0.50                 # runs menores que isto sao descartados
SPLICE_SHORE_TOL_M = 0.12        # dedupe escora extra vs escora do passo
_PITCH_FLOOR_M = 0.60            # piso de seguranca para o pitch
# Capitel (Orguel Q6 / capitel_densification): anel 0.70-1.50 m ao redor do
# pilar com escoras adensadas. No modo line-first o adensamento acontece
# SOBRE as linhas (midpoint do passo dentro do anel), nunca em ponto avulso.
CAPITEL_INNER_RADIUS_M = 0.70
CAPITEL_OUTER_RADIUS_M = 1.50

# Sistema ALU14 + VM80 para lajes NERVURADAS (gold standard §9/§10,
# projetos 110749/101112): primarias ALU14 na lattice do pavimento +
# secundarias VM80 com passo FIXO por tipo de laje (texto de calibracao
# do 110749: "PARA LAJE NERVURADA: VM 80 C/60 cm" / "PARA LAJE MACICA:
# VM 80 C/36.7 cm"). O passo e ancorado na lattice GLOBAL do pavimento
# (u_anchor + k*step) — NUNCA esticado por painel — para que paineis
# vizinhos saiam equidistantes e alinhados.
SECONDARY_STEP_RIBBED_M = 0.60
SECONDARY_STEP_SOLID_THICK_M = 0.367
MIN_SECONDARY_LEN_M = 0.30

# Propriedades dos modelos de guia (manual §13.3, kgf -> kN x0.00980665):
# model -> (M_adm kN.m, EI kN.m2, comprimentos mm)
GUIDE_SPECS: Dict[str, Tuple[float, float, List[int]]] = {
    "VM80": (2.08, 146.8, list(DEFAULT_VM_LENGTHS_MM["VM80"])),
    "VM130": (5.06, 461.8, list(DEFAULT_VM_LENGTHS_MM["VM130"])),
    "ALU14": (4.01, 199.2, [1500, 2000, 2500, 3000, 3500, 4000, 6000]),
}


# ---------------------------------------------------------------------------
# Dataclasses de saida
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GuidePiece:
    """Peca fisica de guia selecionada do catalogo (pode transpassar)."""
    model: str
    length_mm: int
    start: Tuple[float, float]
    end: Tuple[float, float]
    spliced: bool = False  # True quando participa de emenda por transpasse


@dataclass
class GuideLine:
    """Uma linha de guia: run continuo com escoras ao longo."""
    angle_deg: float
    start: Tuple[float, float]
    end: Tuple[float, float]
    pitch_m: float                       # faixa de influencia (entre linhas)
    step_m: float                        # passo de escora ao longo da linha
    pieces: List[GuidePiece] = field(default_factory=list)
    shore_positions: List[Tuple[float, float]] = field(default_factory=list)
    splices: List[Tuple[float, float]] = field(default_factory=list)
    edge_gap_m: float = EDGE_GAP_DEFAULT_M
    # Escoras FORA do ritmo do passo (mas SOBRE a linha): pares de
    # transpasse e adensamento de capitel. Subconjuntos de shore_positions,
    # usados para excluir do audit de passo uniforme.
    splice_shore_positions: List[Tuple[float, float]] = field(default_factory=list)
    capitel_shore_positions: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class LineFirstBOM:
    """BOM do layout line-first."""
    guides: Dict[str, Dict[int, int]] = field(default_factory=dict)
    shore_count: int = 0
    tripod_count: int = 0


@dataclass
class LineFirstLayout:
    """Resultado completo do gerador line-first para um painel."""
    guide_model: str = "VM130"
    angle_deg: float = 0.0
    pitch_m: float = 0.0
    step_m: float = 0.0
    lines: List[GuideLine] = field(default_factory=list)
    shores: List[Tuple[float, float]] = field(default_factory=list)
    bom: LineFirstBOM = field(default_factory=LineFirstBOM)
    issues: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Direcao por painel
# ---------------------------------------------------------------------------

def _axis_aligned_ratio(polygon: Polygon, tol_deg: float = 3.0) -> float:
    """Fracao do perimetro alinhada aos eixos (H/V)."""
    try:
        coords = list(polygon.exterior.coords)
    except Exception:
        return 1.0
    total = axis = 0.0
    for a, b in zip(coords, coords[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        if ln <= 1e-9:
            continue
        total += ln
        ang = abs(math.degrees(math.atan2(dy, dx))) % 180.0
        if min(ang, abs(ang - 90.0), abs(ang - 180.0)) <= tol_deg:
            axis += ln
    return axis / total if total > 0 else 1.0


def _dominant_edge_angle_deg(polygon: Polygon) -> float:
    """Angulo (mod 180) da aresta/viga dominante: maior soma de comprimento."""
    try:
        coords = list(polygon.exterior.coords)
    except Exception:
        return 0.0
    buckets: Dict[int, float] = {}
    for a, b in zip(coords, coords[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        if ln <= 1e-9:
            continue
        ang = math.degrees(math.atan2(dy, dx)) % 180.0
        buckets[int(round(ang / 5.0)) % 36] = (
            buckets.get(int(round(ang / 5.0)) % 36, 0.0) + ln
        )
    if not buckets:
        return 0.0
    return (max(buckets, key=buckets.get) * 5.0) % 180.0


def panel_guide_angle_deg(polygon: Polygon) -> float:
    """Direcao da guia POR PAINEL (gold standard, regra 7 + nova regra 7).

    - Painel ortogonal: perpendicular ao vao menor = ao longo do lado maior
      do bbox (0 graus se largo em X, 90 se alto em Y).
    - Painel nao-ortogonal: segue o angulo da aresta/viga dominante,
      escolhendo entre dominante e dominante+90 o que da o MAIOR alcance
      (guias ao longo do lado maior do bbox rotacionado).
    """
    min_x, min_y, max_x, max_y = polygon.bounds
    if _axis_aligned_ratio(polygon) >= 0.60:
        return 0.0 if (max_x - min_x) >= (max_y - min_y) else 90.0
    ang = _dominant_edge_angle_deg(polygon)
    rot = affinity.rotate(polygon, -ang, origin=(0, 0))
    rx0, ry0, rx1, ry1 = rot.bounds
    return ang if (rx1 - rx0) >= (ry1 - ry0) else (ang + 90.0) % 180.0


# ---------------------------------------------------------------------------
# Verificacoes (reutilizam vm_checks)
# ---------------------------------------------------------------------------

def _max_guide_span_m(
    q_line_kn_m: float,
    moment_adm_kn_m: float,
    ei_kn_m2: float,
    hi: float = 4.5,
) -> float:
    """Maior vao da guia que passa momento (M=qL^2/8) E flecha (1+L/500)."""
    if q_line_kn_m <= 0:
        return hi
    lo, hi_b = 0.10, hi
    for _ in range(48):
        mid = (lo + hi_b) / 2.0
        _, _, _, _, pm, pf = compute_segment_load_and_moment(
            mid, q_line_kn_m, moment_adm_kn_m, ei_kn_m2,
        )
        if pm and pf:
            lo = mid
        else:
            hi_b = mid
    return lo


def _select_piece_mm(length_m: float, lengths_mm: Sequence[int]) -> int:
    """Menor peca do catalogo >= comprimento; senao a maior."""
    target = int(math.ceil(length_m * 1000.0))
    fitting = [L for L in lengths_mm if L >= target]
    return min(fitting) if fitting else max(lengths_mm)


def _compose_pieces(
    run_len_m: float,
    lengths_mm: Sequence[int],
    overlap_m: float,
) -> Tuple[List[Tuple[float, float, int]], List[Tuple[float, float]]]:
    """Compoe o run com pecas do catalogo emendadas por transpasse.

    Retorna (pieces, splices):
    - pieces: lista (u_start, u_end, length_mm) relativa ao inicio do run;
    - splices: lista (u_lo, u_hi) das regioes de transpasse (largura ~overlap).
    """
    L_max = max(lengths_mm) / 1000.0
    if run_len_m <= L_max + 1e-9:
        return [(0.0, run_len_m, _select_piece_mm(run_len_m, lengths_mm))], []

    coverage = L_max - overlap_m
    k = max(2, int(math.ceil((run_len_m - L_max) / coverage)) + 1)
    pieces: List[Tuple[float, float, int]] = []
    splices: List[Tuple[float, float]] = []
    for j in range(k - 1):
        s = j * coverage
        pieces.append((s, min(s + L_max, run_len_m), int(max(lengths_mm))))
    s_last = (k - 1) * coverage
    needed = run_len_m - s_last
    pieces.append((s_last, run_len_m, _select_piece_mm(needed, lengths_mm)))
    for j in range(1, k):
        u_lo = j * coverage                       # inicio da peca j
        u_hi = (j - 1) * coverage + L_max         # fim da peca j-1
        splices.append((u_lo, min(u_hi, run_len_m)))
    return pieces, splices


# ---------------------------------------------------------------------------
# Builder principal
# ---------------------------------------------------------------------------

def build_line_first_layout(
    polygon: Polygon,
    load_kn_m2: float,
    shore_capacity_kn: float,
    *,
    guide_model: str = "VM130",
    available_lengths_mm: Optional[Sequence[int]] = None,
    edge_gap_m: float = EDGE_GAP_DEFAULT_M,
    splice_overlap_m: float = SPLICE_OVERLAP_DEFAULT_M,
    pitch_range_m: Tuple[float, float] = PITCH_RANGE_M,
    pitch_target_max_m: float = PITCH_TARGET_MAX_M,
    step_range_m: Tuple[float, float] = STEP_RANGE_M,
    exclusions: Optional[Sequence] = None,
    angle_override_deg: Optional[float] = None,
    capitel_centers: Optional[Sequence[Tuple[float, float]]] = None,
    pitch_override_m: Optional[float] = None,
    v_anchor: Optional[float] = None,
    tripod_ratio: float = TRIPOD_RATIO,
) -> LineFirstLayout:
    """Gera linhas de guia + escoras para um painel de laje (line-first).

    Args:
        polygon: poligono do painel (m).
        load_kn_m2: carga majorada por m2 (kN/m2).
        shore_capacity_kn: capacidade DERATEADA da escora na abertura real.
        guide_model: "VM80" | "VM130" | "ALU14" (manual §13.3).
        available_lengths_mm: catalogo de comprimentos; default por modelo.
        edge_gap_m: gap guia->borda (clampado a 0..0.40 m).
        splice_overlap_m: transpasse de emenda (clampado a 0.45..0.70 m).
        exclusions: objetos com min_x/min_y/max_x/max_y (pilares, shafts) a
            subtrair do painel antes de tracar as linhas.
        angle_override_deg: forca o angulo da guia (graus, mod 180).
        capitel_centers: centros (x, y) de pilares para adensamento de
            capitel SOBRE as linhas (anel 0.70-1.50 m, Orguel Q6): insere
            escora no midpoint de cada passo cujo centro caia no anel.
        tripod_ratio: fracao de tripes sobre o total de escoras (nota 17
            Orguel: 0.30; perfil §28.9 `tripes_fracao` pode sobrescrever).
    """
    layout = LineFirstLayout(guide_model=guide_model)
    if polygon is None or polygon.is_empty or polygon.area <= 0:
        layout.issues.append("Painel vazio: nenhum layout line-first gerado.")
        return layout
    if guide_model not in GUIDE_SPECS:
        layout.issues.append(
            f"Modelo de guia desconhecido '{guide_model}' — usando VM130."
        )
        guide_model = "VM130"
        layout.guide_model = guide_model
    m_adm, ei, default_lengths = GUIDE_SPECS[guide_model]
    lengths_mm = list(available_lengths_mm or default_lengths)
    gap = min(max(edge_gap_m, 0.0), EDGE_GAP_MAX_M)
    overlap = min(
        max(splice_overlap_m, SPLICE_OVERLAP_RANGE_M[0]),
        SPLICE_OVERLAP_RANGE_M[1],
    )

    # Painel util = poligono - exclusoes (pilares/shafts)
    clip = polygon.buffer(0)
    if exclusions:
        boxes = []
        for ex in exclusions:
            try:
                b = box(ex.min_x, ex.min_y, ex.max_x, ex.max_y)
                if b.intersects(clip):
                    boxes.append(b)
            except Exception:
                continue
        if boxes:
            try:
                clip = clip.difference(unary_union(boxes))
            except Exception:
                pass
    if clip.is_empty:
        layout.issues.append("Painel coberto por exclusoes — sem linhas.")
        return layout

    # Direcao por painel + frame local (guia ao longo do +X local)
    angle = (
        angle_override_deg % 180.0
        if angle_override_deg is not None
        else panel_guide_angle_deg(polygon)
    )
    layout.angle_deg = round(angle, 2)
    local = affinity.rotate(clip, -angle, origin=(0, 0))
    min_u, min_v, max_u, max_v = local.bounds
    span_perp = max_v - min_v
    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    def to_world(u: float, v: float) -> Tuple[float, float]:
        return (u * cos_a - v * sin_a, u * sin_a + v * cos_a)

    if span_perp <= 1e-6:
        layout.issues.append("Painel degenerado (vao perpendicular nulo).")
        return layout

    # Capacidade: area de influencia pitch x passo <= cap/q
    max_area_m2 = (
        shore_capacity_kn / load_kn_m2
        if load_kn_m2 > 0 and shore_capacity_kn > 0
        else float("inf")
    )
    if pitch_override_m is not None and pitch_override_m > 0:
        # Malha de PAVIMENTO (decisao do revisor 2026-06-12): pitch unico
        # para todos os paineis; com v_anchor, as posicoes das linhas sao
        # ancoradas numa lattice global -> linhas colineares atravessando
        # as vigas (alinhamento continuo entre paineis).
        pitch = pitch_override_m
        n_lines = max(1, int(math.ceil(span_perp / pitch)))
    else:
        # Pitch entre linhas = vao/n, alvo dentro de pitch_range (moda <=1.55)
        n_lines = max(1, int(math.ceil(span_perp / pitch_target_max_m)))
        pitch = span_perp / n_lines
        if pitch < pitch_range_m[0] and n_lines > 1:
            alt = span_perp / (n_lines - 1)
            if alt <= pitch_range_m[1] + 1e-9:
                n_lines -= 1
                pitch = alt
        while pitch > _PITCH_FLOOR_M and pitch * 0.30 > max_area_m2:
            n_lines += 1
            pitch = span_perp / n_lines
    layout.pitch_m = round(pitch, 3)

    # Passo de escora ao longo da linha: capacidade + vao admissivel da guia
    q_line = load_kn_m2 * pitch
    span_adm = _max_guide_span_m(q_line, m_adm, ei)
    step_cap = max_area_m2 / pitch if max_area_m2 != float("inf") else float("inf")
    step_allowed = min(span_adm, step_cap)
    target_step = min(step_range_m[1], step_allowed)
    if target_step < step_range_m[0]:
        layout.issues.append(
            f"Passo alvo reduzido para {target_step:.2f} m (capacidade da "
            f"escora / vao admissivel da guia {guide_model})."
        )
    target_step = max(target_step, 0.30)

    # Passo REAL calculado UMA vez por painel (nao por linha): linhas
    # paralelas usam o mesmo passo e as escoras ficam alinhadas em colunas.
    # n = ceil(L_util/passo_alvo); passo_real = L_util/n.
    panel_run_m = max(0.30, (max_u - min_u) - 2.0 * gap)
    n_panel_steps = max(1, int(math.ceil(panel_run_m / target_step - 1e-9)))
    panel_step = panel_run_m / n_panel_steps

    # Centros de capitel no frame local (u, v)
    local_capitels: List[Tuple[float, float]] = []
    for cx, cy in capitel_centers or []:
        local_capitels.append(
            (cx * cos_a + cy * sin_a, -cx * sin_a + cy * cos_a)
        )

    bom_guides: Dict[str, Dict[int, int]] = {}
    all_shores: List[Tuple[float, float]] = []
    steps_used: List[float] = []

    # Posicoes das linhas: por painel (centro dos pitches) ou ancoradas na
    # lattice global v_anchor + k*pitch (malha de pavimento — linhas
    # colineares entre paineis, atravessando as vigas em alinhamento).
    if v_anchor is not None and pitch > 0:
        k_lo = math.ceil((min_v + 0.10 - v_anchor) / pitch)
        k_hi = math.floor((max_v - 0.10 - v_anchor) / pitch)
        v_positions = [v_anchor + k * pitch for k in range(k_lo, k_hi + 1)]
        if not v_positions:
            v_positions = [(min_v + max_v) / 2.0]
    else:
        v_positions = [min_v + (i + 0.5) * pitch for i in range(n_lines)]

    for v in v_positions:
        scan = LineString([(min_u - 1.0, v), (max_u + 1.0, v)])
        try:
            inter = scan.intersection(local)
        except Exception:
            continue
        parts = (
            [inter] if inter.geom_type == "LineString"
            else list(getattr(inter, "geoms", []))
        )
        for part in parts:
            if part.geom_type != "LineString" or part.length < MIN_RUN_M:
                continue
            us = [c[0] for c in part.coords]
            u0, u1 = min(us), max(us)
            g = gap
            if (u1 - u0) - 2 * g < 0.30:
                g = max(0.0, ((u1 - u0) - 0.30) / 2.0)
            run_lo, run_hi = u0 + g, u1 - g
            run_len = run_hi - run_lo
            if run_len < 0.30:
                continue

            # Escoras a passo CONSTANTE na linha, com escora em CADA ponta.
            # n deriva do passo_real do PAINEL: no run cheio n == n_panel e
            # step == panel_step exato (colunas alinhadas entre linhas);
            # runs recortados (pilar) mantem passo constante <= panel_step.
            n_steps = max(1, int(math.ceil(run_len / panel_step - 1e-9)))
            step = run_len / n_steps
            shore_us = [run_lo + k * step for k in range(n_steps + 1)]

            # Pecas do catalogo + transpasses (escora extra em cada ponta)
            rel_pieces, rel_splices = _compose_pieces(run_len, lengths_mm, overlap)
            splice_us: List[float] = []
            for s_lo, s_hi in rel_splices:
                for u_extra in (run_lo + s_lo, run_lo + s_hi):
                    if all(
                        abs(u_extra - u) > SPLICE_SHORE_TOL_M for u in shore_us
                    ):
                        shore_us.append(u_extra)
                        splice_us.append(u_extra)
            shore_us.sort()

            # Adensamento de capitel SOBRE a linha (Orguel Q6): midpoint de
            # cada passo cujo centro caia no anel 0.70-1.50 m de um pilar.
            # Nunca ponto avulso fora da linha (manual §28.8).
            capitel_us: List[float] = []
            if local_capitels:
                for u_a, u_b in zip(shore_us, shore_us[1:]):
                    u_mid = (u_a + u_b) / 2.0
                    if (u_b - u_a) <= SPLICE_SHORE_TOL_M * 2:
                        continue
                    for cu, cv in local_capitels:
                        d = math.hypot(u_mid - cu, v - cv)
                        if CAPITEL_INNER_RADIUS_M <= d <= CAPITEL_OUTER_RADIUS_M:
                            capitel_us.append(u_mid)
                            break
                shore_us.extend(capitel_us)
                shore_us.sort()

            line = GuideLine(
                angle_deg=layout.angle_deg,
                start=to_world(run_lo, v),
                end=to_world(run_hi, v),
                pitch_m=round(pitch, 3),
                step_m=round(step, 3),
                edge_gap_m=round(g, 3),
            )
            spliced = bool(rel_splices)
            for p_lo, p_hi, L_mm in rel_pieces:
                line.pieces.append(GuidePiece(
                    model=guide_model,
                    length_mm=L_mm,
                    start=to_world(run_lo + p_lo, v),
                    end=to_world(run_lo + p_hi, v),
                    spliced=spliced,
                ))
                bom_guides.setdefault(guide_model, {}).setdefault(L_mm, 0)
                bom_guides[guide_model][L_mm] += 1
            line.splices = [
                to_world(run_lo + (s_lo + s_hi) / 2.0, v)
                for s_lo, s_hi in rel_splices
            ]
            line.shore_positions = [to_world(u, v) for u in shore_us]
            line.splice_shore_positions = [to_world(u, v) for u in splice_us]
            line.capitel_shore_positions = [to_world(u, v) for u in capitel_us]
            all_shores.extend(line.shore_positions)
            steps_used.append(step)
            layout.lines.append(line)

    if not layout.lines:
        layout.issues.append("Nenhuma linha de guia coube no painel.")
        return layout

    layout.step_m = round(panel_step, 3)
    layout.shores = [(round(x, 3), round(y, 3)) for x, y in all_shores]
    ratio = tripod_ratio if 0.0 <= tripod_ratio <= 1.0 else TRIPOD_RATIO
    layout.bom = LineFirstBOM(
        guides=bom_guides,
        shore_count=len(layout.shores),
        tripod_count=int(math.ceil(ratio * len(layout.shores))),
    )
    return layout


# ---------------------------------------------------------------------------
# Conversao para VMGrid (integracao com pipeline/verifiers/DXF)
# ---------------------------------------------------------------------------

def layout_to_vm_grid(layout: LineFirstLayout, load_kn_m2: float) -> VMGrid:
    """Converte o layout line-first em VMGrid (so primarias; sem secundarias).

    Gold standard nota 15: barrotes de madeira sao do cliente e nao se
    desenham. span_m de cada peca = PASSO entre escoras na linha (a peca
    apoia em multiplas escoras — nao confundir com o comprimento da peca).
    """
    axis = "x" if (layout.angle_deg % 180.0) < 45.0 or (layout.angle_deg % 180.0) > 135.0 else "y"
    grid = VMGrid(primaria_axis=axis)
    m_adm, ei, _ = GUIDE_SPECS.get(layout.guide_model, GUIDE_SPECS["VM130"])
    for line in layout.lines:
        q_line = load_kn_m2 * line.pitch_m
        M, Madm, f, fadm, passM, passF = compute_segment_load_and_moment(
            line.step_m, q_line, m_adm, ei,
        )
        note = (
            f"guia line-first (passo {line.step_m:.2f}m, "
            f"pitch {line.pitch_m:.2f}m, gap {line.edge_gap_m:.2f}m)"
        )
        for piece in line.pieces:
            grid.add_segment(VMSegment(
                role="primaria",
                model=piece.model,
                length_mm=piece.length_mm,
                start=piece.start,
                end=piece.end,
                axis=axis,
                load_kn_m=round(q_line, 2),
                span_m=round(line.step_m, 3),
                moment_kn_m=round(M, 3),
                moment_adm_kn_m=Madm,
                flecha_mm=round(f, 2),
                flecha_adm_mm=round(fadm, 2),
                passes_moment=passM,
                passes_deflection=passF,
                notes=(
                    note + "; emenda por transpasse"
                    if piece.spliced else note
                ),
            ))
        if not (passM and passF):
            grid.issues.append(
                f"Guia line-first {layout.guide_model} passo "
                f"{line.step_m:.2f}m: falha de momento/flecha — revisar."
            )
    grid.issues.extend(layout.issues)
    return grid


def append_fixed_step_secondaries(
    grid: VMGrid,
    layout: LineFirstLayout,
    polygon: Polygon,
    load_kn_m2: float,
    *,
    ribbed: bool = True,
    step_m: Optional[float] = None,
    u_anchor: Optional[float] = None,
    model: str = "VM80",
    exclusions: Optional[Sequence] = None,
) -> int:
    """Adiciona secundarias VM80 de passo FIXO ao grid (sistema ALU14+VM80).

    Gold standard (110749/101112): paineis NERVURADOS usam primarias ALU14
    na lattice do pavimento + secundarias VM80 perpendiculares com passo
    constante por TIPO de laje — c/0.60 m (nervurada) ou c/0.367 m (macica
    espessa). As posicoes sao ancoradas na lattice GLOBAL ``u_anchor +
    k*step`` (coordenada ao longo da direcao das guias), de modo que o
    passo nunca e esticado por painel e paineis vizinhos compartilham a
    mesma malha (equidistancia + alinhamento entre paineis).

    Args:
        grid: VMGrid ja contendo as primarias do layout line-first.
        layout: layout line-first do painel (angulo/pitch das primarias).
        polygon: poligono do painel (m).
        load_kn_m2: carga majorada por m2 (kN/m2).
        ribbed: True = nervurada (c/0.60); False = macica espessa (c/0.367).
        step_m: passo explicito (sobrepoe a escolha por tipo de laje).
        u_anchor: ancora GLOBAL da lattice na coordenada u (ao longo da
            guia). None = ancora no inicio do proprio painel.
        exclusions: objetos com min_x/min_y/max_x/max_y a subtrair.

    Returns:
        Numero de segmentos de secundaria adicionados.
    """
    if polygon is None or polygon.is_empty or polygon.area <= 0:
        return 0
    step = step_m if step_m and step_m > 0 else (
        SECONDARY_STEP_RIBBED_M if ribbed else SECONDARY_STEP_SOLID_THICK_M
    )
    angle = layout.angle_deg % 180.0
    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    clip = polygon.buffer(0)
    if exclusions:
        boxes = []
        for ex in exclusions:
            try:
                b = box(ex.min_x, ex.min_y, ex.max_x, ex.max_y)
                if b.intersects(clip):
                    boxes.append(b)
            except Exception:
                continue
        if boxes:
            try:
                clip = clip.difference(unary_union(boxes))
            except Exception:
                pass
    if clip.is_empty:
        return 0

    local = affinity.rotate(clip, -angle, origin=(0, 0))
    min_u, min_v, max_u, max_v = local.bounds

    def to_world(u: float, v: float) -> Tuple[float, float]:
        return (u * cos_a - v * sin_a, u * sin_a + v * cos_a)

    anchor = u_anchor if u_anchor is not None else min_u
    k_lo = math.ceil((min_u - anchor) / step - 1e-9)
    k_hi = math.floor((max_u - anchor) / step + 1e-9)
    if k_hi < k_lo:
        return 0

    # Vao da secundaria = pitch entre primarias (apoia de guia em guia);
    # carga linear = faixa de influencia do passo fixo.
    span_m = layout.pitch_m if layout.pitch_m > 0 else 1.50
    q_kn_m = load_kn_m2 * step
    m_adm, ei, _ = GUIDE_SPECS.get("VM80", (2.08, 146.8, []))
    M, Madm, f, fadm, passM, passF = compute_segment_load_and_moment(
        span_m, q_kn_m, m_adm, ei,
    )
    lengths_mm = list(DEFAULT_VM_LENGTHS_MM.get(model, [])) or [1000, 2050, 3100]
    axis = "y" if (angle < 45.0 or angle > 135.0) else "x"
    note = (
        f"secundaria {model} passo fixo c/{step * 100:.1f} cm "
        f"({'nervurada' if ribbed else 'macica espessa'} — sistema "
        f"ALU14+VM80, lattice global)"
    )

    added = 0
    for k in range(k_lo, k_hi + 1):
        u = anchor + k * step
        scan = LineString([(u, min_v - 1.0), (u, max_v + 1.0)])
        try:
            inter = scan.intersection(local)
        except Exception:
            continue
        parts = (
            [inter] if inter.geom_type == "LineString"
            else list(getattr(inter, "geoms", []))
        )
        for part in parts:
            if part.geom_type != "LineString" or part.length < MIN_SECONDARY_LEN_M:
                continue
            vs = [c[1] for c in part.coords]
            v0, v1 = min(vs), max(vs)
            grid.add_segment(VMSegment(
                role="secundaria",
                model=model,
                length_mm=_select_piece_mm(v1 - v0, lengths_mm),
                start=to_world(u, v0),
                end=to_world(u, v1),
                axis=axis,
                load_kn_m=round(q_kn_m, 2),
                span_m=round(span_m, 3),
                moment_kn_m=round(M, 3),
                moment_adm_kn_m=Madm,
                flecha_mm=round(f, 2),
                flecha_adm_mm=round(fadm, 2),
                passes_moment=passM,
                passes_deflection=passF,
                notes=note,
            ))
            added += 1
    if added and not (passM and passF):
        grid.issues.append(
            f"Secundaria {model} c/{step * 100:.1f} cm vao {span_m:.2f} m: "
            f"falha de momento/flecha — reduzir pitch das primarias."
        )
    return added
