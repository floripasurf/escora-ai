"""Pendência tipada no fallback de capacidade (AGENTS.md: no silent fallbacks).

Antes: `except Exception: cap_kn = shore.load_capacity_kn` — falha no derate
de Euler caía silenciosamente para a capacidade NOMINAL (maior), podendo
subdimensionar o escoramento. Agora o fallback carrega uma pendência que o
runner converte em requires_review.
"""
import pytest

from src.models.shore import ShoreCatalogEntry
from src.pipeline.stage_calculate import (
    CAPACITY_PENDENCY_PREFIX,
    _effective_capacity_kn,
)
from src.utils.constants import Q_PROJETO_FALLBACK_LAJE_KN_M2


@pytest.fixture
def shore():
    return ShoreCatalogEntry(
        id="ESC2000-3100",
        manufacturer="Orguel",
        model="ESC2000-3100",
        height_min_m=2.0,
        height_max_m=3.1,
        load_capacity_kn=20.0,
        weight_kg=17.0,
        tube_external_mm=60.0,
        tube_internal_mm=48.0,
        base_plate_mm=150.0,
        price_reference_brl=100.0,
        capacity_curve=[(2.0, 20.0), (3.1, 12.0)],
    )


def test_known_height_derates_without_pendency(shore):
    cap, pendency = _effective_capacity_kn(shore, 3.1)
    assert cap == pytest.approx(12.0)
    assert pendency is None


def test_unknown_height_uses_nominal_with_pendency(shore):
    cap, pendency = _effective_capacity_kn(shore, None)
    assert cap == pytest.approx(20.0)
    assert pendency is not None
    assert pendency.startswith(CAPACITY_PENDENCY_PREFIX)
    assert "NOMINAL" in pendency


def test_derate_failure_uses_nominal_with_pendency(shore):
    class ExplodingShore:
        model = "X"
        load_capacity_kn = 30.0

        def effective_capacity(self, h):
            raise ValueError("curva corrompida")

    cap, pendency = _effective_capacity_kn(ExplodingShore(), 2.8)
    assert cap == pytest.approx(30.0)
    assert pendency is not None
    assert pendency.startswith(CAPACITY_PENDENCY_PREFIX)


def test_fallback_load_constant_traceable():
    # Derivação documentada em constants.py: laje 12 cm default.
    assert Q_PROJETO_FALLBACK_LAJE_KN_M2 == pytest.approx(7.7)
