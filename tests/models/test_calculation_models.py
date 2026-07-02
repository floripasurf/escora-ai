"""Test calculation result models."""

from shapely.geometry import box
from src.models.calculation_models import (
    BeamShoringResult, SlabShoringResult, CalculationResult,
)
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.shore import ShoreCatalogEntry, PositionedShore


def _make_shore_entry():
    return ShoreCatalogEntry(
        id="TEST-01", manufacturer="Generic", model="T-180",
        type="telescopic", height_min_m=1.80, height_max_m=3.20,
        load_capacity_kn=20.0, weight_kg=12.0,
        tube_external_mm=60.0, tube_internal_mm=48.0,
        base_plate_mm=150.0, price_reference_brl=85.0,
    )


def _make_beam_element():
    return ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[(0.0, 5.0), (8.0, 5.0)],
        score_geometric=0.85, score_textual=0.0, score_final=0.75,
        section_width_m=0.14, section_height_m=0.40, length_m=8.0,
    )


def test_beam_shoring_result_creation():
    shore = _make_shore_entry()
    beam = _make_beam_element()
    result = BeamShoringResult(
        beam=beam,
        support_positions=[0.0, 8.0],
        is_cantilever_start=False,
        is_cantilever_end=False,
        total_linear_load_kn_m=12.5,
        shores=[
            PositionedShore(x=2.0, y=5.0, shore=shore, load_applied_kn=10.0, utilization_ratio=0.50),
        ],
        shore_count=1,
        spacing_m=2.0,
        selected_shore=shore,
        shore_height_m=2.40,
    )
    assert result.shore_count == 1
    assert result.total_linear_load_kn_m == 12.5


def test_slab_shoring_result_creation():
    shore = _make_shore_entry()
    polygon = box(0, 0, 5, 4)
    result = SlabShoringResult(
        polygon=polygon,
        thickness_m=0.12,
        thickness_is_default=True,
        area_m2=20.0,
        is_cantilever=False,
        total_load_kn=100.0,
        shores=[],
        grid_nx=3, grid_ny=3,
        spacing_x_m=1.5, spacing_y_m=1.2,
        selected_shore=shore,
        exclusions=[],
    )
    assert result.area_m2 == 20.0
    assert result.thickness_is_default is True


def test_calculation_result_totals():
    result = CalculationResult(
        beam_results=[], slab_results=[],
        shore_catalog_used=[], total_shores=15,
        total_load_kn=500.0,
        pe_direito_m=2.80, pe_direito_is_default=True,
        warnings=["Pe-direito usando valor padrao 2.80m"],
        validation_errors=[], is_valid=True,
    )
    assert result.total_shores == 15
    assert result.pe_direito_is_default is True
    assert len(result.warnings) == 1


def test_calculation_result_serialization():
    result = CalculationResult(
        beam_results=[], slab_results=[],
        shore_catalog_used=[], total_shores=0,
        total_load_kn=0.0,
        pe_direito_m=2.80, pe_direito_is_default=False,
        warnings=[], validation_errors=[], is_valid=True,
    )
    d = result.model_dump()
    assert "total_shores" in d
    assert "warnings" in d
