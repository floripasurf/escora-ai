"""Testes do gerador line-first (manual §28.8 / orguel_gold_standard.md).

Casos exigidos pelo plano:
1. Painel retangular 8x5 m, laje 12 cm: pitch e passo nas faixas do gold
   standard, gap nas bordas (0 < gap <= 0.40) e escoras nas pontas da linha.
2. Linha longa > 4.10 m: emenda por transpasse + escoras extras em cada
   ponta do transpasse (pares ~0.70 m).
3. BOM com tripes = 30% das escoras (arredondado para cima).
4. Direcao por painel: 10x3 vs 3x10 dao direcoes perpendiculares.
"""
import math

import pytest
from shapely.geometry import Polygon

from src.engine.line_first_builder import (
    EDGE_GAP_MAX_M,
    PITCH_RANGE_M,
    SPLICE_OVERLAP_RANGE_M,
    STEP_RANGE_M,
    build_line_first_layout,
    layout_to_vm_grid,
    panel_guide_angle_deg,
)

# Laje 12 cm majorada: 1.4 x (25*0.12 + 0.5 + 2.0) = 7.7 kN/m2
Q_LAJE_12CM = 7.7
# ESC310 a ~2.6 m de abertura (capacidade derateada tipica)
CAP_ESC310 = 20.0


def _rect(w: float, h: float) -> Polygon:
    return Polygon([(0, 0), (w, 0), (w, h), (0, h)])


@pytest.fixture(scope="module")
def layout_8x5():
    return build_line_first_layout(_rect(8.0, 5.0), Q_LAJE_12CM, CAP_ESC310)


class TestPainel8x5Laje12:
    """Caso 1: painel 8x5 m, laje 12 cm, guia VM130."""

    def test_pitch_na_faixa_gold_standard(self, layout_8x5):
        # pitch = vao_perpendicular/n dentro de 1.10-1.80 (5/4 = 1.25)
        assert PITCH_RANGE_M[0] <= layout_8x5.pitch_m <= PITCH_RANGE_M[1]

    def test_passo_na_faixa_alvo(self, layout_8x5):
        # passo ao longo da guia na moda 1.20-1.55
        assert STEP_RANGE_M[0] <= layout_8x5.step_m <= STEP_RANGE_M[1]
        for line in layout_8x5.lines:
            assert STEP_RANGE_M[0] - 1e-6 <= line.step_m <= STEP_RANGE_M[1] + 1e-6

    def test_area_influencia_respeita_capacidade(self, layout_8x5):
        # pitch x passo <= capacidade derateada / q
        area = layout_8x5.pitch_m * layout_8x5.step_m
        assert area * Q_LAJE_12CM <= CAP_ESC310 + 1e-6

    def test_guias_correm_no_vao_maior(self, layout_8x5):
        # 8x5: guias horizontais (perpendiculares ao vao menor de 5 m)
        assert layout_8x5.angle_deg == pytest.approx(0.0)
        for line in layout_8x5.lines:
            assert line.start[1] == pytest.approx(line.end[1], abs=1e-6)

    def test_gap_nas_bordas(self, layout_8x5):
        # A guia corta com gap 0 < gap <= 0.40 m da borda do painel
        for line in layout_8x5.lines:
            x_lo = min(line.start[0], line.end[0])
            x_hi = max(line.start[0], line.end[0])
            assert 0.0 < x_lo <= EDGE_GAP_MAX_M
            assert 0.0 < 8.0 - x_hi <= EDGE_GAP_MAX_M

    def test_escora_nas_pontas_da_linha(self, layout_8x5):
        for line in layout_8x5.lines:
            xs = sorted(p[0] for p in line.shore_positions)
            x_lo = min(line.start[0], line.end[0])
            x_hi = max(line.start[0], line.end[0])
            assert xs[0] == pytest.approx(x_lo, abs=0.01)
            assert xs[-1] == pytest.approx(x_hi, abs=0.01)

    def test_numero_de_linhas(self, layout_8x5):
        # vao 5 m / pitch <= 1.55 -> 4 linhas
        assert len(layout_8x5.lines) == 4

    def test_vm_grid_so_primarias_e_passa(self, layout_8x5):
        grid = layout_to_vm_grid(layout_8x5, Q_LAJE_12CM)
        assert grid.segments, "grid sem segmentos"
        for seg in grid.segments:
            assert seg.role == "primaria"
            assert seg.model == "VM130"
            assert seg.passes_moment and seg.passes_deflection
        assert not grid.secundarias()  # barrote de madeira nao se desenha


