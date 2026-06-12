"""Tests for the calculation pipeline bridge."""

import pytest
from src.pipeline.stage_calculate import (
    associate_beams_pillars,
    run_calculation,
)
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.calculation_models import CalculationResult


def _beam(x1, y1, x2, y2, width=0.14, height=0.40):
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    return ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[(x1, y1), (x2, y2)],
        score_geometric=0.85, score_textual=0.0, score_final=0.75,
        section_width_m=width, section_height_m=height, length_m=length,
    )


def _pillar(cx, cy, w=0.20, h=0.40):
    return ClassifiedElement(
        element_type=ElementType.PILLAR,
        geometry=[(cx, cy)],
        score_geometric=0.80, score_textual=0.0, score_final=0.70,
        section_width_m=w, section_height_m=h,
    )


class TestBeamPillarAssociation:
    def test_pillar_near_beam_endpoint_is_support(self):
        beam = _beam(0, 5, 10, 5)
        pillars = [_pillar(0.1, 5.0), _pillar(9.9, 5.0)]
        result = associate_beams_pillars([beam], pillars)
        assert len(result) == 1
        assoc = result[0]
        assert len(assoc["support_positions"]) == 2
        assert assoc["is_cantilever_start"] is False
        assert assoc["is_cantilever_end"] is False

    def test_beam_with_cantilever_end(self):
        beam = _beam(0, 5, 10, 5)
        pillars = [_pillar(0.1, 5.0)]
        result = associate_beams_pillars([beam], pillars)
        assert len(result) == 1
        assoc = result[0]
        assert assoc["is_cantilever_start"] is False
        assert assoc["is_cantilever_end"] is True

    def test_beam_with_no_pillars_both_cantilever(self):
        beam = _beam(0, 5, 10, 5)
        pillars = [_pillar(20, 20)]
        result = associate_beams_pillars([beam], pillars)
        assert len(result) == 1
        assoc = result[0]
        assert assoc["is_cantilever_start"] is True
        assert assoc["is_cantilever_end"] is True

    def test_pillar_far_from_beam_not_support(self):
        beam = _beam(0, 5, 10, 5)
        pillars = [_pillar(5, 8)]
        result = associate_beams_pillars([beam], pillars)
        assert len(result) == 1
        assert len(result[0]["support_positions"]) == 0


class TestRunCalculation:
    def test_simple_grid_produces_results(self):
        beams = [
            _beam(0, 0, 10, 0),
            _beam(0, 6, 10, 6),
            _beam(0, 0, 0, 6),
            _beam(10, 0, 10, 6),
        ]
        pillars = [
            _pillar(0, 0), _pillar(10, 0),
            _pillar(0, 6), _pillar(10, 6),
        ]
        elements = beams + pillars
        result = run_calculation(elements, pe_direito_m=2.80)
        assert isinstance(result, CalculationResult)
        assert result.total_shores > 0
        assert result.total_load_kn > 0
        assert len(result.beam_results) > 0

    def test_simple_grid_produces_slab_results(self):
        beams = [
            _beam(0, 0, 10, 0),
            _beam(0, 6, 10, 6),
            _beam(0, 0, 0, 6),
            _beam(10, 0, 10, 6),
        ]
        pillars = [
            _pillar(0, 0), _pillar(10, 0),
            _pillar(0, 6), _pillar(10, 6),
        ]
        result = run_calculation(beams + pillars, pe_direito_m=2.80)
        assert len(result.slab_results) > 0

    def test_low_confidence_beam_skipped(self):
        beam = ClassifiedElement(
            element_type=ElementType.BEAM,
            geometry=[(0, 0), (10, 0)],
            score_geometric=0.30, score_textual=0.0, score_final=0.30,
            section_width_m=0.14, section_height_m=0.40, length_m=10.0,
        )
        pillars = [_pillar(0, 0), _pillar(10, 0)]
        result = run_calculation([beam] + pillars, pe_direito_m=2.80)
        assert len(result.beam_results) == 0
        assert any("confiança" in w.lower() or "ignorada" in w.lower() for w in result.warnings)

    def test_missing_beam_height_estimated(self):
        beam = _beam(0, 0, 10, 0)
        beam.section_height_m = None
        beam.section_width_m = 0.14
        pillars = [_pillar(0, 0), _pillar(10, 0)]
        result = run_calculation([beam] + pillars, pe_direito_m=2.80)
        # Now estimated instead of skipped
        assert len(result.beam_results) == 1
        assert any("estimada" in w for w in result.warnings)

    def test_learned_section_height_used(self):
        beam = _beam(0, 0, 10, 0)
        beam.section_height_m = None
        beam.section_width_m = 0.14
        pillars = [_pillar(0, 0), _pillar(10, 0)]
        result = run_calculation(
            [beam] + pillars,
            pe_direito_m=2.80,
            learned_section_height_m=0.25,
        )
        assert len(result.beam_results) == 1
        assert any("aprendido" in w for w in result.warnings)
        # Should NOT fall back to ratio-based estimation
        assert not any("estimada" in w for w in result.warnings)

    def test_default_pe_direito_flagged(self):
        beams = [_beam(0, 0, 10, 0), _beam(0, 6, 10, 6),
                 _beam(0, 0, 0, 6), _beam(10, 0, 10, 6)]
        pillars = [_pillar(0, 0), _pillar(10, 0),
                   _pillar(0, 6), _pillar(10, 6)]
        result = run_calculation(beams + pillars, pe_direito_m=2.80, pe_direito_is_default=True)
        assert result.pe_direito_is_default is True
        assert any("pé-direito" in w.lower() or "pe-direito" in w.lower() or "padrão" in w.lower()
                    for w in result.warnings)


