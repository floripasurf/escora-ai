"""Tests for B2 — VM50 bracing BOM (Orguel Q4).

Regra da locadora (Q4): VM50 tem 3 usos distintos:
1. **Travamento lateral de vigas**: barras de VM50 a cada 0.80-1.0 m
   ao longo da viga (usamos 0.90 m midpoint da faixa).
2. **Travamento de pilares**: conjunto por pilar = 2× VM50 + 2 barras
   de ancoragem com porca.
3. **Fundo de viga**: 1 conjunto por escora com cruzeta (viga escorada
   com telescópicas) — já que cruzetas/escora é o número relevante.

Este módulo testa o helper `compute_vm50_bracing_bom` que devolve as
contagens por categoria para alimentar o BOM.
"""
import math

from src.engine.vm50_bracing import (
    VM50_LATERAL_SPACING_M,
    compute_vm50_bracing_bom,
)
from src.models.calculation_models import BeamShoringResult
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.shore import ShoreCatalogEntry


def _shore_catalog_entry() -> ShoreCatalogEntry:
    return ShoreCatalogEntry(
        id="ESC310",
        manufacturer="Orguel",
        model="ESC310",
        height_min_m=2.0,
        height_max_m=3.10,
        load_capacity_kn=30.0,
        weight_kg=18.6,
        tube_external_mm=60.0,
        tube_internal_mm=50.0,
        base_plate_mm=150.0,
        price_reference_brl=30.0,
    )


def _beam_result(length_m: float, shore_count: int = 4) -> BeamShoringResult:
    return BeamShoringResult(
        beam=ClassifiedElement(
            element_type=ElementType.BEAM,
            geometry=[(0.0, 0.0), (length_m, 0.0)],
            score_final=1.0,
            length_m=length_m,
        ),
        support_positions=[0.0, length_m],
        total_linear_load_kn_m=10.0,
        shores=[],
        shore_count=shore_count,
        spacing_m=length_m / max(1, shore_count - 1) if shore_count > 1 else length_m,
        selected_shore=_shore_catalog_entry(),
        shore_height_m=2.8,
    )


class TestLateralVigaBracing:
    def test_spacing_constant_is_midpoint_of_range(self):
        """Plano: faixa 0.80-1.0m → usamos 0.90m (midpoint)."""
        assert VM50_LATERAL_SPACING_M == 0.90

    def test_single_beam_lateral_count(self):
        """Viga de 6m → ceil(6/0.90) = 7 barras de VM50 lateral."""
        bom = compute_vm50_bracing_bom([_beam_result(6.0)], pillar_count=0)
        assert bom.lateral_viga == math.ceil(6.0 / 0.90)

    def test_multiple_beams_lateral_sum(self):
        """3m + 4m + 5m → ceil(3/0.9)+ceil(4/0.9)+ceil(5/0.9)."""
        beams = [_beam_result(3.0), _beam_result(4.0), _beam_result(5.0)]
        bom = compute_vm50_bracing_bom(beams, pillar_count=0)
        expected = sum(math.ceil(L / 0.90) for L in (3.0, 4.0, 5.0))
        assert bom.lateral_viga == expected

    def test_zero_length_beam_is_ignored(self):
        bom = compute_vm50_bracing_bom([_beam_result(0.0)], pillar_count=0)
        assert bom.lateral_viga == 0


class TestPilarBracing:
    def test_two_vm50_per_pillar(self):
        """12 pilares → 24 VM50 + 24 barras ancoragem (2 por pilar cada)."""
        bom = compute_vm50_bracing_bom([], pillar_count=12)
        assert bom.pilar_vm50 == 24
        assert bom.pilar_barras_ancoragem == 24

    def test_zero_pillars(self):
        bom = compute_vm50_bracing_bom([], pillar_count=0)
        assert bom.pilar_vm50 == 0
        assert bom.pilar_barras_ancoragem == 0


class TestFundoVigaBracing:
    def test_one_conjunto_per_shore_on_telescopic_beam(self):
        """Viga escorada com telescópicas: 1 conjunto VM50 por escora."""
        beam = _beam_result(6.0, shore_count=7)
        bom = compute_vm50_bracing_bom([beam], pillar_count=0)
        # shore_count=7 → 7 conjuntos de fundo
        assert bom.fundo_viga == 7

    def test_multiple_beams_sum_shores(self):
        beams = [_beam_result(6.0, shore_count=7), _beam_result(4.0, shore_count=5)]
        bom = compute_vm50_bracing_bom(beams, pillar_count=0)
        assert bom.fundo_viga == 12

    def test_tower_supported_beam_excluded(self):
        """Se a viga usa torre (selected_shore.id startswith TWR-), pula fundo."""
        beam = _beam_result(6.0, shore_count=7)
        beam.selected_shore = ShoreCatalogEntry(
            id="TWR-TA150", manufacturer="Orguel", model="TA-150",
            height_min_m=0.0, height_max_m=25.0,
            load_capacity_kn=120.0, weight_kg=38.0,
            tube_external_mm=0.0, tube_internal_mm=0.0, base_plate_mm=0.0,
            price_reference_brl=0.0,
        )
        bom = compute_vm50_bracing_bom([beam], pillar_count=0)
        assert bom.fundo_viga == 0


class TestIntegratedBom:
    def test_combined_scenario(self):
        """3 vigas + 10 pilares: soma lateral + pilar + fundo."""
        beams = [_beam_result(6.0, shore_count=7), _beam_result(4.0, shore_count=5)]
        bom = compute_vm50_bracing_bom(beams, pillar_count=10)
        expected_lateral = math.ceil(6.0 / 0.90) + math.ceil(4.0 / 0.90)
        assert bom.lateral_viga == expected_lateral
        assert bom.pilar_vm50 == 20
        assert bom.pilar_barras_ancoragem == 20
        assert bom.fundo_viga == 12
        # total_vm50 é lateral + pilar + fundo
        assert bom.total_vm50 == expected_lateral + 20 + 12
