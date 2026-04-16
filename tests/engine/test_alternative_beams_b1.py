"""Tests for B1 — ALU14/ALU20/H20 como vigas primárias alternativas (Orguel Q7).

Regra da locadora (Q7): "ALU14 e H20 podem ser utilizadas como principal e
secundária, ou somente como principal tendo VM80 como secundária". Hoje a
locadora não tem estoque corrente desses perfis, então entram no catálogo
com `available=False` — o seletor deve pulá-las em modo inventário (quando
o cliente só quer itens em estoque) mas considerá-las em modo preço (quando
queremos ver alternativas técnicas).
"""
from src.engine.tower_selector import (
    load_tower_catalog,
    select_distribution_beam,
)
from src.engine.inventory import InventoryAvailability
from src.models.shore import DistributionBeamEntry


class TestAlternativeBeamsInCatalog:
    def test_alu14_present_unavailable(self):
        _, beams, _ = load_tower_catalog()
        alu14 = [b for b in beams if b.model.startswith("ALU14")]
        assert alu14, "ALU14 deve estar presente no catálogo"
        assert all(not b.available for b in alu14), (
            "ALU14 é oferta técnica — available=False por padrão"
        )

    def test_alu20_present_unavailable(self):
        _, beams, _ = load_tower_catalog()
        alu20 = [b for b in beams if b.model.startswith("ALU20")]
        assert alu20, "ALU20 deve estar presente no catálogo"
        assert all(not b.available for b in alu20)

    def test_h20_marked_unavailable(self):
        """H20 já existia no catálogo; plano pede available=False."""
        _, beams, _ = load_tower_catalog()
        h20 = [b for b in beams if b.model == "H20"]
        assert h20, "H20 deve continuar no catálogo"
        assert all(not b.available for b in h20)

    def test_vm_families_remain_available(self):
        """VM130/VM80/VM50 são o estoque real da locadora → available=True."""
        _, beams, _ = load_tower_catalog()
        for b in beams:
            if b.model.startswith(("VM130", "VM80", "VM50")):
                assert b.available, f"{b.model} deve permanecer disponível"


class TestSelectDistributionBeamRespectsAvailable:
    """`select_distribution_beam` filtra por `available` conforme o modo."""

    def _fake_beams(self):
        # Uma viga disponível cara e uma alternativa barata indisponível.
        return [
            DistributionBeamEntry(
                id="VD-AVAIL",
                manufacturer="X",
                model="AVAIL",
                height_mm=130,
                moment_capacity_knm=5.0,
                max_span_m=2.5,
                weight_per_m_kg=6.0,
                price_per_m_brl=10.00,
                available=True,
            ),
            DistributionBeamEntry(
                id="VD-ALT",
                manufacturer="X",
                model="ALT",
                height_mm=200,
                moment_capacity_knm=5.0,
                max_span_m=2.5,
                weight_per_m_kg=4.5,
                price_per_m_brl=4.00,  # Mais barato, mas indisponível
                available=False,
            ),
        ]

    def test_price_mode_allows_unavailable(self):
        beams = self._fake_beams()
        chosen = select_distribution_beam(beams, span_m=2.0, load_kn_m=3.0, mode="price")
        # Modo preço: considera todas as tecnicamente válidas → escolhe a mais barata
        assert chosen is not None
        assert chosen.id == "VD-ALT"

    def test_inventory_mode_skips_unavailable(self):
        beams = self._fake_beams()
        inv = InventoryAvailability(
            locadora="Orguel", updated_at="2026-04-16",
            items={"VD-AVAIL": 100},
        )
        chosen = select_distribution_beam(
            beams, span_m=2.0, load_kn_m=3.0,
            mode="inventory", inventory=inv,
        )
        assert chosen is not None
        assert chosen.id == "VD-AVAIL", (
            "Inventory mode deve pular available=False"
        )

    def test_inventory_mode_without_inventory_still_skips_unavailable(self):
        """Sem inventory explícito mas modo=inventory → skip available=False."""
        beams = self._fake_beams()
        chosen = select_distribution_beam(
            beams, span_m=2.0, load_kn_m=3.0, mode="inventory",
        )
        assert chosen is not None
        assert chosen.id == "VD-AVAIL"
