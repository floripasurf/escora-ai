"""Tests for the pipeline_service helper layer (regeneration from revision)."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import ezdxf
import pytest

from api.services import pipeline_service
from api.services.pipeline_service import _generate_output_dxf
from src.models.calculation_models import (
    BeamShoringResult, CalculationResult,
)
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.shore import (
    ShoreCatalogEntry, TowerCatalogEntry, PositionedShore, SupportType,
)


def test_regenerate_from_revision_writes_validated_files(tmp_path: Path):
    """regenerate_from_revision must call process_dxf with output_suffix='_validated'."""
    captured = {}

    def fake_process_dxf(input_path, job_id, mode="price",
                         inventory_name=None, output_suffix="",
                         branch_id=None):
        captured["input_path"] = input_path
        captured["job_id"] = job_id
        captured["output_suffix"] = output_suffix
        stem = Path(input_path).stem
        return {
            "beam_count": 1,
            "pillar_count": 0,
            "slab_count": 0,
            "total_shores": 5,
            "beams": [],
            "slabs": [],
            "warnings": [],
            "output_dxf_path": f"/out/{stem}_escoras{output_suffix}.dxf",
            "csv_path": f"/out/{stem}_BOM{output_suffix}.csv",
            "ifc_path": f"/out/{stem}{output_suffix}.ifc",
            "relatorio": f"/out/{stem}_relatorio{output_suffix}.pdf",
            "memoria_calculo": f"/out/{stem}_memoria_calculo{output_suffix}.pdf",
            "orcamento": f"/out/{stem}_orcamento{output_suffix}.pdf",
        }

    with patch.object(pipeline_service, "process_dxf", side_effect=fake_process_dxf):
        result = pipeline_service.regenerate_from_revision(
            original_input_path="/input/proj.dxf",
            revised_input_path="/input/proj_revisado.dxf",
            job_id="abc123",
        )

    # Called with the revised file, not the original
    assert captured["input_path"] == "/input/proj_revisado.dxf"
    assert captured["job_id"] == "abc123"
    assert captured["output_suffix"] == "_validated"

    # All 6 expected paths use the _validated suffix
    assert result["output_dxf_path"].endswith("_validated.dxf")
    assert result["csv_path"].endswith("_validated.csv")
    assert result["ifc_path"].endswith("_validated.ifc")
    assert result["relatorio"].endswith("_validated.pdf")
    assert result["memoria_calculo"].endswith("_validated.pdf")
    assert result["orcamento"].endswith("_validated.pdf")


# ---------------------------------------------------------------------------
# Visual symbology tests for _generate_output_dxf
# ---------------------------------------------------------------------------

def _shore_entry(shore_id="ESC310", capacity=20.0):
    return ShoreCatalogEntry(
        id=shore_id, manufacturer="Mecanor", model=shore_id,
        type="telescopic", height_min_m=2.0, height_max_m=3.1,
        load_capacity_kn=capacity, weight_kg=15.0,
        tube_external_mm=60.0, tube_internal_mm=48.0,
        base_plate_mm=150.0, price_reference_brl=80.0,
    )


def _tower_entry():
    return TowerCatalogEntry(
        id="TWR-TA150", manufacturer="Orguel", model="TA-150",
        load_capacity_kn=120.0, module_height_m=1.5, base_dimension_m=1.54,
        max_height_m=20.0, weight_per_module_kg=38.0, includes_bracing=True,
        price_per_module_brl=15.0,
    )


def _beam_h(length=8.0, width=0.20):
    return ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[(0.0, 5.0), (length, 5.0)],
        score_geometric=0.9, score_textual=0.0, score_final=0.85,
        name="V1", section_width_m=width, section_height_m=0.40,
        length_m=length,
    )


def _telescopic_beam_result():
    shore = _shore_entry("ESC310")
    beam = _beam_h(length=6.0)
    shores = [
        PositionedShore(
            x=float(i + 1), y=5.0, shore=shore,
            load_applied_kn=10.0, utilization_ratio=0.5,
            support_type=SupportType.TELESCOPIC,
        )
        for i in range(5)
    ]
    return BeamShoringResult(
        beam=beam, support_positions=[0.0, 6.0],
        is_cantilever_start=False, is_cantilever_end=False,
        total_linear_load_kn_m=12.5, shores=shores,
        shore_count=5, spacing_m=1.2,
        selected_shore=shore, shore_height_m=2.6,
    )


def _tower_beam_result():
    shore = _shore_entry("ESC310")
    tower = _tower_entry()
    beam = _beam_h(length=8.0, width=0.20)
    shores = [
        PositionedShore(
            x=float(i * 2 + 1), y=5.0, shore=shore,
            load_applied_kn=20.0, utilization_ratio=0.7,
            support_type=SupportType.TOWER,
            tower=tower,
        )
        for i in range(4)
    ]
    return BeamShoringResult(
        beam=beam, support_positions=[0.0, 8.0],
        is_cantilever_start=False, is_cantilever_end=False,
        total_linear_load_kn_m=20.0, shores=shores,
        shore_count=4, spacing_m=2.0,
        selected_shore=shore, shore_height_m=2.6,
    )


def _calc(beam_results):
    return CalculationResult(
        beam_results=beam_results,
        slab_results=[],
        shore_catalog_used=[],
        total_shores=sum(br.shore_count for br in beam_results),
        total_load_kn=200.0,
        pe_direito_m=2.80,
    )


@pytest.fixture
def empty_input_dxf(tmp_path):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "0"})
    path = str(tmp_path / "input.dxf")
    doc.saveas(path)
    return path


def test_dxf_has_hexagon_shore_marker(empty_input_dxf, tmp_path):
    out = str(tmp_path / "out.dxf")
    calc = _calc([_telescopic_beam_result()])
    _generate_output_dxf(empty_input_dxf, calc, out)

    doc = ezdxf.readfile(out)
    msp = doc.modelspace()
    hex_polylines = [
        e for e in msp.query("LWPOLYLINE")
        if e.dxf.layer == "ESC310_Viga"
        and e.closed
        and len(list(e.vertices())) == 6
    ]
    assert len(hex_polylines) >= 1


def test_dxf_has_two_vm_rails_per_beam(empty_input_dxf, tmp_path):
    out = str(tmp_path / "out.dxf")
    calc = _calc([_tower_beam_result()])
    _generate_output_dxf(empty_input_dxf, calc, out)

    doc = ezdxf.readfile(out)
    msp = doc.modelspace()
    vm_lines = [e for e in msp.query("LINE") if e.dxf.layer.startswith("VM")]
    assert len(vm_lines) == 2

    for line in vm_lines:
        s = line.dxf.start
        e = line.dxf.end
        assert abs(s.y - e.y) < 1e-6  # parallel to horizontal beam axis

    ys = sorted({round(line.dxf.start.y, 4) for line in vm_lines})
    assert len(ys) == 2
    # Separation = 2 * (width/2 + clearance) = 2 * (0.10 + 0.05) = 0.30
    assert abs((ys[1] - ys[0]) - 0.30) < 1e-4


def test_dxf_tower_marker_double_square(empty_input_dxf, tmp_path):
    out = str(tmp_path / "out.dxf")
    calc = _calc([_tower_beam_result()])
    _generate_output_dxf(empty_input_dxf, calc, out)

    doc = ezdxf.readfile(out)
    msp = doc.modelspace()
    tower_polylines = [
        e for e in msp.query("LWPOLYLINE")
        if e.dxf.layer == "TORRE_VIGA" and e.closed
    ]
    # 4 towers × 2 squares (outer + inner) = 8 closed polylines
    assert len(tower_polylines) == 8
