"""Smoke tests for PDF report generation."""

import os
from src.output.pdf_generator import generate_pdf
from src.output.report_data import (
    ReportData, SummaryData, BeamRow, SlabRow, BomRow,
)


def _empty_report():
    return ReportData(
        project_name="TEST",
        date="2026-03-25",
        summary=SummaryData(
            total_shores=0, total_load_kn=0.0,
            pe_direito_m=2.80, pe_direito_is_default=False,
            slab_thickness_m=0.12, thickness_is_default=True,
            beam_count=0, slab_count=0, is_valid=True,
        ),
    )


def _report_with_data():
    return ReportData(
        project_name="CVS-COB",
        date="2026-03-25",
        summary=SummaryData(
            total_shores=16, total_load_kn=500.0,
            pe_direito_m=2.80, pe_direito_is_default=True,
            slab_thickness_m=0.12, thickness_is_default=True,
            beam_count=2, slab_count=1, is_valid=True,
        ),
        beam_rows=[
            BeamRow(name="V1", section="14x40 cm", section_width_m=0.14,
                    section_height_m=0.40, length_m=8.0, load_kn_m=12.5,
                    shore_count=7, spacing_m=1.2, shore_model="Escora T-01",
                    is_cantilever=False),
            BeamRow(name="V2", section="14x50 cm", section_width_m=0.14,
                    section_height_m=0.50, length_m=6.0, load_kn_m=15.0,
                    shore_count=5, spacing_m=1.1, shore_model="Escora T-01",
                    is_cantilever=True),
        ],
        slab_rows=[
            SlabRow(panel_id=1, area_m2=20.0, thickness_m=0.12,
                    total_load_kn=100.0, grid="3x3", spacing_x_m=1.5,
                    spacing_y_m=1.2, shore_model="Escora T-02",
                    is_cantilever=False),
        ],
        bom_rows=[
            BomRow(id="ESC-01", model="Escora T-01", manufacturer="Generico",
                   quantity=12, capacity_kn=20.0, height_min_m=1.80,
                   height_max_m=3.20, weight_kg=11.0, total_weight_kg=132.0,
                   price_brl=65.0, total_price_brl=780.0),
            BomRow(id="ESC-02", model="Escora T-02", manufacturer="Generico",
                   quantity=9, capacity_kn=15.0, height_min_m=1.80,
                   height_max_m=3.20, weight_kg=8.0, total_weight_kg=72.0,
                   price_brl=45.0, total_price_brl=405.0),
        ],
        warnings=["Pe-direito padrao 2.80m", "ERRO: Escora #3 sobrecarregada"],
    )


class TestPdfGenerator:
    def test_generates_file(self, tmp_path):
        path = str(tmp_path / "test.pdf")
        generate_pdf(_report_with_data(), path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 1000  # non-trivial PDF

    def test_empty_report_generates(self, tmp_path):
        path = str(tmp_path / "test.pdf")
        generate_pdf(_empty_report(), path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 500

    def test_returns_output_path(self, tmp_path):
        path = str(tmp_path / "test.pdf")
        result = generate_pdf(_report_with_data(), path)
        assert result == path
