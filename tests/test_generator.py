"""Testes do módulo generator."""

import pytest
import os
import csv
from pathlib import Path
from shapely.geometry import Polygon

from src.models.slab import Slab
from src.models.project import ShoringResult
from src.engine.load_calculator import calculate_self_weight, calculate_live_load, calculate_total_load
from src.engine.shore_selector import load_catalog, select_shore
from src.engine.grid_distributor import distribute_shores
from src.generator.dxf_writer import generate_output_dxf
from src.generator.bom_generator import generate_bom, write_bom_csv
from src.generator.report_generator import print_report


@pytest.fixture
def shoring_result():
    """Resultado de escoramento para uma laje 4x6m."""
    polygon = Polygon([(0, 0), (6, 0), (6, 4), (0, 4)])
    slab = Slab.from_polygon(polygon, "LAJE_12CM", 0.12)

    catalog = load_catalog()
    total_load = calculate_total_load(slab)
    self_weight = calculate_self_weight(slab)
    live_load = calculate_live_load(slab)

    shore = select_shore(catalog, 2.8, 10.0)
    shores, nx, ny, sx, sy = distribute_shores(slab, shore, total_load)
    load_per_shore = total_load / len(shores)

    return ShoringResult(
        slab=slab,
        total_load_kn=round(total_load, 2),
        self_weight_kn=round(self_weight, 2),
        live_load_kn=round(live_load, 2),
        selected_shore=shore,
        shores=shores,
        grid_nx=nx,
        grid_ny=ny,
        spacing_x_m=round(sx, 4),
        spacing_y_m=round(sy, 4),
        load_per_shore_kn=round(load_per_shore, 2),
    )


class TestDxfWriter:
    def test_generate_output_dxf(self, shoring_result, tmp_path):
        output_path = str(tmp_path / "output.dxf")
        result = generate_output_dxf([shoring_result], output_path)

        assert os.path.exists(result)
        assert os.path.getsize(result) > 0

        # Verificar que o DXF pode ser lido de volta
        import ezdxf
        doc = ezdxf.readfile(result)
        layers = [l.dxf.name for l in doc.layers]
        assert "ESTRUTURA" in layers
        assert "ESCORAS" in layers
        assert "TEXTO_ESCORAS" in layers

        # Contar círculos (escoras)
        msp = doc.modelspace()
        circles = [e for e in msp if e.dxftype() == "CIRCLE"]
        assert len(circles) == len(shoring_result.shores)


class TestBomGenerator:
    def test_generate_bom(self, shoring_result):
        bom = generate_bom([shoring_result])
        assert len(bom) > 0

        entry = bom[0]
        assert entry["quantidade"] == len(shoring_result.shores)
        assert "modelo" in entry
        assert "peso_total_kg" in entry

    def test_write_bom_csv(self, shoring_result, tmp_path):
        output_path = str(tmp_path / "bom.csv")
        write_bom_csv([shoring_result], output_path)

        assert os.path.exists(output_path)

        with open(output_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) > 0
            assert "modelo" in rows[0]
            assert "quantidade" in rows[0]


class TestReportGenerator:
    def test_print_report(self, shoring_result, capsys):
        from rich.console import Console
        console = Console(file=open(os.devnull, "w"))
        print_report([shoring_result], console)
        # Se não deu exception, o relatório foi gerado com sucesso
