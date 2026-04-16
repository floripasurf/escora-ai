"""Integration tests — VM50 travamento deve aparecer no BOM (Supplier Q4)."""
from src.models.calculation_models import CalculationResult, BeamShoringResult
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.shore import ShoreCatalogEntry, PositionedShore
from src.output.report_data import (
    VM50_BRACING_BOM_ID,
    BARRA_ANCORAGEM_BOM_ID,
    ReportMetadata,
    build_report_data,
)


def _shore_entry(sid="ESC310"):
    return ShoreCatalogEntry(
        id=sid, manufacturer="Supplier", model=sid,
        height_min_m=2.0, height_max_m=3.10,
        load_capacity_kn=30.0, weight_kg=18.6,
        tube_external_mm=60.0, tube_internal_mm=50.0,
        base_plate_mm=150.0, price_reference_brl=30.0,
    )


def _beam(length=6.0, shore_count=5, shore_id="ESC310"):
    shore = _shore_entry(shore_id)
    beam = ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[(0, 0), (length, 0)],
        score_final=1.0,
        length_m=length,
        section_width_m=0.14,
        section_height_m=0.40,
        name="V1",
    )
    shores = [
        PositionedShore(x=float(i), y=0.0, shore=shore,
                        load_applied_kn=5.0, utilization_ratio=0.3)
        for i in range(shore_count)
    ]
    return BeamShoringResult(
        beam=beam, support_positions=[0.0, length],
        total_linear_load_kn_m=10.0, shores=shores,
        shore_count=shore_count, spacing_m=length / max(1, shore_count - 1),
        selected_shore=shore, shore_height_m=2.80,
    )


def _metadata():
    return ReportMetadata(
        project_name="TestVM50", date="2026-04-16",
        scale=1.0, dxf_filename="test.dxf",
    )


class TestVm50BracingBomIntegration:
    def test_vm50_row_added_when_beams_present(self):
        calc = CalculationResult(
            beam_results=[_beam(length=6.0, shore_count=7)],
            pillar_count=4,
        )
        report = build_report_data(calc, _metadata())
        vm50_rows = [r for r in report.bom_rows if r.id == VM50_BRACING_BOM_ID]
        assert len(vm50_rows) == 1, "Deve existir 1 linha VM50 travamento"
        # qty > 0 (lateral + pilar + fundo)
        assert vm50_rows[0].quantity > 0

    def test_barra_ancoragem_row_per_pillar(self):
        calc = CalculationResult(
            beam_results=[_beam()],
            pillar_count=5,
        )
        report = build_report_data(calc, _metadata())
        ancor = [r for r in report.bom_rows if r.id == BARRA_ANCORAGEM_BOM_ID]
        assert len(ancor) == 1
        # 2 barras por pilar (5 pilares × 2 = 10)
        assert ancor[0].quantity == 10

    def test_no_bracing_rows_when_no_beams_no_pillars(self):
        calc = CalculationResult(
            beam_results=[], slab_results=[], pillar_count=0,
        )
        report = build_report_data(calc, _metadata())
        vm50 = [r for r in report.bom_rows if r.id == VM50_BRACING_BOM_ID]
        ancor = [r for r in report.bom_rows if r.id == BARRA_ANCORAGEM_BOM_ID]
        assert vm50 == []
        assert ancor == []

    def test_tower_beam_excluded_from_fundo(self):
        """Viga com torre (TWR-) não gera fundo VM50."""
        tower_shore = ShoreCatalogEntry(
            id="TWR-TA150", manufacturer="Supplier", model="TA-150",
            height_min_m=0.0, height_max_m=25.0,
            load_capacity_kn=120.0, weight_kg=38.0,
            tube_external_mm=0.0, tube_internal_mm=0.0, base_plate_mm=0.0,
            price_reference_brl=0.0,
        )
        tbeam = _beam(length=6.0, shore_count=5)
        tbeam.selected_shore = tower_shore

        calc_tower = CalculationResult(
            beam_results=[tbeam], pillar_count=0,
        )
        report = build_report_data(calc_tower, _metadata())
        vm50 = [r for r in report.bom_rows if r.id == VM50_BRACING_BOM_ID]
        # Só lateral (ceil(6/0.9)=7), fundo=0, pilar=0 → qty=7
        assert len(vm50) == 1
        assert vm50[0].quantity == 7
