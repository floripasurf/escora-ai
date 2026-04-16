"""Tests for beam_calculator — Rule 14 (continuous beam over 3 supports).

NBR 6120 / Orguel manual Regra 14: a continuous beam over 3 equal spans
transfers 10/8·q·L to the central support and 3/8·q·L to the end supports
(vs. q·L and 0.5·q·L in biapoiado analysis). Practical effect: the shore
closest to the central apoio must be dimensioned for 25% more load.

Scope (per confirmed plan): applied ONLY to beams with len(support_positions)
== 3. Beams with 4+ supports are untouched (manual only covers the 3-apoio
case; not extrapolating).
"""
import pytest

from src.engine.beam_calculator import distribute_beam_shores
from src.models.shore import ShoreCatalogEntry


def _shore() -> ShoreCatalogEntry:
    return ShoreCatalogEntry(
        id="ESC450",
        manufacturer="Orguel",
        model="ESC450",
        height_min_m=3.00,
        height_max_m=4.50,
        load_capacity_kn=22.0,
        weight_kg=18.0,
        tube_external_mm=60.0,
        tube_internal_mm=48.0,
        base_plate_mm=120.0,
        price_reference_brl=250.0,
    )


class TestRule14ContinuousBeamThreeSupports:
    def test_central_shore_load_amplified_by_10_over_8(self):
        """Viga 10m com 3 apoios em [0, 5, 10]: escora mais próxima do
        apoio central recebe carga × 10/8 = 1.25× a carga uniforme."""
        shore = _shore()
        q = 10.0  # kN/m

        shores_uniform, _, _ = distribute_beam_shores(
            beam_length_m=10.0,
            beam_width_m=0.20,
            beam_height_m=0.40,
            shore=shore,
            total_linear_load_kn_m=q,
            support_positions=[0.0, 10.0],  # só 2 apoios → biapoiado
        )
        uniform_load = shores_uniform[0].load_applied_kn

        shores_3, _, _ = distribute_beam_shores(
            beam_length_m=10.0,
            beam_width_m=0.20,
            beam_height_m=0.40,
            shore=shore,
            total_linear_load_kn_m=q,
            support_positions=[0.0, 5.0, 10.0],  # 3 apoios → contínuo
        )

        # Encontrar escora mais próxima do apoio central (x=5.0)
        central_shore = min(shores_3, key=lambda s: abs(s.x - 5.0))
        other_shores = [s for s in shores_3 if s is not central_shore]

        # Escora central deve ter carga 1.25× a uniforme
        assert central_shore.load_applied_kn == pytest.approx(
            uniform_load * 1.25, rel=0.15
        ), (
            f"central_shore carga={central_shore.load_applied_kn} deveria ser "
            f"~1.25×{uniform_load}={uniform_load * 1.25}"
        )
        # Utilização também amplificada
        assert central_shore.utilization_ratio > max(
            s.utilization_ratio for s in other_shores
        )

    def test_two_supports_beam_unchanged(self):
        """Viga com 2 apoios (biapoiado) — nenhuma escora é amplificada."""
        shore = _shore()
        shores, _, _ = distribute_beam_shores(
            beam_length_m=6.0,
            beam_width_m=0.20,
            beam_height_m=0.40,
            shore=shore,
            total_linear_load_kn_m=10.0,
            support_positions=[0.0, 6.0],
        )
        loads = [s.load_applied_kn for s in shores]
        assert max(loads) == pytest.approx(min(loads), rel=0.01), (
            "Biapoiado: todas as escoras devem ter carga uniforme"
        )

    def test_four_supports_beam_unchanged(self):
        """Viga com 4+ apoios — sem amplificação (fora do escopo do Rule 14)."""
        shore = _shore()
        shores, _, _ = distribute_beam_shores(
            beam_length_m=15.0,
            beam_width_m=0.20,
            beam_height_m=0.40,
            shore=shore,
            total_linear_load_kn_m=10.0,
            support_positions=[0.0, 5.0, 10.0, 15.0],
        )
        loads = [s.load_applied_kn for s in shores]
        # Todas uniformes (sem regra de contínuo aplicada)
        assert max(loads) == pytest.approx(min(loads), rel=0.01)
