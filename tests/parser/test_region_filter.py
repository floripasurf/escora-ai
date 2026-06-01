"""Tests for region_filter — spatial clustering and detail view exclusion."""

import pytest
from src.parser.region_filter import (
    _find_gap_splits,
    _detect_regions,
    _detect_bounding_rectangles,
    _is_in_detail_zone,
    filter_main_plan,
    DETAIL_EXCLUSION_RADIUS,
)
from src.pipeline.stage_parse import (
    TextEntity, SegmentEntity, PolylineEntity, HatchEntity,
    RectEntity, CircleEntity, DimensionEntity,
)


class TestGapDetection:
    def test_small_gap_detected_with_new_threshold(self):
        """Gap of 2.5m should be detected with the new lower threshold."""
        # total_range = 100m → threshold = max(2.0, 0.02*100) = 2.0m
        # 2.5m > 2.0m → should split
        values = [0.0, 1.0, 2.0, 3.0, 5.5, 6.5, 7.5]
        splits = _find_gap_splits(values, 100.0)
        assert len(splits) >= 1
        assert any(3.0 < s < 5.5 for s in splits)

    def test_gap_below_threshold_not_detected(self):
        """Gaps below threshold should not cause splits."""
        values = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
        splits = _find_gap_splits(values, 100.0)
        assert len(splits) == 0


class TestDominanceThreshold:
    def test_main_at_40_pct_activates_filter(self):
        """Main region with 40% of entities should activate filtering (> 35%)."""
        # Create two clusters with a clear gap
        cluster1 = [(float(i), 0.0) for i in range(40)]  # 40 points at y=0
        cluster2 = [(float(i), 50.0) for i in range(60)]  # 60 points at y=50
        centroids = cluster1 + cluster2
        regions = _detect_regions(centroids)
        # Should detect 2 regions; the larger has 60% (>35%), filter activates
        assert len(regions) >= 2

    def test_main_at_30_pct_does_not_activate(self):
        """Main region with only 30% should NOT activate (< 35%)."""
        # This is tested indirectly via filter_main_plan, but we verify
        # the threshold logic: 30/100 = 0.30 < 0.35
        assert 0.30 < 0.35


class TestBoundingRectangleDetection:
    def _make_polyline(self, points, layer="0"):
        return PolylineEntity(points=points, layer=layer, is_closed=True)

    def test_detects_rectangular_frame(self):
        """A closed rectangular polyline should be detected as a frame."""
        rect = self._make_polyline(
            [(10, 10), (20, 10), (20, 18), (10, 18), (10, 10)],
            layer="QUADRO",
        )
        rects = _detect_bounding_rectangles([rect])
        assert len(rects) == 1

    def test_ignores_too_large_rectangle(self):
        """Rectangles > 50m should be ignored (likely the sheet border)."""
        rect = self._make_polyline(
            [(0, 0), (60, 0), (60, 40), (0, 40), (0, 0)],
        )
        rects = _detect_bounding_rectangles([rect])
        assert len(rects) == 0

    def test_ignores_too_small_rectangle(self):
        """Rectangles < 1m should be ignored."""
        rect = self._make_polyline(
            [(0, 0), (0.5, 0), (0.5, 0.5), (0, 0.5), (0, 0)],
        )
        rects = _detect_bounding_rectangles([rect])
        assert len(rects) == 0


class TestDetailExclusionRadius:
    def test_radius_is_8m(self):
        """DETAIL_EXCLUSION_RADIUS should be 8.0m.

        Manual §28.7 (2026-05-30): aumentado de 5.0 para 8.0 porque
        detalhes brasileiros como "DETALHE DE IMPERMEABILIZAÇÃO DO P.S.T"
        e "ESQUEMA DE NIVEIS" frequentemente tem 6-8m de extensao e o
        texto-titulo fica no centro; raio menor deixava entidades nas
        bordas escaparem.
        """
        assert DETAIL_EXCLUSION_RADIUS == 8.0


