"""Tests for the pipeline_service helper layer (regeneration from revision)."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import ezdxf
import pytest

from api.services import pipeline_service
from api.services.pipeline_service import _generate_output_dxf
from src.models.calculation_models import (
    BeamShoringResult, CalculationResult, SlabShoringResult,
)
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.shore import (
    ShoreCatalogEntry, TowerCatalogEntry, PositionedShore, SupportType,
)


def test_dwg_conversion_timeout_is_non_fatal(monkeypatch, tmp_path: Path):
    output_dxf = tmp_path / "out.dxf"
    output_dxf.write_text("0\nEOF\n", encoding="utf-8")

    def fake_export(*_args, **_kwargs):
        raise TimeoutError("ODA File Converter exceeded 1s")

    monkeypatch.setattr(pipeline_service, "_export_dwg_with_timeout", fake_export)

    result = pipeline_service._try_generate_dwg(
        str(output_dxf),
        str(tmp_path / "out.dwg"),
        timeout_seconds=1,
    )

    assert result is None


def test_dwg_conversion_error_is_non_fatal(monkeypatch, tmp_path: Path):
    output_dxf = tmp_path / "out.dxf"
    output_dxf.write_text("0\nEOF\n", encoding="utf-8")

    def fake_export(*_args, **_kwargs):
        raise RuntimeError("converter failed")

    monkeypatch.setattr(pipeline_service, "_export_dwg_with_timeout", fake_export)

    result = pipeline_service._try_generate_dwg(
        str(output_dxf),
        str(tmp_path / "out.dwg"),
        timeout_seconds=1,
    )

    assert result is None


def test_dwg_conversion_success_returns_path(monkeypatch, tmp_path: Path):
    output_dxf = tmp_path / "out.dxf"
    output_dxf.write_text("0\nEOF\n", encoding="utf-8")
    output_dwg = tmp_path / "out.dwg"

    def fake_export(*_args, **_kwargs):
        output_dwg.write_text("dwg", encoding="utf-8")
        return str(output_dwg)

    monkeypatch.setattr(pipeline_service, "_export_dwg_with_timeout", fake_export)

    result = pipeline_service._try_generate_dwg(
        str(output_dxf),
        str(output_dwg),
        timeout_seconds=1,
    )

    assert result == str(output_dwg)


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


def test_dxf_vm50_viga_is_not_duplicated(empty_input_dxf, tmp_path):
    out = str(tmp_path / "out.dxf")
    calc = _calc([_telescopic_beam_result()])
    _generate_output_dxf(empty_input_dxf, calc, out)

    doc = ezdxf.readfile(out)
    msp = doc.modelspace()
    vm50_lines = [e for e in msp.query("LINE") if e.dxf.layer == "VM50_Viga"]

    # One travamento marker per telescopic shore. The previous pair-loop
    # drew each interior shore twice.
    assert len(vm50_lines) == len(calc.beam_results[0].shores)

    keys = {
        (
            round(line.dxf.start.x, 3),
            round(line.dxf.start.y, 3),
            round(line.dxf.end.x, 3),
            round(line.dxf.end.y, 3),
        )
        for line in vm50_lines
    }
    assert len(keys) == len(vm50_lines)


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


def test_dxf_does_not_draw_vm50_laje_for_regular_slab(empty_input_dxf, tmp_path):
    from shapely.geometry import box

    shore = _shore_entry("ESC310")
    slab = SlabShoringResult(
        polygon=box(0, 0, 4, 4),
        thickness_m=0.12,
        area_m2=16.0,
        total_load_kn=100.0,
        shores=[
            PositionedShore(
                x=x, y=y, shore=shore,
                load_applied_kn=25.0, utilization_ratio=0.5,
            )
            for x, y in [(0.5, 0.5), (3.5, 0.5), (0.5, 3.5), (3.5, 3.5)]
        ],
        selected_shore=shore,
    )
    calc = CalculationResult(
        beam_results=[],
        slab_results=[slab],
        shore_catalog_used=[],
        total_shores=4,
        total_load_kn=100.0,
        pe_direito_m=2.8,
    )
    out = str(tmp_path / "out.dxf")
    _generate_output_dxf(empty_input_dxf, calc, out)

    doc = ezdxf.readfile(out)
    msp = doc.modelspace()
    assert [e for e in msp if e.dxf.layer == "VM50_Laje"] == []


def test_dxf_tower_legend_only_when_towers_exist(empty_input_dxf, tmp_path):
    out_tel = str(tmp_path / "tel.dxf")
    _generate_output_dxf(empty_input_dxf, _calc([_telescopic_beam_result()]), out_tel)
    tel_texts = [
        e.dxf.text for e in ezdxf.readfile(out_tel).modelspace().query("TEXT")
        if e.dxf.layer == "INFO_ESCORAS"
    ]
    assert "Torre de escoramento" not in tel_texts

    out_tower = str(tmp_path / "tower.dxf")
    _generate_output_dxf(empty_input_dxf, _calc([_tower_beam_result()]), out_tower)
    tower_texts = [
        e.dxf.text for e in ezdxf.readfile(out_tower).modelspace().query("TEXT")
        if e.dxf.layer == "INFO_ESCORAS"
    ]
    assert "Torre de escoramento" in tower_texts


# ---------------------------------------------------------------------------
# BOM CSV: vigas vazadas (VD-*) são adicionadas quando report_data vem
# ---------------------------------------------------------------------------

def test_bom_csv_includes_vigas_vazadas_rows(tmp_path):
    """_generate_bom_csv deve adicionar linhas de acessório para VD-* do ReportData."""
    from api.services.pipeline_service import _generate_bom_csv
    from src.output.report_data import BomRow, ReportData, SummaryData
    import csv

    calc = _calc([_telescopic_beam_result()])

    # ReportData com 1 linha VD-* e 1 linha normal (não-VD)
    report = ReportData(
        project_name="x", date="2026-04-10",
        summary=SummaryData(
            total_shores=5, total_load_kn=100.0, pe_direito_m=2.8,
            pe_direito_is_default=False, slab_thickness_m=0.12,
            thickness_is_default=False, beam_count=1, slab_count=0,
            is_valid=True,
        ),
        bom_rows=[
            BomRow(id="VD-VM80-3M", model="VM80 3m", manufacturer="Orguel",
                   quantity=8, capacity_kn=0.0, height_min_m=0.0,
                   height_max_m=0.0, weight_kg=24.0, total_weight_kg=192.0,
                   price_brl=180.0, total_price_brl=1440.0),
            BomRow(id="ESC310", model="ESC310", manufacturer="Mecanor",
                   quantity=5, capacity_kn=20.0, height_min_m=2.0,
                   height_max_m=3.1, weight_kg=15.0, total_weight_kg=75.0,
                   price_brl=80.0, total_price_brl=400.0),
        ],
    )

    out = str(tmp_path / "bom.csv")
    _generate_bom_csv(calc, out, report_data=report)

    with open(out, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=";"))

    vd_rows = [r for r in rows if r["Elemento"] == "VM80 3m"]
    assert len(vd_rows) == 1
    assert vd_rows[0]["Tipo"] == "Acessório"
    assert vd_rows[0]["Qtd Escoras"] == "8"

    # VD-only logic: ESC310 (non-VD) não é duplicada via report_data path
    acc_rows_from_report = [
        r for r in rows
        if r["Tipo"] == "Acessório" and r["Elemento"] == "ESC310"
    ]
    assert acc_rows_from_report == []


def test_bom_csv_without_report_data_still_works(tmp_path):
    """Backward compat — chamar sem report_data não deve quebrar."""
    from api.services.pipeline_service import _generate_bom_csv

    calc = _calc([_telescopic_beam_result()])
    out = str(tmp_path / "bom.csv")
    _generate_bom_csv(calc, out)  # sem report_data kwarg
    assert Path(out).exists()


# ---------------------------------------------------------------------------
# process_dxf retorna consumption_csv_path
# ---------------------------------------------------------------------------

def test_regenerate_preserves_consumption_csv_path(tmp_path: Path):
    """regenerate_from_revision deve repassar consumption_csv_path."""
    def fake_process_dxf(input_path, job_id, mode="price",
                         inventory_name=None, output_suffix="",
                         branch_id=None):
        stem = Path(input_path).stem
        return {
            "beam_count": 0, "pillar_count": 0, "slab_count": 0,
            "total_shores": 0, "warnings": [],
            "output_dxf_path": f"/out/{stem}_escoras{output_suffix}.dxf",
            "csv_path": f"/out/{stem}_BOM{output_suffix}.csv",
            "consumption_csv_path": f"/out/{stem}_consumo{output_suffix}.csv",
            "ifc_path": None,
        }

    with patch.object(pipeline_service, "process_dxf", side_effect=fake_process_dxf):
        result = pipeline_service.regenerate_from_revision(
            original_input_path="/in/p.dxf",
            revised_input_path="/in/p_rev.dxf",
            job_id="j1",
        )
    assert "consumption_csv_path" in result
    assert result["consumption_csv_path"].endswith("_validated.csv")


def test_process_dxf_propagates_category_label_and_drops_beams_slabs():
    """consumption_summary deve trazer category_label; beams/slabs não devem
    mais ser retornados (ADR — breaking change confirmado pelo usuário)."""
    from unittest.mock import MagicMock
    from api.services.pipeline_service import process_dxf
    from src.output.report_data import (
        ConsumptionByHeightRow, ReportData, SummaryData,
    )

    def fake_run_pipeline(input_path, mode=None, inventory_name=None, branch_id=None,
                          slab_layout_mode=None, methodology=None):
        calc = CalculationResult(
            beam_results=[], slab_results=[],
            total_shores=0, total_load_kn=0.0,
            pe_direito_m=2.80, pe_direito_is_default=False,
            is_valid=True,
        )
        result = MagicMock()
        result.calculation = calc
        result.scale = 1.0
        result.warnings = []
        result.levels = []
        return result

    def fake_build_report_data(calc, metadata):
        summary = SummaryData(
            total_shores=0, total_load_kn=0.0, pe_direito_m=2.80,
            pe_direito_is_default=False, slab_thickness_m=0.12,
            thickness_is_default=False, beam_count=0, slab_count=0,
            is_valid=True,
        )
        rows = [
            ConsumptionByHeightRow(
                pe_direito_m=2.80, area_m2=10.0, volume_bruto_m3=28.0,
                volume_liquido_m3=28.0, shores_weight_kg=100.0,
                accessories_weight_kg=0.0, total_weight_kg=100.0,
                rate_kg_m3_bruto=3.57, rate_kg_m3_liquido=3.57,
                rate_kg_m2=10.0, category_label="Beiral",
            ),
            ConsumptionByHeightRow(
                pe_direito_m=2.80, area_m2=80.0, volume_bruto_m3=224.0,
                volume_liquido_m3=224.0, shores_weight_kg=900.0,
                accessories_weight_kg=0.0, total_weight_kg=900.0,
                rate_kg_m3_bruto=4.02, rate_kg_m3_liquido=4.02,
                rate_kg_m2=11.25, category_label="Laje",
            ),
        ]
        return ReportData(
            project_name="x", date="2026-04-16", summary=summary,
            consumption_rows=rows,
        )

    with patch.object(pipeline_service, "run_pipeline", side_effect=fake_run_pipeline), \
         patch.object(pipeline_service, "build_report_data", side_effect=fake_build_report_data), \
         patch.object(pipeline_service, "_generate_output_dxf"), \
         patch.object(pipeline_service, "_generate_bom_csv"), \
         patch.object(pipeline_service, "write_consumption_csv"), \
         patch.object(pipeline_service, "generate_ifc"), \
         patch.object(pipeline_service, "generate_pdf"), \
         patch.object(pipeline_service, "generate_memoria_calculo"), \
         patch.object(pipeline_service, "generate_orcamento"):
        result = process_dxf(
            input_path="/in/x.dxf", job_id="j-cat",
        )

    assert "beams" not in result
    assert "slabs" not in result
    summary = result["consumption_summary"]
    assert len(summary) == 2
    assert summary[0]["category_label"] == "Beiral"
    assert summary[1]["category_label"] == "Laje"
