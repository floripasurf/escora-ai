"""Testes do gerador de grid de VMs (manual §28).

Cenarios calibrados com:
- UTFPR TCC Bedenaroski 2021 Figura 28 (vigas H20-Eco longitudinais +
  secundarias densas)
- Manual Orguel §13.3 (catalogo de comprimentos)
- Manual §22.2-§22.5 (formulas de momento e flecha)
"""
from __future__ import annotations

import pytest

from src.engine.vm_grid_builder import (
    ShorePoint,
    VMGrid,
    VMSegment,
    build_vm_grid,
    select_vm_length_mm,
    vm_grid_bom_summary,
)
from src.models.plywood import PlywoodSpec


class TestSelectVMLength:
    def test_picks_smallest_fit(self):
        assert select_vm_length_mm(1.0, "VM130") == 1550
        assert select_vm_length_mm(2.0, "VM130") == 2050
        assert select_vm_length_mm(3.05, "VM130") == 3100

    def test_picks_largest_when_oversize(self):
        # Acima do maior catalogo
        assert select_vm_length_mm(5.0, "VM130") == 4100

    def test_vm80_smaller_options(self):
        assert select_vm_length_mm(0.8, "VM80") == 1000
        assert select_vm_length_mm(1.5, "VM80") == 1550

    def test_unknown_model_falls_back(self):
        # Modelo desconhecido sem catalog -> arredonda para 500mm
        assert select_vm_length_mm(1.3, "XYZ") == 1500

    def test_custom_catalog_overrides(self):
        # Locadora especifica seu proprio catalogo
        custom = [800, 1200, 1600, 2000]
        assert select_vm_length_mm(1.0, "VM130", custom) == 1200
        assert select_vm_length_mm(1.5, "VM130", custom) == 1600
        assert select_vm_length_mm(3.0, "VM130", custom) == 2000  # maior disponivel


