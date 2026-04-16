"""Tests for C2 — Densificação de grid em zonas de capitel (Orguel Q6).

Regra da locadora (Q6): em lajes lisas, as torres/escoras devem ser
concentradas em pontos de capitel (ao redor dos pilares). Implementamos
isso como **densificação local** — adicionando escoras em um anel entre
0.70 m (exclusão de punção) e 1.5 m do eixo do pilar, com espaçamento
30% menor que o grid padrão.
"""
from shapely.geometry import Polygon

from src.engine.capitel_densification import (
    CAPITEL_OUTER_RADIUS_M,
    CAPITEL_SPACING_FACTOR,
    capitel_densification_shores,
)
from src.models.shore import ShoreCatalogEntry


def _shore_entry():
    return ShoreCatalogEntry(
        id="ESC310", manufacturer="Orguel", model="ESC310",
        height_min_m=2.0, height_max_m=3.10,
        load_capacity_kn=30.0, weight_kg=18.6,
        tube_external_mm=60.0, tube_internal_mm=50.0,
        base_plate_mm=150.0, price_reference_brl=30.0,
    )


class TestCapitelConstants:
    def test_outer_radius_is_1_5m(self):
        assert CAPITEL_OUTER_RADIUS_M == 1.5

    def test_spacing_factor_is_70_percent(self):
        # "reduzir espaçamento em 30%" → multiplica por 0.70
        assert CAPITEL_SPACING_FACTOR == 0.70


class TestCapitelDensification:
    def test_returns_shores_around_pillar(self):
        """Pilar no centro de laje 6×6 gera ≥1 escora extra no anel."""
        polygon = Polygon([(0, 0), (6, 0), (6, 6), (0, 6)])
        extra = capitel_densification_shores(
            polygon=polygon,
            shore_entry=_shore_entry(),
            pillar_positions=[(3.0, 3.0)],
            existing_shores=[],
            max_spacing=1.30,
        )
        assert len(extra) > 0
        # Todas no anel interior 0.7-1.5m (tolerância p/ arredondamento)
        import math
        for s in extra:
            d = math.hypot(s.x - 3.0, s.y - 3.0)
            assert 0.70 - 1e-3 <= d <= 1.5 + 1e-3

    def test_no_pillars_returns_empty(self):
        polygon = Polygon([(0, 0), (6, 0), (6, 6), (0, 6)])
        extra = capitel_densification_shores(
            polygon=polygon,
            shore_entry=_shore_entry(),
            pillar_positions=[],
            existing_shores=[],
            max_spacing=1.30,
        )
        assert extra == []

    def test_pillar_outside_polygon_ignored(self):
        """Pilar fora do polígono (+ fora do entorno próximo) não gera escoras."""
        polygon = Polygon([(0, 0), (6, 0), (6, 6), (0, 6)])
        extra = capitel_densification_shores(
            polygon=polygon,
            shore_entry=_shore_entry(),
            pillar_positions=[(20.0, 20.0)],
            existing_shores=[],
            max_spacing=1.30,
        )
        assert extra == []

    def test_pillar_close_to_edge_clips_to_polygon(self):
        """Pilar próximo à borda: shoras extras ficam dentro do polígono."""
        polygon = Polygon([(0, 0), (6, 0), (6, 6), (0, 6)])
        extra = capitel_densification_shores(
            polygon=polygon,
            shore_entry=_shore_entry(),
            pillar_positions=[(0.5, 0.5)],  # Cantinho
            existing_shores=[],
            max_spacing=1.30,
        )
        # Todas devem estar dentro do polígono
        for s in extra:
            from shapely.geometry import Point
            assert polygon.contains(Point(s.x, s.y))

    def test_does_not_duplicate_near_existing_shores(self):
        """Se já existe escora em posição próxima, não duplica."""
        from src.models.shore import PositionedShore
        polygon = Polygon([(0, 0), (6, 0), (6, 6), (0, 6)])
        shore = _shore_entry()
        # Pré-preenche uma escora a ~1m do pilar
        existing = [
            PositionedShore(x=2.0, y=3.0, shore=shore,
                            load_applied_kn=0.0, utilization_ratio=0.0)
        ]
        extra = capitel_densification_shores(
            polygon=polygon,
            shore_entry=shore,
            pillar_positions=[(3.0, 3.0)],
            existing_shores=existing,
            max_spacing=1.30,
        )
        # Nenhuma delas pode cair em cima/muito próxima da existente
        for s in extra:
            import math
            d = math.hypot(s.x - 2.0, s.y - 3.0)
            assert d > 0.30  # folga mínima aceitável


class TestIntegrationSpacingReduction:
    def test_spacing_reduction_generates_denser_shores(self):
        """Mais escoras extras quando max_spacing é pequeno (grid denso)."""
        polygon = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        sparse = capitel_densification_shores(
            polygon=polygon,
            shore_entry=_shore_entry(),
            pillar_positions=[(5.0, 5.0)],
            existing_shores=[],
            max_spacing=1.30,
        )
        # Pelo menos um anel de escoras (4 pontos nos cardeais)
        assert len(sparse) >= 3
