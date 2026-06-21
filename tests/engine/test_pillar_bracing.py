"""Testes do BOM de travamento de pilares — manual §15.1 (pendência 19).

Exemplos canônicos Orguel p.62-64, conferidos visualmente em 2026-06-11:
- 40x70 (p.63):  VM50 1000 = 20x (5 níveis x 4 lados — CORRIGIDO, era 10x),
                 tirante 1000 = 10x, tirante 1500 = 10x;
- 25/75 (p.62):  VM80 1550 = 10x (5 níveis x 2 lados), tirante 650 = 10x,
                 espaçamentos 80/80/80/80 + 20 cm na base;
- 25x100 (p.64): VM80 1550 = 16x (8 níveis x 2 lados, ~33 cm),
                 tirante 650 = 16x, + 2 VM verticais + 3 tirantes 1000.
"""

from src.engine.vm50_bracing import (
    PILLAR_SPACING_DEFAULT_M,
    PILLAR_SPACING_DENSE_M,
    compute_pillar_bracing,
    pillar_bracing_spacing_m,
    select_tirante_mm,
    select_vm_length_mm,
)


class TestSelectors:
    def test_tirante_canonicos(self):
        """Orguel p.62-64: 25 cm → 650; 40 → 1000; 70/75 → 1500."""
        assert select_tirante_mm(0.25) == 650
        assert select_tirante_mm(0.40) == 1000
        assert select_tirante_mm(0.70) == 1500

    def test_vm_canonicos(self):
        """Orguel p.62-64: face 70 → VM 1000; faces 75 e 100 → VM 1550."""
        assert select_vm_length_mm(0.70) == 1000
        assert select_vm_length_mm(0.75) == 1550
        assert select_vm_length_mm(1.00) == 1550


class TestSpacing:
    def test_pilar_baixo_usa_80cm_com_alerta(self):
        spacing, warnings = pillar_bracing_spacing_m(3.40, 0.70)
        assert spacing == PILLAR_SPACING_DEFAULT_M
        assert warnings, "default de 80 cm deve vir com alerta de forma"

    def test_face_larga_densifica(self):
        spacing, _ = pillar_bracing_spacing_m(2.85, 1.00)
        assert spacing == PILLAR_SPACING_DENSE_M

    def test_pilar_alto_densifica(self):
        spacing, _ = pillar_bracing_spacing_m(4.20, 0.40)
        assert spacing == PILLAR_SPACING_DENSE_M


class TestCanonico40x70:
    """Orguel p.63 — VM50 1000 20x, tirante 1000 10x, tirante 1500 10x."""

    def test_bom(self):
        spec = compute_pillar_bracing(0.40, 0.70, 3.40)
        assert spec.levels == 5
        assert spec.sides_per_level == 4
        assert spec.vm_profile == "VM50"
        assert spec.vm_length_mm == 1000
        assert spec.vm_count == 20  # CORRIGIDO 2026-06-11 (era 10x)
        assert spec.tirantes[1000] == 10
        assert spec.tirantes[1500] == 10
        assert spec.vertical_vm_count == 0


class TestCanonico25x75:
    """Orguel p.62 — VM80 1550 10x, tirante 650 10x."""

    def test_bom(self):
        spec = compute_pillar_bracing(0.25, 0.75, 3.40)
        assert spec.levels == 5
        assert spec.sides_per_level == 2
        assert spec.vm_profile == "VM80"
        assert spec.vm_length_mm == 1550
        assert spec.vm_count == 10
        assert spec.tirantes[650] == 10
        assert spec.vertical_vm_count == 0


class TestCanonico25x100:
    """Orguel p.64 — VM80 1550 16x, tirante 650 16x, 2 VM vert + 3 tir 1000."""

    def test_bom(self):
        spec = compute_pillar_bracing(0.25, 1.00, 2.85)
        assert spec.levels == 8
        assert spec.sides_per_level == 2
        assert spec.vm_profile == "VM80"
        assert spec.vm_length_mm == 1550
        assert spec.vm_count == 16
        assert spec.tirantes[650] == 16
        assert spec.vertical_vm_count == 2
        assert spec.vertical_tirante_count == 3

    def test_tirante_total_inclui_verticais(self):
        spec = compute_pillar_bracing(0.25, 1.00, 2.85)
        assert spec.tirante_count == 16 + 3


class TestDegenerate:
    def test_dimensoes_invalidas_retornam_vazio(self):
        spec = compute_pillar_bracing(0.0, 0.5, 3.0)
        assert spec.vm_count == 0
        assert spec.tirante_count == 0
