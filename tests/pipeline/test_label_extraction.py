"""Testes da extração de rótulos (structural_name / room_hint) via texto DXF."""

from src.utils.labels import extract_room_hint, extract_structural_name


class TestRoomHintExtraction:
    def test_quarto_with_number(self):
        assert extract_room_hint("QUARTO 1") == "Quarto 1"
        assert extract_room_hint("QUARTO 2") == "Quarto 2"

    def test_quarto_no_number(self):
        assert extract_room_hint("QUARTO") == "Quarto"

    def test_cozinha(self):
        assert extract_room_hint("COZINHA") == "Cozinha"

    def test_suite(self):
        assert extract_room_hint("SUITE 1") == "Suite 1"

    def test_banheiro(self):
        assert extract_room_hint("BANHEIRO") == "Banheiro"

    def test_varanda(self):
        assert extract_room_hint("VARANDA") == "Varanda"

    def test_dormitorio(self):
        assert extract_room_hint("DORMITORIO 2") == "Dormitorio 2"
        assert extract_room_hint("DORM 1") == "Dorm 1"

    def test_no_match_returns_none(self):
        assert extract_room_hint("L3") is None
        assert extract_room_hint("VIGA V1") is None
        assert extract_room_hint("") is None


class TestStructuralNameExtraction:
    def test_structural_wins_over_room(self):
        # Texto como "LAJE L3 QUARTO 1" — estrutural deve ser extraído
        assert extract_structural_name("LAJE L3 QUARTO 1") == "L3"

    def test_canonical_form(self):
        # Diferentes inputs canonizam para "L<N>"
        assert extract_structural_name("LJ-5") == "L5"
        assert extract_structural_name("LJ 5") == "L5"
        assert extract_structural_name("LAJE 12") == "L12"


def _build_calc_with_panel(polygon, text_entities, layer="LAJE"):
    """Helper: roda run_calculation com um único painel vindo de hatch."""
    from src.pipeline.stage_calculate import run_calculation

    hatch_layer = layer if "LAJE" in layer.upper() else f"LAJE_{layer}"
    slab_hatches = [{
        "points": list(polygon.exterior.coords),
        "layer": hatch_layer,
        "pattern_name": "SOLID",
        "is_solid": True,
        "area": polygon.area,
    }]
    return run_calculation(
        elements=[],
        pe_direito_m=2.80,
        slab_thickness_m=0.12,
        slab_hatches=slab_hatches,
        slab_polylines=[],
        text_entities=text_entities,
    )


class TestLabelIntegration:
    def test_quarto_text_inside_polygon_becomes_room_hint(self):
        from shapely.geometry import Polygon

        poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        texts = [{"text": "QUARTO 1", "position": (5.0, 5.0)}]
        calc = _build_calc_with_panel(poly, texts)
        assert len(calc.slab_results) == 1
        sr = calc.slab_results[0]
        assert sr.room_hint == "Quarto 1"
        # Label: "Laje N (Quarto 1)" quando não há nome estrutural
        assert "Quarto 1" in sr.label
        assert sr.category == "laje"

    def test_structural_name_takes_priority(self):
        from shapely.geometry import Polygon

        poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        texts = [{"text": "L3", "position": (5.0, 5.0)}]
        calc = _build_calc_with_panel(poly, texts)
        sr = calc.slab_results[0]
        assert sr.structural_name == "L3"
        assert sr.label == "Laje L3"

    def test_no_text_auto_numbered(self):
        from shapely.geometry import Polygon

        poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        calc = _build_calc_with_panel(poly, text_entities=[])
        sr = calc.slab_results[0]
        assert sr.label == "Laje 1"
        assert sr.category_index == 1

    def test_beiral_layer_classification(self):
        from shapely.geometry import Polygon

        # Painel marcado como BEIRAL via layer
        poly = Polygon([(0, 0), (6.0, 0), (6.0, 1.0), (0, 1.0)])
        calc = _build_calc_with_panel(poly, text_entities=[], layer="BEIRAL_NORTE")
        sr = calc.slab_results[0]
        assert sr.category == "beiral"
        assert sr.label.startswith("Beiral")
