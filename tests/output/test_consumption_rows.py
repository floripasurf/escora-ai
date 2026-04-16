"""Tests for `_build_consumption_rows` (consumo agregado por pé-direito).

Cobertura:
- single-pé-direito: 1 linha + totais coerentes.
- multi-pé-direito: pro-rata de deduções (vigas/pilares) e acessórios.
- vigas vazadas (VD-*) e cruzetas (CRZ-*) são contadas como acessórios.
- divisão por zero: rates retornam 0.0 quando denominador é 0.
"""

from src.output.report_data import (
    BomRow,
    _build_consumption_rows,
    _is_accessory_bom_row,
)
from src.models.calculation_models import (
    BeamShoringResult,
    CalculationResult,
    SlabShoringResult,
    VolumeBreakdownEntry,
)
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.shore import ShoreCatalogEntry, PositionedShore
from shapely.geometry import box


def _shore(weight=11.0):
    return ShoreCatalogEntry(
        id="ESC-T01", manufacturer="Generico", model="ESC-T01",
        type="telescopic", height_min_m=1.80, height_max_m=3.20,
        load_capacity_kn=20.0, weight_kg=weight,
        tube_external_mm=60.0, tube_internal_mm=48.0,
        base_plate_mm=150.0, price_reference_brl=65.0,
    )


def _slab_result(area=80.0, shores_weight_kg=900.0):
    polygon = box(0, 0, 8, 10)
    shore = _shore()
    shores = [
        PositionedShore(x=float(i), y=float(j), shore=shore,
                        load_applied_kn=10.0, utilization_ratio=0.5)
        for i in range(3) for j in range(3)
    ]
    return SlabShoringResult(
        polygon=polygon, thickness_m=0.12, thickness_is_default=True,
        area_m2=area, is_cantilever=False, total_load_kn=100.0,
        shores=shores, grid_nx=3, grid_ny=3,
        spacing_x_m=1.5, spacing_y_m=1.2,
        selected_shore=shore, exclusions=[],
        shores_weight_kg=shores_weight_kg,
    )


def _beam_result(shores_weight_kg=200.0):
    shore = _shore()
    beam = ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[(0, 5), (8, 5)],
        score_geometric=0.85, score_textual=0.0, score_final=0.75,
        name="V1", section_width_m=0.14, section_height_m=0.40,
        length_m=8.0,
    )
    shores = [
        PositionedShore(x=float(i), y=5.0, shore=shore,
                        load_applied_kn=10.0, utilization_ratio=0.5)
        for i in range(5)
    ]
    return BeamShoringResult(
        beam=beam, support_positions=[0.0, 8.0],
        is_cantilever_start=False, is_cantilever_end=False,
        total_linear_load_kn_m=12.5, shores=shores,
        shore_count=5, spacing_m=1.6,
        selected_shore=shore, shore_height_m=2.40,
        shores_weight_kg=shores_weight_kg,
    )


def _volume_entry(area, pe, weight, label="Laje 1", category="laje"):
    return VolumeBreakdownEntry(
        category=category, label=label,
        area_m2=area, pe_direito_m=pe, volume_m3=area * pe,
        centroid_x=0.0, centroid_y=0.0,
        shores_weight_kg=weight,
    )


def _calc(volume_breakdown, beam_results=None, pe=2.80,
          beam_dedu=0.0, pillar_dedu=0.0):
    return CalculationResult(
        beam_results=beam_results or [],
        slab_results=[],
        pe_direito_m=pe,
        volume_breakdown=volume_breakdown,
        beam_volume_deducted_m3=beam_dedu,
        pillar_volume_deducted_m3=pillar_dedu,
        slab_volume_gross_m3=sum(e.volume_m3 for e in volume_breakdown),
        total_volume_m3=sum(e.volume_m3 for e in volume_breakdown)
                        - beam_dedu - pillar_dedu,
    )


def _accessory_bom(total_kg, prefix="CRZ-"):
    """Cria uma BomRow de acessório com peso total preset."""
    return BomRow(
        id=f"{prefix}TEST", model="ACC", manufacturer="Generico",
        quantity=10, capacity_kn=0.0, height_min_m=0.0, height_max_m=0.0,
        weight_kg=total_kg / 10, total_weight_kg=total_kg,
        price_brl=0.0, total_price_brl=0.0,
    )