class TestFilterBeamsToMainCluster:
    """Conexao do cluster = distancia entre linhas < buffer_m (CVS-006).

    O bug do duplo buffer (limiar efetivo 2x buffer_m = 10 m) deixava a
    tabela ESQUEMA DE NIVEIS encadear no cluster principal via a barra de
    corte e receber escoramento fantasma.
    """

    def test_tabela_a_9m_da_planta_e_descartada(self):
        from src.pipeline.stage_calculate import _filter_beams_to_main_cluster
        # Planta principal: malha 10x8 m de vigas
        plan = [
            _beam(0, 0, 10, 0), _beam(0, 8, 10, 8),
            _beam(0, 0, 0, 8), _beam(10, 0, 10, 8),
            _beam(0, 4, 10, 4),
        ]
        # "Tabela" de legenda a 9 m da planta (gap > buffer_m=5)
        table = [
            _beam(19, 2, 23, 2), _beam(19, 3, 23, 3), _beam(19, 4, 23, 4),
        ]
        kept = _filter_beams_to_main_cluster(plan + table)
        assert len(kept) == len(plan)
        assert all(b.geometry[0][0] <= 10 for b in kept)

    def test_encadeamento_via_barra_intermediaria_nao_conecta(self):
        from src.pipeline.stage_calculate import _filter_beams_to_main_cluster
        plan = [
            _beam(0, 0, 10, 0), _beam(0, 8, 10, 8),
            _beam(0, 0, 0, 8), _beam(10, 0, 10, 8),
            _beam(0, 4, 10, 4),
        ]
        # Barra de corte a 7 m da planta + tabela a 6 m da barra:
        # com o duplo buffer antigo (10 m efetivos) tudo encadeava.
        bridge = [_beam(17, 0, 22, 0)]
        table = [_beam(19, 6, 23, 6), _beam(19, 7, 23, 7)]
        kept = _filter_beams_to_main_cluster(plan + bridge + table)
        assert len(kept) == len(plan)

    def test_vigas_proximas_permanecem_conectadas(self):
        from src.pipeline.stage_calculate import _filter_beams_to_main_cluster
        plan = [
            _beam(0, 0, 10, 0),
            _beam(0, 4, 10, 4),
            _beam(13, 0, 20, 0),  # ala separada por 3 m (< buffer 5 m)
        ]
        kept = _filter_beams_to_main_cluster(plan)
        assert len(kept) == 3
