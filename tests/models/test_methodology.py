"""Tests do perfil de metodologia por locadora (manual §28.9)."""

import json

import pytest

from src.models.methodology import (
    MethodologyProfile,
    PROFILE_GRID_LEGACY,
    PROFILE_ORGUEL_LINE_FIRST,
    describe_methodology,
    load_methodology,
    profile_from_dict,
)


class TestTraceability:
    """Rastreabilidade (§28.9): to_dict() + describe_methodology()."""

    def test_to_dict_has_all_profile_fields(self):
        d = PROFILE_ORGUEL_LINE_FIRST.to_dict()
        assert d["laje_layout"] == "line_first"
        assert d["passo_sob_viga_m"] == pytest.approx(0.60)
        assert d["cobertura"] == "torre_first"
        assert d["barrotes_escopo"] == "cliente"
        # cobre todos os campos do perfil (7 base + barrotes_escopo, Fase 5)
        assert set(d) == {
            "laje_layout", "eixo_guias", "escoras_equidistantes",
            "passo_sob_viga_m", "tripes_fracao", "cobertura",
            "min_dist_escoras_m", "barrotes_escopo",
        }

    def test_describe_line_first(self):
        m = {
            **PROFILE_ORGUEL_LINE_FIRST.to_dict(),
            "efetivo": {"slab_layout_mode": "line_first",
                        "passo_sob_viga_m": 0.60,
                        "cobertura_torre_first": True},
            "origem": "perfil_locadora",
        }
        s = describe_methodology(m)
        assert "Line-first Orguel" in s
        assert "barrotes por conta do cliente" in s
        assert "0.60 m" in s
        assert "torre-first" in s
        assert "override" not in s

    def test_describe_grid_override(self):
        s = describe_methodology(
            {"laje_layout": "grid_vm_duplo", "efetivo": {}, "origem": "override"}
        )
        assert "Grid VM duplo" in s
        assert "override do projeto" in s

    def test_describe_none_is_safe(self):
        assert describe_methodology(None).startswith("Metodologia:")


class TestBarrotesExplicit:
    """Fase 5: barrotes (madeira) como atributo explicito da locadora.

    Decisao de produto (2026-06): barrotes_escopo descreve SO a camada de
    barrotes de madeira do cliente; NAO controla as secundarias VM metalicas
    (guias estruturais do engine).
    """

    def test_grid_defaults_match_class_default(self):
        assert PROFILE_GRID_LEGACY == MethodologyProfile()
        assert PROFILE_GRID_LEGACY.barrotes_escopo == "locadora"

    def test_orguel_barrotes_cliente(self):
        assert PROFILE_ORGUEL_LINE_FIRST.barrotes_escopo == "cliente"

    def test_line_first_json_inherits_barrotes_cliente(self):
        p = profile_from_dict({"laje_layout": "line_first"})
        assert p.barrotes_escopo == "cliente"

    def test_explicit_override_of_escopo(self):
        """Locadora line_first que fornece barrotes de madeira no servico."""
        p = profile_from_dict({
            "laje_layout": "line_first",
            "barrotes_escopo": "locadora",
        })
        assert p.barrotes_escopo == "locadora"

    def test_invalid_escopo_kept_default(self):
        assert profile_from_dict({"barrotes_escopo": "xxx"}).barrotes_escopo == "locadora"

    def test_describe_grid_says_locadora(self):
        s = describe_methodology(PROFILE_GRID_LEGACY.to_dict())
        assert "barrotes por conta da locadora" in s

    def test_describe_fallback_when_escopo_absent(self):
        # dados antigos sem barrotes_escopo: cai na inferencia por laje_layout
        assert "cliente" in describe_methodology({"laje_layout": "line_first"})
        assert "locadora" in describe_methodology({"laje_layout": "grid_vm_duplo"})


class TestDefaults:
    def test_grid_legacy_defaults_match_28_9_table(self):
        p = PROFILE_GRID_LEGACY
        assert p.laje_layout == "grid_vm_duplo"
        assert p.eixo_guias == "unico_pavimento"
        assert p.escoras_equidistantes is True
        assert p.passo_sob_viga_m == pytest.approx(0.80)
        assert p.tripes_fracao == pytest.approx(0.30)
        assert p.cobertura == "padrao"
        assert p.min_dist_escoras_m == pytest.approx(0.30)
        assert p.slab_layout_mode == "grid"

    def test_orguel_line_first_profile(self):
        p = PROFILE_ORGUEL_LINE_FIRST
        assert p.laje_layout == "line_first"
        assert p.passo_sob_viga_m == pytest.approx(0.60)
        assert p.cobertura == "torre_first"
        assert p.slab_layout_mode == "line_first"


