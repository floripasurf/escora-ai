"""Testes de acessórios e estabilidade de torres — pendências 23 e 26.

Fontes: manual §13.7 (esbeltez 4:1 JAU p.04; gatilhos 8/20 m; interligação
JAU p.11), §14 (tripés, JAU pág. 70) e OP-028 (folga de desforma 10 cm).
"""

from src.engine.accessories import (
    DEFORM_CLEARANCE_MIN_M,
    check_deform_clearance,
    check_tower_stability,
    count_tripods,
    tower_tie_groups,
)


class TestTripods:
    def test_linha_simples_leva_2(self):
        """1 linha de viga com 5 escoras: tripé nas 2 extremidades."""
        line = [(i * 0.8, 0.0) for i in range(5)]
        assert count_tripods([line]) == 2

    def test_escora_unica_leva_1(self):
        assert count_tripods([[(0.0, 0.0)]]) == 1

    def test_transpasse_soma_1(self):
        line_a = [(i * 0.8, 0.0) for i in range(4)]
        line_b = [(3.2 + i * 0.8, 0.0) for i in range(4)]
        # 2 linhas (4 tripés) + 1 transpasse entre elas = 5
        assert count_tripods([line_a, line_b], transpasse_count=1) == 5

    def test_linhas_vazias_nao_contam(self):
        assert count_tripods([[], []]) == 0


class TestDeformClearance:
    def test_folga_suficiente(self):
        r = check_deform_clearance(total_travel_m=0.30, used_travel_m=0.15)
        assert r.ok and abs(r.clearance_m - 0.15) < 1e-9

    def test_folga_insuficiente(self):
        r = check_deform_clearance(total_travel_m=0.30, used_travel_m=0.25)
        assert not r.ok
        assert "OP-028" in r.message

    def test_limite_exato_passa(self):
        r = check_deform_clearance(0.30, 0.30 - DEFORM_CLEARANCE_MIN_M)
        assert r.ok


class TestTowerStability:
    def test_torre_dentro_da_esbeltez(self):
        r = check_tower_stability(height_m=3.0, base_min_dim_m=1.0)
        assert r.ok and not r.needs_bracing

    def test_esbeltez_estourada(self):
        """JAU p.04: base 1.00 m -> altura máxima 4.00 m sem estaiamento."""
        r = check_tower_stability(height_m=4.5, base_min_dim_m=1.0)
        assert r.needs_bracing and not r.ok

    def test_base_maior_permite_mais_altura(self):
        r = check_tower_stability(height_m=5.5, base_min_dim_m=1.5)
        assert not r.needs_bracing

    def test_gatilho_revisao_8m(self):
        r = check_tower_stability(height_m=9.0, base_min_dim_m=2.5)
        assert r.needs_review and not r.is_special

    def test_gatilho_especial_20m(self):
        r = check_tower_stability(height_m=21.0, base_min_dim_m=6.0)
        assert r.is_special and not r.ok

    def test_base_desconhecida_usa_default_1m(self):
        r = check_tower_stability(height_m=4.5, base_min_dim_m=0.0)
        assert r.needs_bracing  # 4.5/1.0 > 4


class TestTowerTieGroups:
    def test_torres_proximas_agrupam(self):
        groups = tower_tie_groups([(0, 0), (2.0, 0), (10, 10)])
        assert len(groups) == 1
        assert sorted(groups[0]) == [0, 1]

    def test_cadeia_transitiva(self):
        """A-B e B-C próximos -> grupo único A,B,C."""
        groups = tower_tie_groups([(0, 0), (2.4, 0), (4.8, 0)])
        assert len(groups) == 1
        assert sorted(groups[0]) == [0, 1, 2]

    def test_torres_isoladas_sem_grupo(self):
        assert tower_tie_groups([(0, 0), (5, 5), (10, 0)]) == []

    def test_vazio(self):
        assert tower_tie_groups([]) == []
