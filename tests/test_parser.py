"""Testes do módulo parser."""

import pytest
from pathlib import Path
from shapely.geometry import Polygon

from src.parser.dxf_reader import read_dxf, list_layers, find_slab_layers, get_polylines_by_layer, get_document_info
from src.parser.geometry_extractor import extract_polygons
from src.parser.metadata_extractor import extract_thickness_from_layer, extract_level_from_layer
from src.models.slab import Slab


TEST_FILES = Path(__file__).parent.parent / "data" / "test_files"


class TestDxfReader:
    def test_read_simple_slab(self):
        doc = read_dxf(str(TEST_FILES / "simple_slab.dxf"))
        assert doc is not None

    def test_list_layers(self):
        doc = read_dxf(str(TEST_FILES / "simple_slab.dxf"))
        layers = list_layers(doc)
        assert "LAJE_12CM" in layers

    def test_find_slab_layers(self):
        doc = read_dxf(str(TEST_FILES / "simple_slab.dxf"))
        slab_layers = find_slab_layers(doc)
        assert "LAJE_12CM" in slab_layers

    def test_get_polylines(self):
        doc = read_dxf(str(TEST_FILES / "simple_slab.dxf"))
        polylines = get_polylines_by_layer(doc, "LAJE_12CM")
        assert len(polylines) == 1

    def test_document_info(self):
        doc = read_dxf(str(TEST_FILES / "simple_slab.dxf"))
        info = get_document_info(doc)
        assert info["total_entities"] > 0
        assert "LAJE_12CM" in info["layers"]

    def test_two_slabs(self):
        doc = read_dxf(str(TEST_FILES / "two_slabs.dxf"))
        slab_layers = find_slab_layers(doc)
        assert "LAJE_12CM" in slab_layers
        assert "LAJE_15CM" in slab_layers


class TestGeometryExtractor:
    def test_extract_polygon_from_simple_slab(self):
        doc = read_dxf(str(TEST_FILES / "simple_slab.dxf"))
        polylines = get_polylines_by_layer(doc, "LAJE_12CM")
        polygons = extract_polygons(polylines)
        assert len(polygons) == 1

        polygon = polygons[0]
        assert isinstance(polygon, Polygon)
        assert pytest.approx(polygon.area, abs=0.01) == 24.0  # 4x6m
        assert pytest.approx(polygon.length, abs=0.01) == 20.0  # perimeter

    def test_bounding_box(self):
        doc = read_dxf(str(TEST_FILES / "simple_slab.dxf"))
        polylines = get_polylines_by_layer(doc, "LAJE_12CM")
        polygons = extract_polygons(polylines)
        bounds = polygons[0].bounds
        assert bounds[0] == pytest.approx(0.0)  # min_x
        assert bounds[1] == pytest.approx(0.0)  # min_y
        assert bounds[2] == pytest.approx(6.0)  # max_x
        assert bounds[3] == pytest.approx(4.0)  # max_y


class TestMetadataExtractor:
    @pytest.mark.parametrize("layer,expected", [
        ("LAJE_12CM", 0.12),
        ("LAJE_12cm", 0.12),
        ("LAJE_15CM", 0.15),
        ("LAJE_25CM", 0.25),
        ("SLAB_120MM", 0.12),
        ("LAJE_0.12", 0.12),
        ("LAJE12", 0.12),
    ])
    def test_extract_thickness(self, layer, expected):
        result = extract_thickness_from_layer(layer)
        assert result == pytest.approx(expected, abs=0.001)

    def test_default_thickness(self):
        result = extract_thickness_from_layer("CONTORNO")
        assert result == 0.12  # default

    @pytest.mark.parametrize("layer,expected", [
        ("NIVEL_2.80", 2.80),
        ("N+2.80", 2.80),
        ("COTA_280", 2.80),
    ])
    def test_extract_level(self, layer, expected):
        result = extract_level_from_layer(layer)
        assert result == pytest.approx(expected, abs=0.01)


class TestSlabModel:
    def test_slab_from_polygon(self):
        polygon = Polygon([(0, 0), (6, 0), (6, 4), (0, 4)])
        slab = Slab.from_polygon(polygon, "LAJE_12CM", 0.12)

        assert slab.area_m2 == pytest.approx(24.0)
        assert slab.perimeter_m == pytest.approx(20.0)
        assert slab.thickness_m == 0.12
        assert slab.bounding_box.width == pytest.approx(6.0)
        assert slab.bounding_box.height == pytest.approx(4.0)