class TestProfileFromDict:
    def test_empty_dict_returns_grid_legacy(self):
        assert profile_from_dict({}) == PROFILE_GRID_LEGACY
        assert profile_from_dict(None) == PROFILE_GRID_LEGACY

    def test_line_first_layout_inherits_line_first_base(self):
        """Um JSON que so define laje_layout herda os defaults do perfil
        line-first (passo 0.60, cobertura torre_first)."""
        p = profile_from_dict({"laje_layout": "line_first"})
        assert p.passo_sob_viga_m == pytest.approx(0.60)
        assert p.cobertura == "torre_first"

    def test_explicit_fields_override_base(self):
        p = profile_from_dict({
            "laje_layout": "line_first",
            "passo_sob_viga_m": 0.55,
            "cobertura": "padrao",
            "tripes_fracao": 0.60,
            "eixo_guias": "por_painel",
            "escoras_equidistantes": False,
            "min_dist_escoras_m": 0.25,
        })
        assert p.passo_sob_viga_m == pytest.approx(0.55)
        assert p.cobertura == "padrao"
        assert p.tripes_fracao == pytest.approx(0.60)
        assert p.eixo_guias == "por_painel"
        assert p.escoras_equidistantes is False
        assert p.min_dist_escoras_m == pytest.approx(0.25)

    def test_invalid_values_fall_back_to_defaults(self):
        p = profile_from_dict({
            "laje_layout": "doka_124",       # pendente — invalido hoje
            "eixo_guias": "diagonal",
            "cobertura": "voadora",
            "passo_sob_viga_m": -1.0,
            "tripes_fracao": 7,
            "escoras_equidistantes": "sim",
            "min_dist_escoras_m": 99,
        })
        assert p == PROFILE_GRID_LEGACY

    def test_unknown_keys_ignored(self):
        p = profile_from_dict({"barrote": "VM80", "desenha_barrotes": True})
        assert p == PROFILE_GRID_LEGACY


def _write_registry(tmp_path, locadoras):
    path = tmp_path / "locadoras.json"
    path.write_text(
        json.dumps({"version": 1, "locadoras": locadoras}),
        encoding="utf-8",
    )
    return str(path)


class TestLoadMethodology:
    def test_missing_file_returns_defaults(self, tmp_path):
        p = load_methodology(
            branch_id="qualquer", path=str(tmp_path / "nao_existe.json"),
        )
        assert p == PROFILE_GRID_LEGACY

    def test_branch_without_metodologia_returns_defaults(self, tmp_path):
        path = _write_registry(tmp_path, [{
            "id": "orguel", "name": "Orguel",
            "branches": [{"id": "orguel-sjc", "branch_name": "SJC",
                          "inventory_name": "orguel_sjc"}],
        }])
        p = load_methodology(branch_id="orguel-sjc", path=path)
        assert p == PROFILE_GRID_LEGACY

    def test_locadora_level_metodologia(self, tmp_path):
        path = _write_registry(tmp_path, [{
            "id": "orguel", "name": "Orguel",
            "metodologia": {"laje_layout": "line_first"},
            "branches": [{"id": "orguel-sjc", "branch_name": "SJC",
                          "inventory_name": "orguel_sjc"}],
        }])
        p = load_methodology(branch_id="orguel-sjc", path=path)
        assert p.laje_layout == "line_first"
        assert p.passo_sob_viga_m == pytest.approx(0.60)

    def test_branch_metodologia_overrides_locadora(self, tmp_path):
        path = _write_registry(tmp_path, [{
            "id": "orguel", "name": "Orguel",
            "metodologia": {"laje_layout": "line_first",
                            "passo_sob_viga_m": 0.60},
            "branches": [{"id": "orguel-sjc", "branch_name": "SJC",
                          "inventory_name": "orguel_sjc",
                          "metodologia": {"passo_sob_viga_m": 0.55}}],
        }])
        p = load_methodology(branch_id="orguel-sjc", path=path)
        assert p.laje_layout == "line_first"
        assert p.passo_sob_viga_m == pytest.approx(0.55)

    def test_lookup_by_locadora_id(self, tmp_path):
        path = _write_registry(tmp_path, [{
            "id": "orguel", "name": "Orguel",
            "metodologia": {"cobertura": "torre_first"},
            "branches": [],
        }])
        p = load_methodology(locadora_id="orguel", path=path)
        assert p.cobertura == "torre_first"

    def test_unknown_branch_returns_defaults(self, tmp_path):
        path = _write_registry(tmp_path, [{
            "id": "orguel", "name": "Orguel",
            "metodologia": {"laje_layout": "line_first"},
            "branches": [{"id": "orguel-sjc", "branch_name": "SJC",
                          "inventory_name": "orguel_sjc"}],
        }])
        p = load_methodology(branch_id="outra-branch", path=path)
        assert p == PROFILE_GRID_LEGACY

    def test_env_override_file(self, tmp_path, monkeypatch):
        path = _write_registry(tmp_path, [{
            "id": "loc", "name": "Loc",
            "branches": [{"id": "loc-b", "branch_name": "B",
                          "inventory_name": "default",
                          "metodologia": {"laje_layout": "line_first"}}],
        }])
        monkeypatch.setenv("ESCORA_LOCADORAS_FILE", path)
        p = load_methodology(branch_id="loc-b")
        assert p.laje_layout == "line_first"

    def test_corrupt_json_returns_defaults(self, tmp_path):
        path = tmp_path / "locadoras.json"
        path.write_text("{nao-e-json", encoding="utf-8")
        p = load_methodology(branch_id="x", path=str(path))
        assert p == PROFILE_GRID_LEGACY