class TestBuildVMGrid:
    def test_empty_shores_returns_empty_grid(self):
        grid = build_vm_grid([])
        assert len(grid.segments) == 0
        assert any("Menos de 2" in i for i in grid.issues)

    def test_simple_2x2m_panel_generates_both_axes(self):
        # 3x3 = 9 escoras em 2x2m
        shores = [ShorePoint(x=ix, y=iy) for ix in range(3) for iy in range(3)]
        grid = build_vm_grid(shores, polygon_bbox=(0, 0, 2, 2), load_kn_m2=7.7)
        assert len(grid.primarias()) > 0
        assert len(grid.secundarias()) > 0
        # Numero de primarias = N_rows × (N_shores_per_row - 1)
        # 3 rows × 2 segments = 6
        assert len(grid.primarias()) == 6

    def test_rectangular_panel_long_axis_orientation(self):
        # Painel 6x4m (largo em X) -> primarias devem correr em Y
        shores = [ShorePoint(x=ix, y=iy) for ix in range(7) for iy in range(5)]
        grid = build_vm_grid(shores, polygon_bbox=(0, 0, 6, 4), load_kn_m2=7.7)
        assert grid.primaria_axis == "y"

    def test_vertical_panel_primaria_in_x(self):
        # Painel 4x6m (alto em Y) -> primarias devem correr em X
        shores = [ShorePoint(x=ix, y=iy) for ix in range(5) for iy in range(7)]
        grid = build_vm_grid(shores, polygon_bbox=(0, 0, 4, 6), load_kn_m2=7.7)
        assert grid.primaria_axis == "x"

    def test_plywood_default_244mm_seam(self):
        # Compensado 1220 x 2440 -> passo 244mm
        shores = [ShorePoint(x=ix, y=iy) for ix in range(5) for iy in range(5)]
        grid = build_vm_grid(
            shores,
            polygon_bbox=(0, 0, 4, 4),
            plywood=PlywoodSpec(width_mm=1220, length_mm=2440),
        )
        # 4m / 0.244 ≈ 17 barrotes
        assert 15 <= len(grid.secundarias()) <= 20

    def test_plywood_brazilian_220mm_seam(self):
        shores = [ShorePoint(x=ix, y=iy) for ix in range(5) for iy in range(5)]
        grid = build_vm_grid(
            shores,
            polygon_bbox=(0, 0, 4, 4),
            plywood=PlywoodSpec(width_mm=1100, length_mm=2200),
        )
        # 4m / 0.220 ≈ 19 barrotes
        assert 17 <= len(grid.secundarias()) <= 22

    def test_bom_aggregates_by_model_and_length(self):
        shores = [ShorePoint(x=ix, y=iy) for ix in range(7) for iy in range(5)]
        grid = build_vm_grid(shores, polygon_bbox=(0, 0, 6, 4), load_kn_m2=7.7)
        bom = vm_grid_bom_summary(grid)
        # Cada entrada e (model, length_mm, qty)
        assert all(len(item) == 3 for item in bom)
        # Deve ter ao menos VM130 e VM80
        models = {b[0] for b in bom}
        assert "VM130" in models
        assert "VM80" in models

    def test_moment_check_pass_for_typical_span(self):
        # Vao 1m + carga 7.7 kN/m2 -> M = q*L^2/8
        shores = [ShorePoint(x=ix, y=iy) for ix in range(3) for iy in range(3)]
        grid = build_vm_grid(shores, polygon_bbox=(0, 0, 2, 2), load_kn_m2=7.7)
        for seg in grid.primarias():
            assert seg.passes_moment, f"primaria deveria passar: M={seg.moment_kn_m}"

    def test_moment_fails_for_excessive_load(self):
        # Carga 200 kN/m2 (absurda) com vao 3m -> deve falhar
        shores = [
            ShorePoint(x=0, y=0), ShorePoint(x=3, y=0),
            ShorePoint(x=0, y=3), ShorePoint(x=3, y=3),
        ]
        grid = build_vm_grid(
            shores, polygon_bbox=(0, 0, 3, 3), load_kn_m2=200.0,
        )
        failing = [s for s in grid.primarias() if not s.passes_moment]
        assert len(failing) > 0
        assert len(grid.issues) > 0
        assert any("momento" in i for i in grid.issues)


class TestVMGridDataclasses:
    def test_vm_segment_utilization_max_of_moment_and_deflection(self):
        seg = VMSegment(
            role="primaria",
            model="VM130",
            length_mm=2050,
            start=(0, 0), end=(2, 0),
            axis="x",
            moment_kn_m=4.0, moment_adm_kn_m=5.0,
            flecha_mm=2.0, flecha_adm_mm=3.0,
        )
        # u_M = 0.8, u_D = 0.67 -> max = 0.8
        assert abs(seg.utilization - 0.8) < 1e-6

    def test_vm_grid_total_length_filters_by_model(self):
        grid = VMGrid()
        grid.add_segment(VMSegment(
            role="primaria", model="VM130", length_mm=1550,
            start=(0, 0), end=(1, 0), axis="x",
        ))
        grid.add_segment(VMSegment(
            role="primaria", model="VM130", length_mm=2050,
            start=(0, 1), end=(2, 1), axis="x",
        ))
        grid.add_segment(VMSegment(
            role="secundaria", model="VM80", length_mm=1000,
            start=(0, 0), end=(1, 0), axis="x",
        ))
        assert grid.total_length_m("VM130") == pytest.approx(3.6)
        assert grid.total_length_m("VM80") == pytest.approx(1.0)
        # Sem filtro: total de todos
        assert grid.total_length_m() == pytest.approx(4.6)


