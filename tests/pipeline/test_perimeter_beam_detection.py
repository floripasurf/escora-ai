"""Tests for perimeter beam detection (Supplier A3, regra 16).

Regra da locadora (manual, Regra 16): vigas externas/perimetrais têm
limites dimensionais (b≤30cm, h<60cm, L≤3m). A detecção de "externa" é
geométrica: se o centroide da viga está além do casco convexo dos pilares
por mais de PERIMETER_BEAM_HULL_DISTANCE_M, a viga é considerada externa.
"""
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.pipeline.stage_calculate import _pillar_hull, _is_perimeter_beam


def _pillar(x: float, y: float) -> ClassifiedElement:
    return ClassifiedElement(
        element_type=ElementType.PILLAR,
        geometry=[(x, y)],
        score_final=1.0,
    )


def _beam(start, end) -> ClassifiedElement:
    return ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[start, end],
        score_final=1.0,
    )


class TestPillarHull:
    def test_hull_requires_at_least_three_pillars(self):
        assert _pillar_hull([]) is None
        assert _pillar_hull([_pillar(0, 0)]) is None
        assert _pillar_hull([_pillar(0, 0), _pillar(5, 0)]) is None

    def test_hull_built_from_three_plus_pillars(self):
        pillars = [_pillar(0, 0), _pillar(5, 0), _pillar(5, 5), _pillar(0, 5)]
        hull = _pillar_hull(pillars)
        assert hull is not None
        assert hull.area > 0


class TestIsPerimeterBeam:
    def _square_hull(self):
        pillars = [_pillar(0, 0), _pillar(10, 0), _pillar(10, 10), _pillar(0, 10)]
        return _pillar_hull(pillars)

    def test_internal_beam_is_not_perimeter(self):
        """Viga no centro do hull: não é perimetral."""
        hull = self._square_hull()
        beam = _beam((3, 5), (7, 5))  # centroide em (5, 5) — dentro
        assert _is_perimeter_beam(beam, hull) is False

    def test_beam_on_hull_edge_is_not_perimeter(self):
        """Viga no perímetro do hull (exatamente sobre a borda): dentro."""
        hull = self._square_hull()
        beam = _beam((0, 0), (10, 0))  # centroide em (5, 0) — na borda
        assert _is_perimeter_beam(beam, hull) is False

    def test_beam_far_outside_hull_is_perimeter(self):
        """Viga com centroide >0.5m fora do hull: perimetral."""
        hull = self._square_hull()
        # Viga paralela ao topo, deslocada 1.5m para fora
        beam = _beam((2, 11.5), (8, 11.5))  # centroide (5, 11.5) — 1.5m fora
        assert _is_perimeter_beam(beam, hull) is True

    def test_beam_just_outside_hull_within_tolerance_is_not_perimeter(self):
        """Viga com centroide a 0.3m fora (≤0.5m tolerância): não perimetral."""
        hull = self._square_hull()
        beam = _beam((2, 10.3), (8, 10.3))  # 0.3m fora
        assert _is_perimeter_beam(beam, hull) is False

    def test_no_hull_returns_false(self):
        """Sem pilares suficientes para hull: não classifica como perimetral."""
        beam = _beam((0, 0), (5, 0))
        assert _is_perimeter_beam(beam, None) is False