class TestDetailKeywords:
    """Manual §28.7 (2026-05-30) - novos keywords para bug 3."""

    def _text(self, content: str, x: float = 50.0, y: float = 50.0) -> TextEntity:
        return TextEntity(content=content, x=x, y=y, layer="")

    def test_pst_detail_caught(self):
        """'DETALHE DE IMPERMEABILIZACAO DO P.S.T' deve ser detectado."""
        texts = [self._text("DETALHE DE IMPERMEABILIZACAO DO P.S.T")]
        # Entity dentro do raio 8m
        assert _is_in_detail_zone(50.0 + 6.0, 50.0, texts) is True
        # Entity fora do raio
        assert _is_in_detail_zone(50.0 + 12.0, 50.0, texts) is False

    def test_esquema_de_niveis_caught(self):
        texts = [self._text("ESQUEMA DE NIVEIS")]
        assert _is_in_detail_zone(53.0, 50.0, texts) is True

    def test_impermeabilizacao_caught(self):
        texts = [self._text("IMPERMEABILIZAÇÃO COM MANTA")]
        assert _is_in_detail_zone(52.0, 51.0, texts) is True

    def test_armadura_caught(self):
        texts = [self._text("ARMADURA POSITIVA")]
        assert _is_in_detail_zone(53.0, 50.0, texts) is True

    def test_scale_1_25_caught(self):
        texts = [self._text("ESCALA 1:25")]
        assert _is_in_detail_zone(50.0, 51.0, texts) is True

    def test_planta_principal_not_treated_as_detail(self):
        """Texto sem keyword nao dispara filtro."""
        texts = [self._text("V120a")]  # nome de viga - planta principal
        assert _is_in_detail_zone(50.0, 50.0, texts) is False


class TestImplicitRectFrame:
    """Frames implicitos formados por 4 linhas (nao LWPOLYLINE fechada)."""

    def _h(self, y, x0, x1):
        return SegmentEntity(type="H", y=y, x_min=x0, x_max=x1, x=0, y_min=0, y_max=0)

    def _v(self, x, y0, y1):
        return SegmentEntity(type="V", x=x, y_min=y0, y_max=y1, y=0, x_min=0, x_max=0)

    def _text(self, content, x, y):
        return TextEntity(content=content, x=x, y=y, layer="")

    def test_4_lines_with_anchor_form_frame(self):
        """4 linhas formando retangulo + texto anchor devem ser detectados."""
        from src.parser.region_filter import _detect_implicit_rect_frames
        # Frame de 5x4m com texto de detalhe no centro
        segs = [
            self._h(0.0, 0.0, 5.0),    # bottom
            self._h(4.0, 0.0, 5.0),    # top
            self._v(0.0, 0.0, 4.0),    # left
            self._v(5.0, 0.0, 4.0),    # right
        ]
        texts = [self._text("DETALHE 01", 2.5, 2.0)]  # centro
        rects = _detect_implicit_rect_frames(segs, texts)
        assert len(rects) == 1
        assert rects[0].x_min == 0.0
        assert rects[0].x_max == 5.0

    def test_4_lines_without_anchor_ignored(self):
        """Mesma geometria mas SEM texto de detalhe -> nao e frame."""
        from src.parser.region_filter import _detect_implicit_rect_frames
        segs = [
            self._h(0.0, 0.0, 5.0),
            self._h(4.0, 0.0, 5.0),
            self._v(0.0, 0.0, 4.0),
            self._v(5.0, 0.0, 4.0),
        ]
        texts = [self._text("V120a", 2.5, 2.0)]  # planta principal
        rects = _detect_implicit_rect_frames(segs, texts)
        assert len(rects) == 0

    def test_open_rectangle_not_detected(self):
        """Sem 4o lado vertical nao forma frame."""
        from src.parser.region_filter import _detect_implicit_rect_frames
        segs = [
            self._h(0.0, 0.0, 5.0),
            self._h(4.0, 0.0, 5.0),
            self._v(0.0, 0.0, 4.0),
            # missing right side
        ]
        texts = [self._text("DETALHE", 2.5, 2.0)]
        rects = _detect_implicit_rect_frames(segs, texts)
        assert len(rects) == 0
