"""Test slab thickness extraction from text annotations."""

import pytest
from src.pipeline.stage_metadata import extract_slab_thickness
from src.pipeline.stage_parse import TextEntity


def _text(content, x=0.0, y=0.0):
    return TextEntity(content=content, x=x, y=y, layer="TEXT")


class TestSlabThicknessExtraction:
    def test_h_equals_pattern(self):
        texts = [_text("h=12")]
        assert extract_slab_thickness(texts) == pytest.approx(0.12)

    def test_e_equals_pattern(self):
        texts = [_text("e=15cm")]
        assert extract_slab_thickness(texts) == pytest.approx(0.15)

    def test_esp_pattern(self):
        texts = [_text("ESP 10")]
        assert extract_slab_thickness(texts) == pytest.approx(0.10)

    def test_espessura_pattern(self):
        texts = [_text("ESPESSURA = 20")]
        assert extract_slab_thickness(texts) == pytest.approx(0.20)

    def test_no_match_returns_none(self):
        texts = [_text("V1 (14x40)"), _text("P3")]
        assert extract_slab_thickness(texts) is None

    def test_empty_texts(self):
        assert extract_slab_thickness([]) is None

    def test_value_in_cm_converted_to_m(self):
        texts = [_text("h=12")]
        assert extract_slab_thickness(texts) == pytest.approx(0.12)

    def test_value_already_in_meters(self):
        texts = [_text("h=0.15")]
        assert extract_slab_thickness(texts) == pytest.approx(0.15)
