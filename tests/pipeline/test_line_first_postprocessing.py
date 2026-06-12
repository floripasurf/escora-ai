"""Pos-processamento line-first (manual §28.8).

Invariante: no modo line_first, NENHUMA escora de laje pode ficar a mais
de 0.10 m de uma linha de guia no resultado final. O enforcer
``_enforce_line_first_shores_on_lines`` remove escoras orfas injetadas
por pos-processadores legados (ex.: geradores de pontos avulsos).
"""
import pytest
from shapely.geometry import Polygon

from src.engine.vm_grid_builder import VMGrid, VMSegment
from src.models.calculation_models import SlabShoringResult
from src.models.shore import PositionedShore, ShoreCatalogEntry
from src.pipeline.stage_calculate import (
    LINE_FIRST_MAX_OFFLINE_DIST_M,
    _enforce_line_first_shores_on_lines,
)


def _shore_entry() -> ShoreCatalogEntry:
    return ShoreCatalogEntry(
        id="esc310",
        manufacturer="Test",
        model="ESC310",
        type="telescopic",
        height_min_m=1.8,
        height_max_m=3.1,
        load_capacity_kn=20.0,
        weight_kg=15.0,
        tube_external_mm=60,
        tube_internal_mm=48,
        base_plate_mm=150,
        price_reference_brl=10.0,
    )


def _segment(start, end) -> VMSegment:
    return VMSegment(
        role="primaria",
        model="VM130",
        length_mm=4100,
        start=start,
        end=end,
        axis="x",
        load_kn_m=9.6,
        span_m=1.25,
        moment_kn_m=1.0,
        moment_adm_kn_m=5.06,
        flecha_mm=1.0,
        flecha_adm_mm=3.0,
        passes_moment=True,
        passes_deflection=True,
    )


def _ps(x, y, entry):
    return PositionedShore(
        x=x, y=y, shore=entry, load_applied_kn=5.0, utilization_ratio=0.25,
    )


def _slab_result(shores, layout_mode="line_first", vm_grid=None):
    return SlabShoringResult(
        polygon=Polygon([(0, 0), (8, 0), (8, 5), (0, 5)]),
        thickness_m=0.12,
        area_m2=40.0,
        total_load_kn=308.0,
        shores=shores,
        selected_shore=_shore_entry(),
        layout_mode=layout_mode,
        vm_grid=vm_grid,
        shores_weight_kg=sum(s.shore.weight_kg for s in shores),
    )


@pytest.fixture
def grid_2_linhas() -> VMGrid:
    grid = VMGrid(primaria_axis="x")
    grid.add_segment(_segment((0.3, 1.25), (7.7, 1.25)))
    grid.add_segment(_segment((0.3, 2.50), (7.7, 2.50)))
    return grid


class TestEnforceLineFirstShoresOnLines:
    def test_remove_escora_orfa_fora_das_linhas(self, grid_2_linhas):
        entry = _shore_entry()
        shores = [
            _ps(0.3, 1.25, entry),   # na linha
            _ps(4.0, 1.25, entry),   # na linha
            _ps(4.0, 1.90, entry),   # ORFA: 0.60 m da linha mais proxima
        ]
        sr = _slab_result(shores, vm_grid=grid_2_linhas)
        warnings: list = []
        dropped = _enforce_line_first_shores_on_lines([sr], warnings)
        assert dropped == 1
        assert len(sr.shores) == 2
        assert all(s.y == pytest.approx(1.25) for s in sr.shores)
        assert warnings and "fora das linhas" in warnings[0]

    def test_tolerancia_10cm_mantem_escora_na_borda(self, grid_2_linhas):
        entry = _shore_entry()
        shores = [
            _ps(0.3, 1.25, entry),
            _ps(4.0, 1.25 + LINE_FIRST_MAX_OFFLINE_DIST_M - 0.001, entry),
        ]
        sr = _slab_result(shores, vm_grid=grid_2_linhas)
        warnings: list = []
        assert _enforce_line_first_shores_on_lines([sr], warnings) == 0
        assert len(sr.shores) == 2

    def test_recalcula_carga_apos_remocao(self, grid_2_linhas):
        entry = _shore_entry()
        shores = [
            _ps(0.3, 1.25, entry),
            _ps(4.0, 1.25, entry),
            _ps(4.0, 3.40, entry),  # orfa
        ]
        sr = _slab_result(shores, vm_grid=grid_2_linhas)
        _enforce_line_first_shores_on_lines([sr], [])
        # 308 kN / 2 escoras = 154 kN cada
        assert all(s.load_applied_kn == pytest.approx(154.0) for s in sr.shores)
        assert sr.shores_weight_kg == pytest.approx(30.0)

    def test_modo_grid_nao_e_afetado(self, grid_2_linhas):
        entry = _shore_entry()
        shores = [_ps(4.0, 1.90, entry)]
        sr = _slab_result(shores, layout_mode="grid", vm_grid=grid_2_linhas)
        assert _enforce_line_first_shores_on_lines([sr], []) == 0
        assert len(sr.shores) == 1

    def test_sem_vm_grid_nao_remove(self):
        entry = _shore_entry()
        sr = _slab_result([_ps(4.0, 1.90, entry)], vm_grid=None)
        assert _enforce_line_first_shores_on_lines([sr], []) == 0
        assert len(sr.shores) == 1

    def test_nunca_reduz_a_zero(self, grid_2_linhas):
        entry = _shore_entry()
        sr = _slab_result([_ps(4.0, 1.90, entry)], vm_grid=grid_2_linhas)
        _enforce_line_first_shores_on_lines([sr], [])
        assert len(sr.shores) == 1  # todas orfas -> mantem (kept vazio)
