"""Testes do h_pilha — manual §13.6 (pendência 16, Orguel p.89)."""

from src.engine.beam_calculator import (
    compute_h_pilha,
    estimate_beam_shore_height,
)


class TestComputeHPilha:
    def test_canonico_orguel_14mm(self):
        """Orguel p.89: VM130 + VM80 + compensado 14 mm = 0.224 m."""
        assert abs(compute_h_pilha(e_compensado_m=0.014) - 0.224) < 1e-9

    def test_default_18mm(self):
        """Compensado default do pipeline (18 mm) -> 0.228 m."""
        assert abs(compute_h_pilha() - 0.228) < 1e-9

    def test_pilha_doka_h20(self):
        """Pilha H20 + H20 (0.20 + 0.20) + 18 mm = 0.418 m."""
        h = compute_h_pilha(h_guia_m=0.20, h_barrote_m=0.20)
        assert abs(h - 0.418) < 1e-9


class TestBeamShoreHeight:
    def test_sem_pilha_mantem_comportamento(self):
        """Escora com forcado direto no fundo da viga (default)."""
        assert abs(estimate_beam_shore_height(3.30, 0.90) - 2.40) < 1e-9

    def test_torre_sob_viga_canonico(self):
        """Orguel p.89: (3.30 - 0.90 - 0.224) = 2.176 m."""
        h = estimate_beam_shore_height(
            3.30, 0.90, h_pilha_m=compute_h_pilha(e_compensado_m=0.014)
        )
        assert abs(h - 2.176) < 1e-9

    def test_torre_em_laje_canonico(self):
        """Orguel p.89: (3.30 - 0.10 - 0.224) = 2.976 m (impresso "2.99")."""
        h = 3.30 - 0.10 - compute_h_pilha(e_compensado_m=0.014)
        assert abs(h - 2.976) < 1e-9