class TestSinglePeDireito:
    def test_one_panel_one_row(self):
        calc = _calc(
            volume_breakdown=[_volume_entry(80.0, 2.80, 900.0)],
            beam_results=[_beam_result(shores_weight_kg=200.0)],
            pe=2.80,
            beam_dedu=2.0, pillar_dedu=1.0,
        )
        bom = [_accessory_bom(50.0, "CRZ-"), _accessory_bom(80.0, "VD-")]

        rows, totals = _build_consumption_rows(calc, bom)

        assert len(rows) == 1
        r = rows[0]
        assert r.pe_direito_m == 2.80
        assert r.category_label == "Laje"
        assert r.area_m2 == 80.0
        assert r.volume_bruto_m3 == 224.0          # 80 × 2.80
        assert r.volume_liquido_m3 == 221.0        # 224 − (2+1)
        assert r.shores_weight_kg == 1100.0        # 900 (laje) + 200 (viga)
        assert r.accessories_weight_kg == 130.0    # CRZ + VD
        assert r.total_weight_kg == 1230.0
        # rate = 1230 / 224 ≈ 5.49
        assert r.rate_kg_m3_bruto == round(1230.0 / 224.0, 2)
        # rate liquido = 1230 / 221
        assert r.rate_kg_m3_liquido == round(1230.0 / 221.0, 2)
        # rate kg/m² = 1230 / 80
        assert r.rate_kg_m2 == round(1230.0 / 80.0, 2)

        assert totals["area_m2"] == 80.0
        assert totals["volume_bruto_m3"] == 224.0
        assert totals["shores_kg"] == 1100.0
        assert totals["accessories_kg"] == 130.0
        assert totals["total_kg"] == 1230.0


class TestMultiPeDireito:
    def test_two_groups_pro_rata(self):
        # Grupo A: pe=2.80, área=100 → bruto 280
        # Grupo B: pe=4.20, área=50  → bruto 210
        # Total bruto = 490; share A = 280/490 ≈ 0.5714
        # Vigas/pilares globais = 9.8 m³ → A = 5.6, B = 4.2
        # Acessórios globais = 100 kg → A = 57.14, B = 42.86
        calc = _calc(
            volume_breakdown=[
                _volume_entry(100.0, 2.80, 1000.0, "Laje A"),
                _volume_entry(50.0, 4.20, 800.0, "Laje B"),
            ],
            beam_results=[],   # zero contribuição de vigas
            pe=2.80,
            beam_dedu=5.0, pillar_dedu=4.8,
        )
        bom = [_accessory_bom(100.0, "CRZ-")]

        rows, totals = _build_consumption_rows(calc, bom)

        assert len(rows) == 2
        a, b = rows  # ordenado por pe ASC
        assert a.pe_direito_m == 2.80
        assert b.pe_direito_m == 4.20

        # share A
        share_a = 280.0 / 490.0
        # liquido A = 280 − 9.8 × share
        assert a.volume_liquido_m3 == round(280.0 - 9.8 * share_a, 2)
        # acessórios A
        assert a.accessories_weight_kg == round(100.0 * share_a, 2)
        # totais
        assert totals["area_m2"] == 150.0
        assert totals["volume_bruto_m3"] == 490.0
        # liquido total ≈ bruto − total deduções
        assert abs(totals["volume_liquido_m3"] - (490.0 - 9.8)) < 0.05
        assert totals["accessories_kg"] == 100.0


class TestAccessoryClassification:
    def test_crz_is_accessory(self):
        assert _is_accessory_bom_row(_accessory_bom(50.0, "CRZ-"))

    def test_vd_is_accessory(self):
        assert _is_accessory_bom_row(_accessory_bom(80.0, "VD-"))

    def test_telescopic_is_not_accessory(self):
        row = BomRow(
            id="ESC-T01", model="ESC-T01", manufacturer="Generico",
            quantity=10, capacity_kn=20.0, height_min_m=1.80,
            height_max_m=3.20, weight_kg=11.0, total_weight_kg=110.0,
            price_brl=65.0, total_price_brl=650.0,
        )
        assert not _is_accessory_bom_row(row)

    def test_tower_is_not_accessory(self):
        row = BomRow(
            id="TWR-T1", model="Torre 1", manufacturer="Generico",
            quantity=4, capacity_kn=80.0, height_min_m=2.0,
            height_max_m=4.0, weight_kg=80.0, total_weight_kg=320.0,
            price_brl=400.0, total_price_brl=1600.0,
        )
        assert not _is_accessory_bom_row(row)


