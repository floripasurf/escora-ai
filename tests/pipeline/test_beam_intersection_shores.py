"""Tests for `_beam_intersections_without_pillar` (Orguel Q3, A4).

Regra da locadora (Q3): "Toda interseção de viga sem pilar deve ter
torre/escora". Este módulo testa o helper geométrico que localiza
cruzamentos viga×viga sem pilar e devolve as posições ao longo da
viga principal.
"""
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.pipeline.stage_calculate import _beam_intersections_without_pillar


def _beam(start, end, length=None) -> ClassifiedElement:
    return ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[start, end],
        score_final=1.0,
        length_m=length,
    )


def _pillar(x, y) -> ClassifiedElement:
    return ClassifiedElement(
        element_type=ElementType.PILLAR,
        geometry=[(x, y)],
        score_final=1.0,
    )


class TestBeamIntersectionsWithoutPillar:
    def test_single_crossing_no_pillar(self):
        """Viga horizontal cruzada por viga vertical sem pilar em (5,0)."""
        main = _beam((0, 0), (10, 0))
        crossing = _beam((5, -3), (5, 3))
        positions = _beam_intersections_without_pillar(main, [crossing], [])
        assert positions == [5.0]

    def test_crossing_with_pillar_ignored(self):
        """Se há pilar na interseção (dentro de 0.70m), não gera forçada."""
        main = _beam((0, 0), (10, 0))
        crossing = _beam((5, -3), (5, 3))
        pillar = _pillar(5.0, 0.0)
        positions = _beam_intersections_without_pillar(main, [crossing], [pillar])
        assert positions == []

    def test_pillar_just_outside_tolerance_still_forces_shore(self):
        """Pilar a >0.70m da interseção não sustenta o ponto → gera forçada."""
        main = _beam((0, 0), (10, 0))
        crossing = _beam((5, -3), (5, 3))
        pillar = _pillar(5.0, 1.0)  # 1m do ponto (5,0) > 0.70m
        positions = _beam_intersections_without_pillar(main, [crossing], [pillar])
        assert positions == [5.0]

    def test_no_other_beams_returns_empty(self):
        main = _beam((0, 0), (10, 0))
        assert _beam_intersections_without_pillar(main, [main], []) == []
        assert _beam_intersections_without_pillar(main, [], []) == []

    def test_endpoint_intersections_skipped(self):
        """Cruzamento no próprio canto da viga não conta (end-joint)."""
        main = _beam((0, 0), (10, 0))
        end_crossing = _beam((10, -3), (10, 3))
        positions = _beam_intersections_without_pillar(main, [end_crossing], [])
        assert positions == []

    def test_multiple_crossings(self):
        """Viga de 12m com 2 vigas atravessando em 3 e 8m — ambas sem pilar."""
        main = _beam((0, 0), (12, 0))
        c1 = _beam((3, -3), (3, 3))
        c2 = _beam((8, -3), (8, 3))
        positions = _beam_intersections_without_pillar(main, [c1, c2], [])
        assert positions == [3.0, 8.0]