class TestOrthogonalPrimarias:
    """Manual §28.7 (2026-05-31) - VM primarias devem ser sempre
    perfeitamente ortogonais ao eixo (0° ou 90°), mesmo quando as
    escoras na row tem coordenadas ligeiramente diferentes."""

    def test_row_with_y_jitter_produces_axis_aligned_primaria(self):
        """Escoras com Y variando ~5cm devem gerar primaria horizontal."""
        # Painel largo em X (primary_axis = "y" ... espera)
        # Painel largo em X (width > height) -> primaria axis "y"
        # Quero testar primaria axis "x" -> painel alto em Y (height > width)
        # Mas tambem quero row com escoras horizontais (mesma Y aproximada)
        # Vou usar painel alto em Y para ter primaria axis "x"
        shores = [
            ShorePoint(x=ix, y=iy)
            for ix in range(5)
            for iy in range(8)
        ]
        # Adicionar jitter Y em algumas escoras da primeira row
        shores[0] = ShorePoint(x=0, y=0.05)
        shores[1] = ShorePoint(x=1, y=-0.02)
        # Painel 4x7m -> width=4 < height=7 -> primary_axis="x" (primaria em X)
        grid = build_vm_grid(
            shores, polygon_bbox=(0, 0, 4, 7), load_kn_m2=7.7,
        )
        assert grid.primaria_axis == "x"
        # Cada primaria deve ter start.y == end.y (perfeitamente horizontal)
        for seg in grid.primarias():
            assert abs(seg.start[1] - seg.end[1]) < 1e-9, (
                f"primaria nao-horizontal: start={seg.start} end={seg.end}"
            )

    def test_row_with_x_jitter_in_vertical_panel(self):
        """Painel largo (primary_axis='y'): primarias verticais, X fixo."""
        shores = [
            ShorePoint(x=ix, y=iy)
            for ix in range(8)
            for iy in range(4)
        ]
        # Jitter X
        shores[0] = ShorePoint(x=0.05, y=0)
        shores[8] = ShorePoint(x=-0.02, y=1)
        grid = build_vm_grid(
            shores, polygon_bbox=(0, 0, 7, 4), load_kn_m2=7.7,
        )
        assert grid.primaria_axis == "y"
        for seg in grid.primarias():
            assert abs(seg.start[0] - seg.end[0]) < 1e-9, (
                f"primaria nao-vertical: start={seg.start} end={seg.end}"
            )