class TestEmendaTranspasse:
    """Caso 2: linha > 4.10 m exige emenda por transpasse + escoras extras."""

    @pytest.fixture(scope="class")
    def layout(self):
        # run = 8 - 2x0.30 = 7.4 m > 4.10 -> 2 pecas por linha
        return build_line_first_layout(_rect(8.0, 5.0), Q_LAJE_12CM, CAP_ESC310)

    def test_linha_longa_tem_mais_de_uma_peca(self, layout):
        for line in layout.lines:
            assert len(line.pieces) >= 2
            assert len(line.splices) == len(line.pieces) - 1

    def test_transpasse_na_faixa(self, layout):
        # Sobreposicao entre pecas consecutivas dentro de 0.45-0.70 m
        for line in layout.lines:
            pieces = sorted(line.pieces, key=lambda p: min(p.start[0], p.end[0]))
            for p1, p2 in zip(pieces, pieces[1:]):
                overlap = max(p1.start[0], p1.end[0]) - min(p2.start[0], p2.end[0])
                assert SPLICE_OVERLAP_RANGE_M[0] - 1e-6 <= overlap <= SPLICE_OVERLAP_RANGE_M[1] + 1e-6

    def test_escora_extra_em_cada_ponta_do_transpasse(self, layout):
        # Em cada emenda ha escora a <=0.15 m de CADA ponta do transpasse
        for line in layout.lines:
            xs = sorted(p[0] for p in line.shore_positions)
            pieces = sorted(line.pieces, key=lambda p: min(p.start[0], p.end[0]))
            for p1, p2 in zip(pieces, pieces[1:]):
                lap_lo = min(p2.start[0], p2.end[0])
                lap_hi = max(p1.start[0], p1.end[0])
                assert any(abs(x - lap_lo) <= 0.15 for x in xs), (
                    f"sem escora na ponta inicial do transpasse ({lap_lo:.2f})"
                )
                assert any(abs(x - lap_hi) <= 0.15 for x in xs), (
                    f"sem escora na ponta final do transpasse ({lap_hi:.2f})"
                )
                # pares a ~0.70 m (largura do transpasse)
                assert lap_hi - lap_lo <= 0.75

    def test_transpasse_reflete_no_bom(self, layout):
        # 4 linhas x 2 pecas de VM130-4100 = 8 guias no BOM
        vm130 = layout.bom.guides.get("VM130", {})
        assert sum(vm130.values()) == sum(len(l.pieces) for l in layout.lines)
        assert vm130.get(4100, 0) >= len(layout.lines)  # >=1 peca 4.10 por linha

    def test_linha_curta_nao_emenda(self):
        # run = 4.0 - 0.6 = 3.4 m <= 4.10 -> 1 peca, sem transpasse
        layout = build_line_first_layout(_rect(4.0, 3.0), Q_LAJE_12CM, CAP_ESC310)
        for line in layout.lines:
            assert len(line.pieces) == 1
            assert line.splices == []


class TestBOMTripes:
    """Caso 3: BOM com tripes = 30% das escoras (arredondado para cima)."""

    def test_tripes_30_pct(self):
        layout = build_line_first_layout(_rect(8.0, 5.0), Q_LAJE_12CM, CAP_ESC310)
        n = layout.bom.shore_count
        assert n == len(layout.shores) > 0
        assert layout.bom.tripod_count == math.ceil(0.30 * n)

    def test_tripes_arredonda_para_cima(self):
        layout = build_line_first_layout(_rect(2.0, 1.2), Q_LAJE_12CM, CAP_ESC310)
        n = layout.bom.shore_count
        if n:
            assert layout.bom.tripod_count == math.ceil(0.30 * n)
            assert layout.bom.tripod_count >= 1


def _base_xs(line):
    """Posicoes ao longo da linha EXCLUINDO extras (transpasse/capitel)."""
    extras = {
        (round(p[0], 6), round(p[1], 6))
        for p in line.splice_shore_positions + line.capitel_shore_positions
    }
    return sorted(
        p[0] for p in line.shore_positions
        if (round(p[0], 6), round(p[1], 6)) not in extras
    )


class TestPassoUniformePorPainel:
    """Defeito 2: passo CONSTANTE por linha e UNICO por painel.

    n = ceil(L_util/passo_alvo); passo_real = L_util/n calculado UMA vez
    por painel; escoras em i*passo_real a partir da ponta. Excecao: extras
    de transpasse (pares ~0.65-0.70 m) e capitel ficam fora do ritmo.
    """

    def test_passo_constante_dentro_de_cada_linha(self, layout_8x5):
        for line in layout_8x5.lines:
            xs = _base_xs(line)
            steps = [b - a for a, b in zip(xs, xs[1:])]
            assert steps, "linha sem passos"
            assert max(steps) - min(steps) < 1e-6, (
                f"passo nao-uniforme na linha: {steps}"
            )

    def test_passo_real_unico_por_painel(self, layout_8x5):
        # Todas as linhas paralelas usam o MESMO passo_real do painel
        for line in layout_8x5.lines:
            assert line.step_m == pytest.approx(layout_8x5.step_m, abs=1e-3)

    def test_escoras_em_i_vezes_passo_da_ponta(self, layout_8x5):
        for line in layout_8x5.lines:
            xs = _base_xs(line)
            x_lo = min(line.start[0], line.end[0])
            step = xs[1] - xs[0]
            for i, x in enumerate(xs):
                assert x == pytest.approx(x_lo + i * step, abs=1e-6)

    def test_linhas_adjacentes_alinhadas_em_colunas(self, layout_8x5):
        # Painel 8x5: escoras de linhas vizinhas nas MESMAS coordenadas
        # ao longo do eixo da linha (colunas alinhadas).
        ref = _base_xs(layout_8x5.lines[0])
        for line in layout_8x5.lines[1:]:
            xs = _base_xs(line)
            assert len(xs) == len(ref)
            for a, b in zip(ref, xs):
                assert a == pytest.approx(b, abs=1e-6)


