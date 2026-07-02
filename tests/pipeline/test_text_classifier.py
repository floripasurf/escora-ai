from src.parser.text_classifier import (
    classify_text, extract_section, extract_thickness,
)
from src.models.pipeline_models import ElementType


class TestClassifyText:
    def test_beam_v1(self):
        r = classify_text("V1")
        assert r.element_type == ElementType.BEAM
        assert r.name == "V1"
        assert r.score > 0.8

    def test_beam_vg301(self):
        r = classify_text("VG-301")
        assert r.element_type == ElementType.BEAM

    def test_beam_viga(self):
        r = classify_text("VIGA 5")
        assert r.element_type == ElementType.BEAM
        assert r.name == "VIGA 5"

    def test_pillar_p1(self):
        r = classify_text("P1")
        assert r.element_type == ElementType.PILLAR

    def test_pillar_pilar(self):
        r = classify_text("PILAR 7")
        assert r.element_type == ElementType.PILLAR

    def test_slab_l1(self):
        r = classify_text("L1")
        assert r.element_type == ElementType.SLAB

    def test_slab_laje(self):
        r = classify_text("LAJE 3")
        assert r.element_type == ElementType.SLAB

    def test_unknown(self):
        r = classify_text("QUADRO DE AREAS")
        assert r.element_type == ElementType.UNKNOWN

    def test_layer_vigas(self):
        r = classify_text("VIGAS")
        assert r.element_type == ElementType.BEAM


class TestExtractSection:
    def test_14x40(self):
        w, h = extract_section("14x40")
        assert w == 0.14
        assert h == 0.40

    def test_14_slash_60(self):
        w, h = extract_section("14/60")
        assert w == 0.14
        assert h == 0.60

    def test_20x50_in_context(self):
        w, h = extract_section("V3 (20x50)")
        assert w == 0.20
        assert h == 0.50

    def test_no_section(self):
        result = extract_section("V1")
        assert result is None


class TestExtractThickness:
    def test_h_12(self):
        assert extract_thickness("h=12") == 0.12

    def test_e_15cm(self):
        assert extract_thickness("e=15cm") == 0.15

    def test_esp_10(self):
        assert extract_thickness("ESP. 10") == 0.10

    def test_no_thickness(self):
        assert extract_thickness("LAJE") is None
