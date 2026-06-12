"""Plumbing do perfil de metodologia (§28.9) no pipeline de calculo.

Tarefas (2026-06):
1. Derivacao de slab_layout_mode + parametros do perfil (runner).
2. Passo sob viga configuravel (`passo_sob_viga_m`, gold standard 0.55-0.65
   vs DOCX 0.80 — conflito §23.9).
3. Cobertura torre-first (gold standard §28.8 item 10).
"""

import math

import pytest

from src.models.methodology import (
    MethodologyProfile,
    PROFILE_GRID_LEGACY,
    PROFILE_ORGUEL_LINE_FIRST,
)
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.shore import SupportType
from src.pipeline.runner import _is_cobertura_level, derive_methodology_params
from src.pipeline.stage_calculate import run_calculation


def _beam(x1, y1, x2, y2, width=0.14, height=0.40):
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    return ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[(x1, y1), (x2, y2)],
        score_geometric=0.85, score_textual=0.0, score_final=0.75,
        section_width_m=width, section_height_m=height, length_m=length,
    )


def _pillar(cx, cy, w=0.20, h=0.40):
    return ClassifiedElement(
        element_type=ElementType.PILLAR,
        geometry=[(cx, cy)],
        score_geometric=0.80, score_textual=0.0, score_final=0.70,
        section_width_m=w, section_height_m=h,
    )


class TestIsCoberturaLevel:
    def test_full_word(self):
        assert _is_cobertura_level("COBERTURA")
        assert _is_cobertura_level("FÔRMA DA COBERTURA - NÍVEL +1330,40m")
        assert _is_cobertura_level("Coberta")

    def test_cob_token(self):
        assert _is_cobertura_level("CVS-COB-FOR-006")
        assert _is_cobertura_level("COB.")

    def test_negatives(self):
        assert not _is_cobertura_level("TIPO 1")
        assert not _is_cobertura_level("DEFAULT")
        assert not _is_cobertura_level("COBOGO")
        assert not _is_cobertura_level(None)
        assert not _is_cobertura_level("")


class TestDeriveMethodologyParams:
    def test_grid_default_profile_keeps_legacy(self):
        w = []
        p = derive_methodology_params(PROFILE_GRID_LEGACY, None, ["TIPO 1"], w)
        assert p["slab_layout_mode"] == "grid"
        assert p["passo_sob_viga_m"] is None
        assert p["cobertura_torre_first"] is False
        assert p["min_dist_escoras_m"] == pytest.approx(0.30)

    def test_explicit_flag_wins_over_profile(self):
        w = []
        p = derive_methodology_params(
            PROFILE_ORGUEL_LINE_FIRST, "grid", ["TIPO 1"], w,
        )
        assert p["slab_layout_mode"] == "grid"
        # Perfil line_first NAO ativo (engenheiro forcou grid): passo legado
        assert p["passo_sob_viga_m"] is None

    def test_line_first_profile_derives_mode_and_passo(self):
        w = []
        p = derive_methodology_params(
            PROFILE_ORGUEL_LINE_FIRST, None, ["TIPO 1"], w,
        )
        assert p["slab_layout_mode"] == "line_first"
        assert p["passo_sob_viga_m"] == pytest.approx(0.60)
        assert any("§28.9" in msg for msg in w)

    def test_explicit_line_first_with_grid_profile_keeps_legacy_passo(self):
        """Compat: testes/execucoes existentes com slab_layout_mode=
        'line_first' explicito (perfil default grid) nao mudam de passo."""
        w = []
        p = derive_methodology_params(
            PROFILE_GRID_LEGACY, "line_first", ["TIPO 1"], w,
        )
        assert p["slab_layout_mode"] == "line_first"
        assert p["passo_sob_viga_m"] is None
        assert p["cobertura_torre_first"] is False

    def test_cobertura_applied_when_level_is_cobertura(self):
        w = []
        p = derive_methodology_params(
            PROFILE_ORGUEL_LINE_FIRST, None, ["COBERTURA"], w,
        )
        assert p["cobertura_torre_first"] is True
        assert any("torre-first aplicado" in msg for msg in w)

    def test_cobertura_ambiguous_level_keeps_current_with_warning(self):
        w = []
        p = derive_methodology_params(
            PROFILE_ORGUEL_LINE_FIRST, None, ["DEFAULT"], w,
        )
        assert p["cobertura_torre_first"] is False
        assert any("ambigua" in msg for msg in w)

    def test_cobertura_named_non_cobertura_level_not_applied(self):
        w = []
        p = derive_methodology_params(
            PROFILE_ORGUEL_LINE_FIRST, None, ["TIPO 2"], w,
        )
        assert p["cobertura_torre_first"] is False

    def test_cobertura_padrao_never_applies(self):
        w = []
        profile = MethodologyProfile(
            laje_layout="line_first", cobertura="padrao",
        )
        p = derive_methodology_params(profile, None, ["COBERTURA"], w)
        assert p["cobertura_torre_first"] is False


