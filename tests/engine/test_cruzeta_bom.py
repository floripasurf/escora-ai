"""Tests for cruzeta BOM split between beams and slabs (Orguel rule A1).

Locadora rule (Q5): "Em vigas, o conjunto escora+cruzeta é distribuído a
cada 80 cm sob a viga". So for vigas we use beam length / 0.80 (ceil),
NOT the 0.25 global ratio. Lajes keep the 0.25 calibrated ratio.
"""
import pytest

from src.engine.tower_selector import (
    compute_cruzeta_bom,
    count_cruzetas_viga,
    count_cruzetas_laje,
)
from src.models.shore import ShoreCatalogEntry, AccessoryCatalogEntry


def _shore(id_: str = "ESC450") -> ShoreCatalogEntry:
    return ShoreCatalogEntry(
        id=id_,
        manufacturer="Orguel",
        model=id_,
        height_min_m=3.00,
        height_max_m=4.50,
        load_capacity_kn=22.0,
        weight_kg=18.0,
        tube_external_mm=60.0,
        tube_internal_mm=48.0,
        base_plate_mm=120.0,
        price_reference_brl=250.0,
    )


def _accs():
    return [
        AccessoryCatalogEntry(
            id="CRZ-ESC450", category="cruzeta",
            manufacturer="Orguel", model="Cruzeta ESC450",
            associated_model_ids=["ESC450"],
            weight_kg=3.5, price_brl=8.0,
        ),
        AccessoryCatalogEntry(
            id="CRZ-ESC310", category="cruzeta",
            manufacturer="Orguel", model="Cruzeta ESC310",
            associated_model_ids=["ESC310"],
            weight_kg=2.8, price_brl=6.5,
        ),
        AccessoryCatalogEntry(
            id="CRZ-TORRE", category="cruzeta",
            manufacturer="Orguel", model="Cruzeta TA",
            associated_model_ids=["TWR-TA100", "TWR-TA150"],
            weight_kg=5.8, price_brl=11.0,
        ),
    ]


class _FakeBeam:
    def __init__(self, length_m: float):
        self.length_m = length_m


class _FakeBeamResult:
    def __init__(self, length_m: float, shore_id: str = "ESC450"):
        self.beam = _FakeBeam(length_m)
        self.selected_shore = _shore(shore_id)


class TestCountCruzetasViga:
    def test_6m_beam_yields_8_cruzetas(self):
        """Viga de 6m com espaçamento 0.80m → ceil(6/0.80) = 8 cruzetas."""
        br = _FakeBeamResult(length_m=6.0, shore_id="ESC450")
        counts = count_cruzetas_viga([br])
        assert counts["ESC450"] == 8

    def test_exact_multiple_of_080(self):
        """Viga 4.0m: ceil(4.0/0.80) = 5 cruzetas (0, 0.8, 1.6, 2.4, 3.2 → cover 0..4)."""
        counts = count_cruzetas_viga([_FakeBeamResult(length_m=4.0)])
        assert counts["ESC450"] == 5

    def test_tower_beam_excluded(self):
        """Vigas que usam torres não contam cruzetas sob a regra 0.80m
        (torres já têm 4 cruzetas por torre)."""
        br = _FakeBeamResult(length_m=6.0, shore_id="TWR-TA150")
        counts = count_cruzetas_viga([br])
        assert "TWR-TA150" not in counts
        assert counts == {}

    def test_multiple_beams_same_shore_id(self):
        brs = [
            _FakeBeamResult(length_m=6.0, shore_id="ESC450"),  # 8
            _FakeBeamResult(length_m=3.2, shore_id="ESC450"),  # 4
        ]
        counts = count_cruzetas_viga(brs)
        assert counts["ESC450"] == 12


class TestCountCruzetasVigaSpacingPerfil:
    """Perfil §28.9 `passo_sob_viga_m`: passo configuravel (gold standard
    Orguel 0.50-0.65; legado DOCX 0.80)."""

    def test_spacing_060_yields_denser_count(self):
        """Viga 6m com passo 0.60 → ceil(6/0.60) = 10 cruzetas."""
        br = _FakeBeamResult(length_m=6.0, shore_id="ESC450")
        counts = count_cruzetas_viga([br], spacing_m=0.60)
        assert counts["ESC450"] == 10

    def test_spacing_none_keeps_legacy_080(self):
        br = _FakeBeamResult(length_m=6.0, shore_id="ESC450")
        assert count_cruzetas_viga([br], spacing_m=None) == \
            count_cruzetas_viga([br])

    def test_invalid_spacing_falls_back_to_legacy(self):
        br = _FakeBeamResult(length_m=6.0, shore_id="ESC450")
        counts = count_cruzetas_viga([br], spacing_m=0.0)
        assert counts["ESC450"] == 8


class TestCountCruzetasLaje:
    def test_preserves_025_ratio(self):
        """Lajes mantêm ratio calibrado Orguel (0.25 cruzeta/escora)."""
        counts = count_cruzetas_laje({"ESC310": 100, "ESC450": 40})
        assert counts["ESC310"] == 25
        assert counts["ESC450"] == 10


class TestComputeCruzetaBom:
    def test_combines_beams_slabs_and_towers(self):
        beam_counts = count_cruzetas_viga([
            _FakeBeamResult(length_m=6.0, shore_id="ESC450"),
        ])
        slab_counts = count_cruzetas_laje({"ESC310": 100, "ESC450": 40})
        result = compute_cruzeta_bom(
            _accs(),
            beam_cruzeta_counts=beam_counts,
            slab_cruzeta_counts=slab_counts,
            tower_count=5,
        )
        by_id = {acc.id: qty for acc, qty in result}
        # ESC450: 8 (viga) + 10 (laje) = 18
        assert by_id["CRZ-ESC450"] == 18
        # ESC310: 25 (laje)
        assert by_id["CRZ-ESC310"] == 25
        # Torre: 5 × 4 faces × 1 cruzeta = 20
        assert by_id["CRZ-TORRE"] == 20

    def test_empty_inputs_produce_no_rows(self):
        result = compute_cruzeta_bom(
            _accs(),
            beam_cruzeta_counts={},
            slab_cruzeta_counts={},
            tower_count=0,
        )
        assert result == []