class TestCapitelSobreALinha:
    """Defeito 1: adensamento de capitel SOBRE as linhas (nunca avulso)."""

    @pytest.fixture(scope="class")
    def layout(self):
        # Pilar no centro do painel 8x5: anel de capitel 0.70-1.50 m
        return build_line_first_layout(
            _rect(8.0, 5.0), Q_LAJE_12CM, CAP_ESC310,
            capitel_centers=[(4.0, 2.5)],
        )

    def test_capitel_gera_escoras_extras(self, layout):
        extras = [p for ln in layout.lines for p in ln.capitel_shore_positions]
        assert extras, "nenhum adensamento de capitel gerado"

    def test_escoras_de_capitel_ficam_na_linha(self, layout):
        for line in layout.lines:
            y = line.start[1]
            for x_c, y_c in line.capitel_shore_positions:
                assert y_c == pytest.approx(y, abs=1e-6)
                x_lo = min(line.start[0], line.end[0])
                x_hi = max(line.start[0], line.end[0])
                assert x_lo - 1e-6 <= x_c <= x_hi + 1e-6

    def test_capitel_no_anel_do_pilar(self, layout):
        for line in layout.lines:
            for x_c, y_c in line.capitel_shore_positions:
                d = math.hypot(x_c - 4.0, y_c - 2.5)
                assert 0.70 - 1e-6 <= d <= 1.50 + 1e-6

    def test_toda_escora_a_menos_de_10cm_de_uma_linha(self, layout):
        # Invariante line-first: escora de laje SEMPRE sobre uma linha
        for x, y in layout.shores:
            d = min(
                _dist_point_segment(x, y, ln.start, ln.end)
                for ln in layout.lines
            )
            assert d <= 0.10, f"escora orfa ({x}, {y}) a {d:.3f} m da linha"

    def test_ritmo_base_preservado_com_capitel(self, layout):
        # Os extras de capitel nao alteram o passo das escoras base
        for line in layout.lines:
            xs = _base_xs(line)
            steps = [b - a for a, b in zip(xs, xs[1:])]
            assert max(steps) - min(steps) < 1e-6


def _dist_point_segment(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class TestDirecaoPorPainel:
    """Caso 4: 10x3 vs 3x10 dao direcoes perpendiculares."""

    def test_angulos_perpendiculares(self):
        a_wide = panel_guide_angle_deg(_rect(10.0, 3.0))
        a_tall = panel_guide_angle_deg(_rect(3.0, 10.0))
        assert a_wide == pytest.approx(0.0)
        assert a_tall == pytest.approx(90.0)
        assert abs(a_wide - a_tall) == pytest.approx(90.0)

    def test_linhas_geometricamente_perpendiculares(self):
        lw = build_line_first_layout(_rect(10.0, 3.0), Q_LAJE_12CM, CAP_ESC310)
        lt = build_line_first_layout(_rect(3.0, 10.0), Q_LAJE_12CM, CAP_ESC310)
        # 10x3: linhas horizontais (y constante); 3x10: verticais (x constante)
        for line in lw.lines:
            assert line.start[1] == pytest.approx(line.end[1], abs=1e-6)
        for line in lt.lines:
            assert line.start[0] == pytest.approx(line.end[0], abs=1e-6)
        # pitch identico nos dois (mesma geometria rotacionada)
        assert lw.pitch_m == pytest.approx(lt.pitch_m, abs=0.01)

    def test_painel_obliquo_segue_aresta_dominante(self):
        # Retangulo 10x3 rotacionado 30 graus: guia acompanha a aresta longa
        from shapely import affinity
        poly = affinity.rotate(_rect(10.0, 3.0), 30.0, origin=(0, 0))
        ang = panel_guide_angle_deg(poly)
        assert ang == pytest.approx(30.0, abs=3.0)
        layout = build_line_first_layout(poly, Q_LAJE_12CM, CAP_ESC310)
        assert layout.lines, "painel obliquo sem linhas"
        line = layout.lines[0]
        dx = line.end[0] - line.start[0]
        dy = line.end[1] - line.start[1]
        line_ang = math.degrees(math.atan2(dy, dx)) % 180.0
        assert line_ang == pytest.approx(30.0, abs=3.0)
