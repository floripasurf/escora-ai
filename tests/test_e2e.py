"""Testes end-to-end — pipeline completo."""

import pytest
import os
import csv
from pathlib import Path

from src.parser.dxf_reader import read_dxf, find_slab_layers, get_polylines_by_layer
from src.parser.geometry_extractor import extract_polygons
from src.parser.metadata_extractor import extract_thickness_from_layer
from src.engine.load_calculator import calculate_self_weight, calculate_live_load, calculate_total_load
from src.engine.shore_selector import load_catalog, select_shore
from src.engine.grid_distributor import distribute_shores
from src.engine.validator import validate_result
from src.generator.dxf_writer import generate_output_dxf
from src.generator.bom_generator import write_bom_csv
from src.models.slab import Slab
from src.models.project import ShoringResult


TEST_FILES = Path(__file__).parent.parent / "data" / "test_files"


def run_pipeline(dxf_path: str, output_dir: Path) -> list[ShoringResult]:
    """Executa o pipeline completo para um DXF."""
    doc = read_dxf(dxf_path)
    slab_layers = find_slab_layers(doc)
    catalog = load_catalog()
    results = []

    for layer_name in slab_layers:
        polylines = get_polylines_by_layer(doc, layer_name)
        polygons = extract_polygons(polylines)
        thickness = extract_thickness_from_layer(layer_name)

        for polygon in polygons:
            slab = Slab.from_polygon(polygon, layer_name, thickness)

            self_weight = calculate_self_weight(slab)
            live_load = calculate_live_load(slab)
            total_load = calculate_total_load(slab)

            estimated_load = total_load / max(1, int(slab.area_m2 / 2.25))
            shore = select_shore(catalog, 2.8, estimated_load)
            assert shore is not None

            shores, nx, ny, sx, sy = distribute_shores(slab, shore, total_load)
            load_per_shore = total_load / len(shores)

            if load_per_shore > shore.load_capacity_kn:
                shore = select_shore(catalog, 2.8, load_per_shore)
                assert shore is not None
                shores, nx, ny, sx, sy = distribute_shores(slab, shore, total_load)
                load_per_shore = total_load / len(shores)

            is_valid, errors = validate_result(shores, sx, sy)
            assert is_valid, f"Validação falhou: {errors}"

            results.append(
                ShoringResult(
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
            )

    return results


class TestE2ESimpleSlab:
    """Pipeline completo com laje simples 4x6m, 12cm."""

    def test_full_pipeline(self, tmp_path):
        dxf_path = str(TEST_FILES / "simple_slab.dxf")
        results = run_pipeline(dxf_path, tmp_path)

        assert len(results) == 1
        result = results[0]

        # Verificar cálculos
        assert result.slab.area_m2 == pytest.approx(24.0)
        assert result.slab.thickness_m == pytest.approx(0.12)
        assert result.self_weight_kn == pytest.approx(72.0)
        assert result.live_load_kn == pytest.approx(36.0)
        assert result.total_load_kn == pytest.approx(151.2)

        # Verificar escoramento
        assert len(result.shores) > 0
        assert result.spacing_x_m <= 1.5
        assert result.spacing_y_m <= 1.5

        # Gerar DXF
        output_dxf = str(tmp_path / "simple_slab_escoras.dxf")
        generate_output_dxf(results, output_dxf)
        assert os.path.exists(output_dxf)

        # Gerar BOM
        bom_path = str(tmp_path / "simple_slab_bom.csv")
        write_bom_csv(results, bom_path)
        assert os.path.exists(bom_path)

        with open(bom_path) as f:
            rows = list(csv.DictReader(f))
            total_qty = sum(int(r["quantidade"]) for r in rows)
            assert total_qty == len(result.shores)


class TestE2ETwoSlabs:
    """Pipeline com duas lajes."""

    def test_full_pipeline(self, tmp_path):
        dxf_path = str(TEST_FILES / "two_slabs.dxf")
        results = run_pipeline(dxf_path, tmp_path)

        assert len(results) == 2

        # Laje 12cm
        r12 = [r for r in results if r.slab.thickness_m == pytest.approx(0.12)][0]
        assert r12.slab.area_m2 == pytest.approx(20.0)

        # Laje 15cm
        r15 = [r for r in results if r.slab.thickness_m == pytest.approx(0.15)][0]
        assert r15.slab.area_m2 == pytest.approx(20.0)

        # 15cm deve ter mais carga
        assert r15.total_load_kn > r12.total_load_kn


class TestE2EThickSlab:
    """Pipeline com laje espessa 8x10m, 25cm."""

    def test_full_pipeline(self, tmp_path):
        dxf_path = str(TEST_FILES / "thick_slab.dxf")
        results = run_pipeline(dxf_path, tmp_path)

        assert len(results) == 1
        result = results[0]

        # Verificar laje espessa
        assert result.slab.area_m2 == pytest.approx(80.0)
        assert result.slab.thickness_m == pytest.approx(0.25)
        assert result.self_weight_kn == pytest.approx(500.0)  # 80 × 0.25 × 25

        # Deve ter muitas escoras
        assert len(result.shores) >= 36  # grid mínimo ~7x6

        # Verificar que a escora selecionada suporta a carga
        for shore in result.shores:
            assert shore.utilization_ratio <= 1.0
