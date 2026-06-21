"""Alinhamento de escoras de viga a lattice line-first (v12).

Decisao do revisor (2026-06-12): o motor prioriza as linhas de
escoramento das lajes e posiciona as escoras das vigas ao longo dessas
linhas (cruzamentos lattice x eixo da viga); depois mantem apenas as
complementares necessarias (vao > passo admissivel da viga).
"""
import pytest

from src.models.calculation_models import BeamShoringResult
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.shore import PositionedShore, ShoreCatalogEntry, SupportType
from src.pipeline.stage_calculate import _align_beam_shores_to_lattice


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


def _beam(start, end, name="V1") -> ClassifiedElement:
    import math
    return ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[start, end],
        score_final=1.0,
        name=name,
        length_m=math.hypot(end[0] - start[0], end[1] - start[1]),
        section_width_m=0.20,
        section_height_m=0.50,
    )


def _ps(x, y, entry, load=10.0, tower=None):
    return PositionedShore(
        x=x, y=y, shore=entry,
        load_applied_kn=load,
        utilization_ratio=load / entry.load_capacity_kn,
        support_type=SupportType.TOWER if tower else SupportType.TELESCOPIC,
        tower=tower,
    )


def _beam_result(beam, shores, spacing_m) -> BeamShoringResult:
    return BeamShoringResult(
        beam=beam,
        support_positions=[],
        total_linear_load_kn_m=12.0,
        shores=shores,
        shore_count=len(shores),
        spacing_m=spacing_m,
        selected_shore=_shore_entry(),
        shore_height_m=2.5,
        shores_weight_kg=sum(s.shore.weight_kg for s in shores),
    )


# Quadro de pavimento: linhas horizontais (angulo 0) em y = 0.75 + k*1.50
FRAME = (0.0, 1.50, 0.75)