class TestGlobalOriginAlignment:
    """Manual §28.7 (2026-05-30) - barrotes secundarios alinham-se ao
    grid global, evitando sobreposicao entre lajes adjacentes."""

    def test_two_adjacent_panels_share_grid(self):
        """Paineis adjacentes com global_origin devem usar mesma grade Y."""
        # Painel A: 0-4m em X, 0-5m em Y
        shores_a = [ShorePoint(x=ix, y=iy) for ix in range(5) for iy in range(6)]
        # Painel B: 4.1-8m em X, 0-5m em Y (adjacente, gap 0.1m)
        shores_b = [ShorePoint(x=4.1 + ix*0.975, y=iy) for ix in range(5) for iy in range(6)]

        plywood = PlywoodSpec(width_mm=1220, length_mm=2440)
        origin = (0.0, 0.0)

        grid_a = build_vm_grid(
            shores_a, polygon_bbox=(0, 0, 4, 5),
            plywood=plywood, global_origin=origin,
        )
        grid_b = build_vm_grid(
            shores_b, polygon_bbox=(4.1, 0, 8, 5),
            plywood=plywood, global_origin=origin,
        )

        # Coletar Y das secundarias horizontais (axis="x")
        ys_a = sorted({round(s.start[1], 4) for s in grid_a.secundarias() if s.axis == "x"})
        ys_b = sorted({round(s.start[1], 4) for s in grid_b.secundarias() if s.axis == "x"})

        # Posicoes Y devem ser MULTIPLOS de 0.244 (snap)
        seam_m = 0.244
        for y in ys_a + ys_b:
            assert abs(y / seam_m - round(y / seam_m)) < 0.01, (
                f"Y={y} nao e multiplo de {seam_m}m"
            )

    def test_global_origin_eliminates_close_barrotes(self):
        """COM global_origin: gaps entre barrotes >= seam_m (244mm)."""
        # Painel A grande (16m em Y) para gerar primarias e detectar eixo X
        shores_a = [
            ShorePoint(x=ix, y=iy*0.512)
            for ix in range(5) for iy in range(11)
        ]
        # Painel B adjacente, comeca a 7mm da borda de A
        shores_b = [
            ShorePoint(x=4 + ix, y=5.130 + iy*0.5)
            for ix in range(5) for iy in range(8)
        ]
        plywood = PlywoodSpec(width_mm=1220, length_mm=2440)

        # SEM global_origin
        g_a_local = build_vm_grid(
            shores_a, polygon_bbox=(0, 0, 4, 5.123), plywood=plywood,
        )
        g_b_local = build_vm_grid(
            shores_b, polygon_bbox=(4, 5.130, 9, 8.630), plywood=plywood,
        )
        ys_local = sorted({
            round(s.start[1], 4)
            for s in g_a_local.secundarias() + g_b_local.secundarias()
            if s.axis == "x"
        })

        # COM global_origin
        g_a = build_vm_grid(
            shores_a, polygon_bbox=(0, 0, 4, 5.123), plywood=plywood,
            global_origin=(0.0, 0.0),
        )
        g_b = build_vm_grid(
            shores_b, polygon_bbox=(4, 5.130, 9, 8.630), plywood=plywood,
            global_origin=(0.0, 0.0),
        )
        # Barrotes EXTRA de emenda (pendencia 18, Orguel p.115) ficam
        # deliberadamente colados a linha de emenda (transpasse lado a
        # lado) — excluir do calculo de alinhamento do grid regular.
        ys_global = sorted({
            round(s.start[1], 4)
            for s in g_a.secundarias() + g_b.secundarias()
            if s.axis == "x" and "emenda" not in (s.notes or "")
        })

        def min_gap(positions):
            gaps = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
            return min(gaps) if gaps else 999.0

        gap_global = min_gap(ys_global)
        # Com snap global, gaps minimos do grid regular devem ser ~seam_m
        assert gap_global >= 0.20, (
            f"global_origin gap minimo={gap_global:.3f}m, esperado >=0.20m"
        )


class TestUTFPRProject1Reference:
    """Verifica geometria proxima ao PROJETO 1 do TCC UTFPR (p.45-50).

    Corrigido 2026-06-11 (manual §28.4, pendencia 25): o painel de
    217.15 m² (laje 20 cm) e o Projeto 1 do TCC Bedenaroski, nao o
    Projeto 2 (que tem 948.41 m²). Os antigos "245/450 mm" citados aqui
    eram COMPRIMENTOS de vigas Doka H20 Eco (2.45/4.50 m) lidos como
    espacamento por engano; o espacamento de secundarias executado era
    48.8 cm ("C/48,8") e 1.52 x 1.00 m e a dimensao do conjunto de torre.
    """

    def test_dense_grid_produces_proportional_segments(self):
        # Simular painel 14m x 15m = 210m² com grid de escoras 1m
        shores = [
            ShorePoint(x=ix, y=iy)
            for ix in range(15)
            for iy in range(16)
        ]
        grid = build_vm_grid(
            shores,
            polygon_bbox=(0, 0, 14, 15),
            load_kn_m2=8.0,  # laje 20cm + sobrecarga
            plywood=PlywoodSpec(width_mm=1220, length_mm=2440),
        )
        # Ordem de grandeza: ~240 segmentos
        assert 200 < len(grid.segments) < 350
        # Primarias devem ser muitas (15 rows × 14 segments = 210)
        assert len(grid.primarias()) >= 150
        # Secundarias = ~60 barrotes (15m / 244mm ~ 62)
        assert 50 <= len(grid.secundarias()) <= 75