def _beam_gaps_along_axis(br):
    """Gaps consecutivos das escoras projetadas no eixo da viga."""
    (x1, y1), (x2, y2) = br.beam.geometry[0], br.beam.geometry[-1]
    L = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    ts = sorted((s.x - x1) * ux + (s.y - y1) * uy for s in br.shores)
    return [b - a for a, b in zip(ts, ts[1:])]


class TestPassoSobViga:
    def _run(self, **kwargs):
        elements = [
            _beam(0, 5, 10, 5),
            _pillar(0.1, 5.0), _pillar(9.9, 5.0),
        ]
        return run_calculation(elements, pe_direito_m=2.80, **kwargs)

    def test_passo_060_densifies_beam_shores(self):
        base = self._run()
        denser = self._run(passo_sob_viga_m=0.60)
        assert len(base.beam_results) == 1
        assert len(denser.beam_results) == 1
        assert (
            len(denser.beam_results[0].shores)
            > len(base.beam_results[0].shores)
        )
        # Gaps interiores respeitam o passo (folga p/ apoios e dedup)
        gaps = _beam_gaps_along_axis(denser.beam_results[0])
        assert gaps and max(gaps) <= 0.65 + 1e-6

    def test_default_none_keeps_legacy_spacing(self):
        base = self._run()
        explicit_none = self._run(passo_sob_viga_m=None)
        assert (
            len(base.beam_results[0].shores)
            == len(explicit_none.beam_results[0].shores)
        )

    def test_passo_propagated_to_result_for_bom(self):
        result = self._run(passo_sob_viga_m=0.60)
        assert result.passo_sob_viga_m == pytest.approx(0.60)
        assert self._run().passo_sob_viga_m is None


class TestCoberturaTorreFirst:
    def _run(self, **kwargs):
        elements = [
            _beam(0, 5, 10, 5),
            _pillar(0.1, 5.0), _pillar(9.9, 5.0),
        ]
        return run_calculation(elements, pe_direito_m=2.80, **kwargs)

    def test_beams_use_towers_at_125_165(self):
        result = self._run(
            cobertura_torre_first=True,
            slab_layout_mode="line_first",
            passo_sob_viga_m=0.60,
        )
        assert len(result.beam_results) == 1
        br = result.beam_results[0]
        assert br.decision_rule == "rule-cobertura-torre-first"
        towers = [
            s for s in br.shores
            if getattr(s, "support_type", None) == SupportType.TOWER
        ]
        # Torres como apoio PRINCIPAL (escoras telescopicas apenas
        # complementares — aqui nenhuma e necessaria)
        assert len(towers) >= 2
        assert len(towers) == len(br.shores)
        gaps = _beam_gaps_along_axis(br)
        assert gaps and max(gaps) <= 1.65 + 0.05
        assert any("torre-first" in w.lower() for w in result.warnings)

    def test_default_off_keeps_mixed_decision(self):
        result = self._run()
        br = result.beam_results[0]
        assert br.decision_rule != "rule-cobertura-torre-first"

    def test_slabs_stay_line_first(self):
        """Cobertura torre-first muda as VIGAS; lajes seguem line-first."""
        elements = [
            _beam(0, 0, 10, 0), _beam(0, 6, 10, 6),
            _beam(0, 0, 0, 6), _beam(10, 0, 10, 6),
            _pillar(0, 0), _pillar(10, 0), _pillar(0, 6), _pillar(10, 6),
        ]
        result = run_calculation(
            elements, pe_direito_m=2.80,
            slab_layout_mode="line_first",
            cobertura_torre_first=True,
        )
        assert result.slab_results
        assert all(
            getattr(sr, "layout_mode", "grid") == "line_first"
            for sr in result.slab_results
            if sr.shores
        )
