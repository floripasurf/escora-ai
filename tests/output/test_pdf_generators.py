"""Tests for PDF generators: relatório, memória de cálculo, orçamento."""

import os
import tempfile
import pytest
from datetime import date
from shapely.geometry import Polygon

from src.models.calculation_models import (
    CalculationResult, BeamShoringResult, SlabShoringResult,
)
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.shore import ShoreCatalogEntry, PositionedShore
from src.output.report_data import build_report_data, ReportMetadata
from src.output.pdf_generator import (
    generate_pdf, generate_memoria_calculo, generate_orcamento,
)


@pytest.fixture
def sample_report_data():
    """Create sample report data for testing."""
    shore = ShoreCatalogEntry(
        id="SH-M", manufacturer="SH", model="Escora Metalica M",
        height_min_m=2.0, height_max_m=3.10, load_capacity_kn=15.0,
        weight_kg=11.5, tube_external_mm=48.3, tube_internal_mm=38.1,
        base_plate_mm=140, price_reference_brl=12.50,
    )
    beam = ClassifiedElement(
        element_type=ElementType.BEAM, name="V1", layer="VIGAS",
        geometry=[(0, 0), (5, 0)], length_m=5.0, section_width_m=0.14,
        section_height_m=0.40, score_final=0.85,
    )
    shores_list = [
        PositionedShore(
            x=i * 1.0, y=0, shore=shore,
            load_applied_kn=10.0, utilization_ratio=0.67,
        )
        for i in range(6)
    ]
    br = BeamShoringResult(
        beam=beam, support_positions=[0, 5.0],
        total_linear_load_kn_m=12.5, shores=shores_list,
        shore_count=6, spacing_m=1.0, selected_shore=shore,
        shore_height_m=2.40,
    )
    slab_poly = Polygon([(0, 0), (5, 0), (5, 4), (0, 4)])
    slab_shores = [
        PositionedShore(
            x=x, y=y, shore=shore,
            load_applied_kn=8.0, utilization_ratio=0.53,
        )
        for x in [1.25, 2.50, 3.75]
        for y in [1.0, 2.0, 3.0]
    ]
    sr = SlabShoringResult(
        polygon=slab_poly, thickness_m=0.12, area_m2=20.0,
        total_load_kn=72.0, shores=slab_shores,
        grid_nx=3, grid_ny=3, spacing_x_m=1.25, spacing_y_m=1.0,
        selected_shore=shore,
    )
    calc = CalculationResult(
        beam_results=[br], slab_results=[sr],
        shore_catalog_used=[shore], total_shores=15,
        total_load_kn=134.5, pe_direito_m=2.80,
        warnings=["Teste de aviso"],
    )
    metadata = ReportMetadata(
        project_name="Projeto Teste",
        date=date.today().strftime("%d/%m/%Y"),
        scale=0.02, dxf_filename="teste.dxf",
    )
    return build_report_data(calc, metadata)


def test_disclaimer_and_art_block_content():
    """The Orguel p.60 disclaimer and an unfilled ART block are mandated on
    every delivered PDF (AGENTS.md 'Engineering Sign-off')."""
    from src.output.pdf_generator import DISCLAIMER_ORGUEL_P60, ART_BLOCK_LINES
    assert "SUGEST" in DISCLAIMER_ORGUEL_P60.upper()
    assert "responsável" in DISCLAIMER_ORGUEL_P60.lower()
    joined = " ".join(ART_BLOCK_LINES)
    assert "ART" in joined          # ART/RRT reference
    assert "CREA" in joined         # CREA registration
    assert any("ssinatura" in line for line in ART_BLOCK_LINES)  # signature line


def test_disclaimer_art_flowables_build():
    from src.output.pdf_generator import _disclaimer_art_flowables, _styles
    flowables = _disclaimer_art_flowables(_styles())
    assert isinstance(flowables, list)
    assert len(flowables) > 0


def test_generate_pdf(sample_report_data):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = f.name
    try:
        result = generate_pdf(sample_report_data, path)
        assert result == path
        assert os.path.exists(path)
        assert os.path.getsize(path) > 1000
    finally:
        os.unlink(path)


def test_generate_memoria_calculo(sample_report_data):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = f.name
    try:
        result = generate_memoria_calculo(sample_report_data, path)
        assert result == path
        assert os.path.exists(path)
        assert os.path.getsize(path) > 2000  # Should be larger than basic report
    finally:
        os.unlink(path)


def test_generate_orcamento(sample_report_data):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = f.name
    try:
        result = generate_orcamento(
            sample_report_data, path,
            client_name="Construtora ABC Ltda",
            validity_days=30,
            rental_period_days=60,
        )
        assert result == path
        assert os.path.exists(path)
        assert os.path.getsize(path) > 2000
    finally:
        os.unlink(path)


def test_orcamento_without_client(sample_report_data):
    """Orçamento should work without a client name."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = f.name
    try:
        result = generate_orcamento(sample_report_data, path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 1000
    finally:
        os.unlink(path)


def test_report_data_has_prices(sample_report_data):
    """BOM rows should include prices for orçamento."""
    assert len(sample_report_data.bom_rows) > 0
    for row in sample_report_data.bom_rows:
        assert row.price_brl > 0
        assert row.total_price_brl > 0
        assert row.quantity > 0