class TestAlignBeamShoresToLattice:
    def test_viga_perpendicular_snapa_nos_cruzamentos(self):
        entry = _shore_entry()
        beam = _beam((5.0, 0.0), (5.0, 6.0))  # vertical, perpendicular
        shores = [
            _ps(5.0, t, entry)
            for t in (0.3, 1.0, 2.0, 3.0, 4.0, 5.0, 5.7)
        ]
        br = _beam_result(beam, shores, spacing_m=1.50)
        warnings: list = []
        snapped, removed = _align_beam_shores_to_lattice(
            [br], FRAME, warnings,
        )
        # Cruzamentos em y = 0.75, 2.25, 3.75, 5.25 (tol = 0.75)
        assert snapped == 4
        ys = sorted(s.y for s in br.shores)
        for cross in (0.75, 2.25, 3.75, 5.25):
            assert any(abs(y - cross) < 1e-6 for y in ys)
        # Complementar em y=3.0 ficou redundante (vao 2.25->3.75 = pitch
        # 1.50 <= passo admissivel 1.50) e foi removida
        assert removed == 1
        assert len(br.shores) == 6
        assert br.shore_count == 6
        # Pontas (apoios) preservadas
        assert min(ys) == pytest.approx(0.3)
        assert max(ys) == pytest.approx(5.7)
        assert warnings and "lattice" in warnings[0]

    def test_viga_paralela_mantem_passo_proprio(self):
        entry = _shore_entry()
        beam = _beam((0.0, 3.0), (6.0, 3.0))  # horizontal = paralela
        shores = [_ps(t, 3.0, entry) for t in (0.3, 1.7, 3.1, 4.5, 5.7)]
        br = _beam_result(beam, shores, spacing_m=1.40)
        snapped, removed = _align_beam_shores_to_lattice([br], FRAME, [])
        assert snapped == 0 and removed == 0
        assert [s.x for s in br.shores] == [0.3, 1.7, 3.1, 4.5, 5.7]

    def test_complementar_mantida_quando_vao_excede_passo(self):
        entry = _shore_entry()
        # Lattice com pitch 3.0: cruzamentos em y = 1.5 e 4.5
        frame = (0.0, 3.0, 1.5)
        beam = _beam((2.0, 0.0), (2.0, 6.0))
        shores = [_ps(2.0, t, entry) for t in (0.2, 1.4, 2.9, 4.4, 5.8)]
        br = _beam_result(beam, shores, spacing_m=1.50)
        snapped, removed = _align_beam_shores_to_lattice([br], frame, [])
        assert snapped == 2
        assert removed == 0  # vao 1.5->4.5 = 3.0 m > 1.5 m: 2.9 e necessaria
        ys = sorted(s.y for s in br.shores)
        assert ys == pytest.approx([0.2, 1.5, 2.9, 4.5, 5.8])

    def test_torre_nao_e_snapada_nem_removida(self):
        from src.models.shore import TowerCatalogEntry
        entry = _shore_entry()
        tower = TowerCatalogEntry(
            id="t1", manufacturer="Test", model="T60",
            max_height_m=6.0, load_capacity_kn=120.0,
            base_dimension_m=1.0, module_height_m=1.0,
            weight_per_module_kg=30.0, price_per_module_brl=10.0,
        )
        beam = _beam((5.0, 0.0), (5.0, 6.0))
        shores = [
            _ps(5.0, 0.3, entry),
            _ps(5.0, 2.3, entry, tower=tower),  # torre perto do cruzamento
            _ps(5.0, 3.0, entry),
            _ps(5.0, 5.7, entry),
        ]
        br = _beam_result(beam, shores, spacing_m=1.50)
        _align_beam_shores_to_lattice([br], FRAME, [])
        tower_shores = [s for s in br.shores if s.tower is not None]
        assert len(tower_shores) == 1
        assert tower_shores[0].y == pytest.approx(2.3)  # nao snapada

    def test_cargas_escaladas_apos_remocao(self):
        entry = _shore_entry()
        beam = _beam((5.0, 0.0), (5.0, 6.0))
        shores = [
            _ps(5.0, t, entry, load=10.0)
            for t in (0.3, 1.0, 2.0, 3.0, 4.0, 5.0, 5.7)
        ]
        br = _beam_result(beam, shores, spacing_m=1.50)
        _, removed = _align_beam_shores_to_lattice([br], FRAME, [])
        assert removed == 1
        # 7 -> 6 escoras: cargas escaladas por 7/6
        assert all(
            s.load_applied_kn == pytest.approx(10.0 * 7 / 6, abs=0.01)
            for s in br.shores
        )
        assert br.shores_weight_kg == pytest.approx(6 * 15.0)

    def test_sem_floor_frame_e_noop(self):
        entry = _shore_entry()
        beam = _beam((5.0, 0.0), (5.0, 6.0))
        br = _beam_result(beam, [_ps(5.0, 3.0, entry)], spacing_m=1.5)
        assert _align_beam_shores_to_lattice([br], None, []) == (0, 0)
        assert len(br.shores) == 1

    def test_lattice_vertical_angulo_90(self):
        entry = _shore_entry()
        # Linhas verticais (angulo 90) em x = 0.75 + k*1.50
        frame = (90.0, 1.50, -0.75)
        # v = -x*sin(90) + y*cos(90) = -x -> linhas em -x = -0.75 + ...
        beam = _beam((0.0, 2.0), (6.0, 2.0))  # horizontal, perpendicular
        shores = [_ps(t, 2.0, entry) for t in (0.3, 1.0, 2.0, 4.0, 5.7)]
        br = _beam_result(beam, shores, spacing_m=1.50)
        snapped, _removed = _align_beam_shores_to_lattice([br], frame, [])
        assert snapped >= 3
        xs = sorted(s.x for s in br.shores)
        assert any(abs(x - 0.75) < 1e-6 for x in xs)
        assert any(abs(x - 2.25) < 1e-6 for x in xs)
