"""Test report data extraction from CalculationResult."""

import pytest
from src.output.report_data import (
    ReportMetadata, ReportData, SummaryData,
    BeamRow, SlabRow, BomRow, build_report_data,
)
from src.models.calculation_models import (
    CalculationResult, BeamShoringResult, SlabShoringResult,
)
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.shore import ShoreCatalogEntry, PositionedShore, SupportType
from shapely.geometry import box


def _shore(shore_id="ESC-01", capacity=20.0, price=65.0):
    return ShoreCatalogEntry(
        id=shore_id, manufacturer="Generico", model=f"Escora {shore_id}",
        type="telescopic", height_min_m=1.80, height_max_m=3.20,
        load_capacity_kn=capacity, weight_kg=11.0,
        tube_external_mm=60.0, tube_internal_mm=48.0,
        base_plate_mm=150.0, price_reference_brl=price,
    )


def _tower_shore(shore_id="TWR-01", capacity=80.0, price=140.0):
    return ShoreCatalogEntry(
        id=shore_id, manufacturer="Generico", model=f"Torre {shore_id}",
        type="tower", height_min_m=0.0, height_max_m=6.0,
        load_capacity_kn=capacity, weight_kg=45.0,
        tube_external_mm=0.0, tube_internal_mm=0.0,
        base_plate_mm=1200.0, price_reference_brl=price,
    )


def _beam_result(name="V1", width=0.14, height=0.40, length=8.0,
                 shore_count=7, shore_id="ESC-01"):
    shore = _shore(shore_id)
    beam = ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[(0, 5), (length, 5)],
        score_geometric=0.85, score_textual=0.0, score_final=0.75,
        name=name, section_width_m=width, section_height_m=height,
        length_m=length,
    )
    shores = [
        PositionedShore(x=float(i), y=5.0, shore=shore,
                        load_applied_kn=10.0, utilization_ratio=0.5)
        for i in range(shore_count)
    ]
    return BeamShoringResult(
        beam=beam, support_positions=[0.0, length],
        is_cantilever_start=False, is_cantilever_end=False,
        total_linear_load_kn_m=12.5, shores=shores,
        shore_count=shore_count, spacing_m=1.2,
        selected_shore=shore, shore_height_m=2.40,
    )


def _slab_result(area=20.0, thickness=0.12, shore_count=9, shore_id="ESC-02"):
    shore = _shore(shore_id, capacity=15.0, price=45.0)
    polygon = box(0, 0, 5, 4)
    shores = [
        PositionedShore(x=float(i), y=float(j), shore=shore,
                        load_applied_kn=8.0, utilization_ratio=0.4)
        for i in range(3) for j in range(3)
    ]
    return SlabShoringResult(
        polygon=polygon, thickness_m=thickness, thickness_is_default=True,
        area_m2=area, is_cantilever=False, total_load_kn=100.0,
        shores=shores, grid_nx=3, grid_ny=3,
        spacing_x_m=1.5, spacing_y_m=1.2,
        selected_shore=shore, exclusions=[],
    )


def _metadata():
    return ReportMetadata(
        project_name="CVS-COB", date="2026-03-25",
        scale=1.0, dxf_filename="CVS-COB-FOR-006-R00.DXF",
    )


def _calc_result(beam_results=None, slab_results=None, warnings=None,
                 validation_errors=None):
    return CalculationResult(
        beam_results=beam_results or [],
        slab_results=slab_results or [],
        shore_catalog_used=[],
        total_shores=sum(b.shore_count for b in (beam_results or []))
                     + sum(len(s.shores) for s in (slab_results or [])),
        total_load_kn=500.0,
        pe_direito_m=2.80, pe_direito_is_default=True,
        warnings=warnings or [],
        validation_errors=validation_errors or [],
        is_valid=not bool(validation_errors),
    )


