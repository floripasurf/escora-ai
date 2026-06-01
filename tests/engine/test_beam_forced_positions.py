"""Tests for forced shore positions in distribute_beam_shores (Orguel Q3, A4).

Locadora rule (Q3): "Toda interseção de viga sem pilar deve ter torre/escora".
The pipeline computes beam-beam intersections that lack a pillar and feeds
them as `forced_positions` to the shore distributor, which must guarantee
one shore within tolerance of each forced point.
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


class TestBeamForcedPositions:
    def test_forced_position_becomes_a_shore(self):
        """Forced interseção no meio da viga garante uma escora ali."""
        shores, _, _ = distribute_beam_shores(
            beam_length_m=8.0,
            beam_width_m=0.20,
            beam_height_m=0.40,
            shore=_shore(),
            total_linear_load_kn_m=10.0,
            support_positions=[0.0, 8.0],
            forced_positions=[4.0],
        )
        # Deve haver uma escora a no máximo 0.25m da posição forçada
        distances = [abs(s.x - 4.0) for s in shores]
        assert min(distances) < 0.25, (
            f"Esperada escora próxima de x=4.0, escoras={[s.x for s in shores]}"
        )

    def test_forced_position_near_existing_shore_is_no_op(self):
        """Se já existe escora perto da posição forçada, não duplica."""
        shores_without, _, _ = distribute_beam_shores(
            beam_length_m=6.0,
            beam_width_m=0.20,
            beam_height_m=0.40,
            shore=_shore(),
            total_linear_load_kn_m=10.0,
            support_positions=[0.0, 6.0],
        )
        shores_with, _, _ = distribute_beam_shores(
            beam_length_m=6.0,
            beam_width_m=0.20,
            beam_height_m=0.40,
            shore=_shore(),
            total_linear_load_kn_m=10.0,
            support_positions=[0.0, 6.0],
            forced_positions=[shores_without[0].x + 0.05],  # já bem perto
        )
        # Não aumenta o número de escoras significativamente
        assert len(shores_with) <= len(shores_without) + 0

    def test_multiple_forced_positions_all_respected(self):
        shores, _, _ = distribute_beam_shores(
            beam_length_m=12.0,
            beam_width_m=0.20,
            beam_height_m=0.40,
            shore=_shore(),
            total_linear_load_kn_m=10.0,
            support_positions=[0.0, 12.0],
            forced_positions=[3.0, 7.5],
        )
        for forced_x in (3.0, 7.5):
            distances = [abs(s.x - forced_x) for s in shores]
            assert min(distances) < 0.25, (
                f"Forçada x={forced_x} sem escora próxima: {[s.x for s in shores]}"
            )

    def test_no_forced_positions_default_behavior_unchanged(self):
        """Chamada sem forced_positions não altera comportamento existente."""
        shores_default, _, _ = distribute_beam_shores(
            beam_length_m=6.0,
            beam_width_m=0.20,
            beam_height_m=0.40,
            shore=_shore(),
            total_linear_load_kn_m=10.0,
            support_positions=[0.0, 6.0],
        )
        shores_empty, _, _ = distribute_beam_shores(
            beam_length_m=6.0,
            beam_width_m=0.20,
            beam_height_m=0.40,
            shore=_shore(),
            total_linear_load_kn_m=10.0,
            support_positions=[0.0, 6.0],
            forced_positions=[],
        )
        assert len(shores_default) == len(shores_empty)
