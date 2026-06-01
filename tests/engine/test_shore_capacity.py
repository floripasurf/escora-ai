"""Testes para shore_capacity — espaçamento adaptativo por carga."""

import pytest
from src.engine.shore_capacity import compute_adaptive_spacing, get_max_spacing_by_thickness


class TestGetMaxSpacingByThickness:
    def test_thin_slab(self):
        assert get_max_spacing_by_thickness(0.12) == 1.30

    def test_medium_slab(self):
        assert get_max_spacing_by_thickness(0.20) == 1.20

    def test_thick_slab(self):
        assert get_max_spacing_by_thickness(0.25) == 1.10

    def test_very_thick_slab(self):
        assert get_max_spacing_by_thickness(0.35) == 1.00

    def test_default_fallback(self):
        # Espessura fora de qualquer faixa → 1.10m
        assert get_max_spacing_by_thickness(0.05) == 1.10


class TestComputeAdaptiveSpacing:
    def test_thin_slab_high_capacity(self):
        """Laje 10cm, ESC310@2.80m → espaçamento amplo, cap pelo teto."""
        # carga = (25*0.10 + 0.50 + 1.50) * 1.4 = (2.5+0.5+1.5)*1.4 = 6.3 kN/m²
        # ESC310@2.80m ≈ 12.0 kN (via capacity_curve, but here we pass directly)
        # area_trib = 12.0 / 6.3 ≈ 1.905 m²
        # spacing = sqrt(1.905) ≈ 1.38m → cap pelo teto 1.30m (faixa 10-16cm)
        spacing = compute_adaptive_spacing(
            slab_thickness_m=0.10,
            floor_height_m=2.80,
            shore_capacity_kn=12.0,
        )
        assert spacing == pytest.approx(1.30, abs=0.01)

    def test_thick_slab_high_capacity(self):
        """Laje 25cm, ESC310@2.80m → espaçamento reduzido pela carga."""
        # carga = (25*0.25 + 0.50 + 1.50) * 1.4 = (6.25+0.5+1.5)*1.4 = 11.55 kN/m²
        # area_trib = 12.0 / 11.55 ≈ 1.039 m²
        # spacing = sqrt(1.039) ≈ 1.019m → cap pelo teto 1.10m → fica 1.019m
        spacing = compute_adaptive_spacing(
            slab_thickness_m=0.25,
            floor_height_m=2.80,
            shore_capacity_kn=12.0,
        )
        assert 0.90 < spacing < 1.10

    def test_very_thick_slab_low_capacity(self):
        """Laje 30cm, ESC450@3.50m (derateada) → espaçamento bem reduzido."""
        # carga = (25*0.30 + 0.50 + 1.50) * 1.4 = (7.5+0.5+1.5)*1.4 = 13.3 kN/m²
        # ESC450@3.50m ≈ 13.0 kN (derateada)
        # area_trib = 13.0 / 13.3 ≈ 0.977 m²
        # spacing = sqrt(0.977) ≈ 0.989m → cap pelo teto 1.10m (faixa 25-30cm) → fica ~0.989m
        # Mas if capacity is lower: 8.0 kN → area_trib = 8.0/13.3 = 0.60 → sqrt = 0.775
        spacing = compute_adaptive_spacing(
            slab_thickness_m=0.30,
            floor_height_m=3.50,
            shore_capacity_kn=8.0,
        )
        assert 0.60 < spacing < 0.85

    def test_respects_minimum_spacing(self):
        """Carga muito alta → não pode ser menor que ESPACAMENTO_MIN (0.30m)."""
        spacing = compute_adaptive_spacing(
            slab_thickness_m=0.50,
            floor_height_m=4.0,
            shore_capacity_kn=1.0,
        )
        assert spacing >= 0.30

    def test_respects_table_ceiling(self):
        """Capacidade muito alta não ultrapassa teto da tabela."""
        spacing = compute_adaptive_spacing(
            slab_thickness_m=0.12,
            floor_height_m=2.0,
            shore_capacity_kn=50.0,
        )
        assert spacing <= 1.30  # Teto para 10-16cm

    def test_zero_capacity_returns_table_value(self):
        """Capacidade zero → fallback para teto da tabela."""
        spacing = compute_adaptive_spacing(
            slab_thickness_m=0.12,
            floor_height_m=2.0,
            shore_capacity_kn=0.0,
        )
        assert spacing == 1.30

    def test_adaptive_varies_with_thickness(self):
        """Laje mais espessa deve dar espaçamento menor (mais carga)."""
        cap = 12.0
        s_thin = compute_adaptive_spacing(0.10, 2.80, cap)
        s_thick = compute_adaptive_spacing(0.30, 2.80, cap)
        assert s_thin > s_thick