class TestBuildReportData:
    def test_returns_report_data(self):
        calc = _calc_result(beam_results=[_beam_result()])
        report = build_report_data(calc, _metadata())
        assert isinstance(report, ReportData)
        assert report.project_name == "CVS-COB"

    def test_summary_totals(self):
        calc = _calc_result(
            beam_results=[_beam_result()],
            slab_results=[_slab_result()],
        )
        report = build_report_data(calc, _metadata())
        assert report.summary.total_shores == calc.total_shores
        assert report.summary.beam_count == 1
        assert report.summary.slab_count == 1
        assert report.summary.pe_direito_is_default is True

    def test_slab_thickness_from_first_slab(self):
        calc = _calc_result(slab_results=[_slab_result(thickness=0.15)])
        report = build_report_data(calc, _metadata())
        assert report.summary.slab_thickness_m == pytest.approx(0.15)
        assert report.summary.thickness_is_default is True

    def test_slab_thickness_default_when_no_slabs(self):
        calc = _calc_result()
        report = build_report_data(calc, _metadata())
        assert report.summary.slab_thickness_m == pytest.approx(0.12)
        assert report.summary.thickness_is_default is True

    def test_beam_rows(self):
        calc = _calc_result(beam_results=[_beam_result(name="V1")])
        report = build_report_data(calc, _metadata())
        assert len(report.beam_rows) == 1
        row = report.beam_rows[0]
        assert row.name == "V1"
        assert row.section == "14x40 cm"
        assert row.section_width_m == pytest.approx(0.14)
        assert row.section_height_m == pytest.approx(0.40)
        assert row.shore_count == 7

    def test_beam_row_no_name(self):
        calc = _calc_result(beam_results=[_beam_result(name=None)])
        report = build_report_data(calc, _metadata())
        assert report.beam_rows[0].name == "Viga sem nome"

    def test_beam_row_no_section(self):
        br = _beam_result()
        br.beam.section_width_m = None
        br.beam.section_height_m = None
        calc = _calc_result(beam_results=[br])
        report = build_report_data(calc, _metadata())
        assert report.beam_rows[0].section == "N/D"

    def test_slab_rows(self):
        calc = _calc_result(slab_results=[_slab_result()])
        report = build_report_data(calc, _metadata())
        assert len(report.slab_rows) == 1
        row = report.slab_rows[0]
        assert row.panel_id == 1
        assert row.grid == "3x3"
        assert row.area_m2 == pytest.approx(20.0)

    def test_slab_row_no_shore(self):
        sr = _slab_result()
        sr.selected_shore = None
        calc = _calc_result(slab_results=[sr])
        report = build_report_data(calc, _metadata())
        assert report.slab_rows[0].shore_model == "N/A"

    def test_bom_aggregation(self):
        """Two beams using same shore model -> aggregated quantity."""
        calc = _calc_result(beam_results=[
            _beam_result(name="V1", shore_count=5, shore_id="ESC-01"),
            _beam_result(name="V2", shore_count=3, shore_id="ESC-01"),
        ])
        report = build_report_data(calc, _metadata())
        shore_rows = [r for r in report.bom_rows if r.id.startswith("ESC")]
        assert len(shore_rows) == 1
        assert shore_rows[0].quantity == 8
        assert shore_rows[0].total_weight_kg == pytest.approx(8 * 11.0)

    def test_bom_multiple_models(self):
        calc = _calc_result(
            beam_results=[_beam_result(shore_id="ESC-01", shore_count=5)],
            slab_results=[_slab_result(shore_id="ESC-02", shore_count=9)],
        )
        report = build_report_data(calc, _metadata())
        shore_rows = [r for r in report.bom_rows if r.id.startswith("ESC")]
        assert len(shore_rows) == 2
        ids = {r.id for r in shore_rows}
        assert ids == {"ESC-01", "ESC-02"}

    def test_bom_counts_mixed_positioned_support_models(self):
        """MIXED panels must count actual tower replacements, not selected_shore."""
        slab = _slab_result(shore_id="ESC310", shore_count=9)
        tower = _tower_shore("TWR-TA100")
        slab.shores[0] = PositionedShore(
            x=0.0, y=0.0, shore=tower,
            load_applied_kn=8.0, utilization_ratio=0.1,
            support_type=SupportType.TOWER,
        )
        slab.shores[1] = PositionedShore(
            x=1.0, y=0.0, shore=tower,
            load_applied_kn=8.0, utilization_ratio=0.1,
            support_type=SupportType.TOWER,
        )

        calc = _calc_result(slab_results=[slab])
        report = build_report_data(calc, _metadata())

        support_rows = {
            r.id: r for r in report.bom_rows
            if r.id in {"ESC310", "TWR-TA100"}
        }
        assert support_rows["ESC310"].quantity == 7
        assert support_rows["TWR-TA100"].quantity == 2

    def test_warnings_include_validation_errors(self):
        calc = _calc_result(
            warnings=["Aviso 1"],
            validation_errors=["Erro: capacidade excedida"],
        )
        report = build_report_data(calc, _metadata())
        assert "Aviso 1" in report.warnings
        assert any("capacidade" in w for w in report.warnings)

    def test_empty_calculation(self):
        calc = _calc_result()
        report = build_report_data(calc, _metadata())
        assert len(report.beam_rows) == 0
        assert len(report.slab_rows) == 0
        assert len(report.bom_rows) == 0

    def test_bom_includes_cruzeta_rows_when_present(self):
        # Use a real ESC310 id so cruzetas match the catalog rule
        calc = _calc_result(beam_results=[
            _beam_result(name="V1", shore_count=20, shore_id="ESC310"),
        ])
        report = build_report_data(calc, _metadata())
        cruzeta_rows = [r for r in report.bom_rows if r.id.startswith("CRZ-")]
        assert len(cruzeta_rows) >= 1
        assert any(r.id == "CRZ-ESC310" for r in cruzeta_rows)