class TestEdgeCases:
    def test_empty_calc_returns_empty(self):
        calc = _calc(volume_breakdown=[])
        rows, totals = _build_consumption_rows(calc, [])
        assert rows == []
        assert totals == {}

    def test_zero_volume_zero_rates(self):
        # area > 0 mas volume = 0 (pé-direito 0) — rates kg/m³ devem ser 0
        calc = _calc(
            volume_breakdown=[_volume_entry(50.0, 0.0, 100.0)],
        )
        rows, _ = _build_consumption_rows(calc, [])
        assert len(rows) == 1
        r = rows[0]
        assert r.volume_bruto_m3 == 0.0
        assert r.rate_kg_m3_bruto == 0.0
        assert r.rate_kg_m3_liquido == 0.0
        # rate kg/m² ainda deve calcular
        assert r.rate_kg_m2 == round(100.0 / 50.0, 2)

    def test_only_beams_no_panels(self):
        # Sem volume_breakdown mas com vigas: cria grupo do pe global
        calc = _calc(
            volume_breakdown=[],
            beam_results=[_beam_result(shores_weight_kg=300.0)],
            pe=2.80,
        )
        rows, totals = _build_consumption_rows(calc, [])
        assert len(rows) == 1
        assert rows[0].pe_direito_m == 2.80
        assert rows[0].category_label == "Laje"
        assert rows[0].shores_weight_kg == 300.0
        assert rows[0].volume_bruto_m3 == 0.0
        assert totals["shores_kg"] == 300.0


class TestCategoryGrouping:
    def test_split_by_category_same_pe(self):
        # Mesma altura (2.80), duas categorias: laje + beiral
        calc = _calc(
            volume_breakdown=[
                _volume_entry(80.0, 2.80, 900.0, "Laje 1", category="laje"),
                _volume_entry(10.0, 2.80, 100.0, "Beiral 1", category="beiral"),
            ],
            pe=2.80,
        )
        rows, totals = _build_consumption_rows(calc, [])
        assert len(rows) == 2
        labels = [r.category_label for r in rows]
        # Ordenação estável: categoria ASC → Beiral vem antes de Laje
        assert labels == ["Beiral", "Laje"]
        # Cada grupo mantém suas próprias métricas
        beiral = rows[0]
        laje = rows[1]
        assert beiral.area_m2 == 10.0
        assert beiral.shores_weight_kg == 100.0
        assert laje.area_m2 == 80.0
        assert laje.shores_weight_kg == 900.0
        # Totais somam todas as categorias
        assert totals["area_m2"] == 90.0
        assert abs(totals["volume_bruto_m3"] - (80 * 2.80 + 10 * 2.80)) < 1e-6

    def test_stable_order_pe_asc_then_category_asc(self):
        # 3 grupos: (2.80, Laje), (2.80, Platibanda), (3.00, Laje)
        calc = _calc(
            volume_breakdown=[
                _volume_entry(50.0, 3.00, 400.0, "Laje 2", category="laje"),
                _volume_entry(80.0, 2.80, 900.0, "Laje 1", category="laje"),
                _volume_entry(8.0, 2.80, 60.0, "Platibanda 1", category="platibanda"),
            ],
            pe=2.80,
        )
        rows, _ = _build_consumption_rows(calc, [])
        keys = [(r.pe_direito_m, r.category_label) for r in rows]
        assert keys == [(2.80, "Laje"), (2.80, "Platibanda"), (3.00, "Laje")]

    def test_beam_shores_go_to_default_laje_group(self):
        # Volume breakdown só com beiral. Peso de vigas deve criar grupo Laje
        # separado no pé-direito global, não misturar com Beiral.
        calc = _calc(
            volume_breakdown=[
                _volume_entry(10.0, 2.80, 100.0, "Beiral 1", category="beiral"),
            ],
            beam_results=[_beam_result(shores_weight_kg=500.0)],
            pe=2.80,
        )
        rows, _ = _build_consumption_rows(calc, [])
        assert len(rows) == 2
        beiral = next(r for r in rows if r.category_label == "Beiral")
        laje = next(r for r in rows if r.category_label == "Laje")
        assert beiral.shores_weight_kg == 100.0
        # Vigas concretas entram no grupo Laje
        assert laje.shores_weight_kg == 500.0
        # Grupo Laje tem volume bruto = 0 (sem painéis), mas recebe shore weight
        assert laje.volume_bruto_m3 == 0.0
