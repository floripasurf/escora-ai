"""Testes dos verifiers STRUCT-004 (momento) e STRUCT-005 (flecha) do grid de VMs.

Manual §28.4 - STRUCT-VM-001/002 (correlacao com nomenclatura plano).
"""
from __future__ import annotations

import pytest

from src.engine.vm_grid_builder import VMGrid, VMSegment
from src.rules.project import RuleProject, SlabPanel
from src.rules.schema import REGISTRY
from src.rules.verifiers import register_all


@pytest.fixture(scope="module", autouse=True)
def _register():
    register_all()


def _make_panel(label: str, grid: VMGrid) -> SlabPanel:
    return SlabPanel(
        polygon=None, thickness_m=0.12, area_m2=4.0, shores=[],
        label=label, vm_grid=grid,
    )


def _seg(passes_m: bool, passes_f: bool, role: str = "primaria",
         model: str = "VM130") -> VMSegment:
    return VMSegment(
        role=role, model=model, length_mm=1550,
        start=(0.0, 0.0), end=(1.5, 0.0), axis="x",
        moment_kn_m=10.0 if not passes_m else 2.0,
        moment_adm_kn_m=5.06,
        flecha_mm=10.0 if not passes_f else 1.0,
        flecha_adm_mm=4.0,
        passes_moment=passes_m, passes_deflection=passes_f,
    )


class TestStructVMMoment:
    def test_no_violation_when_segment_passes(self):
        panel = _make_panel("L-ok", VMGrid(segments=[_seg(True, True)]))
        proj = RuleProject(slab_panels=[panel])
        viols = [v for v in REGISTRY.check_all(proj) if v.rule_id == "STRUCT-004"]
        assert viols == []

    def test_violation_when_moment_fails(self):
        panel = _make_panel("L-fail-M", VMGrid(segments=[_seg(False, True)]))
        proj = RuleProject(slab_panels=[panel])
        viols = [v for v in REGISTRY.check_all(proj) if v.rule_id == "STRUCT-004"]
        assert len(viols) == 1
        assert viols[0].severity == "error"
        assert "L-fail-M" in viols[0].message

    def test_no_grid_no_violation(self):
        panel = SlabPanel(
            polygon=None, thickness_m=0.12, area_m2=4.0, shores=[],
            label="L-no-grid", vm_grid=None,
        )
        proj = RuleProject(slab_panels=[panel])
        viols = [v for v in REGISTRY.check_all(proj) if v.rule_id == "STRUCT-004"]
        assert viols == []

    def test_one_violation_per_failing_segment(self):
        grid = VMGrid(segments=[
            _seg(True, True),
            _seg(False, True),
            _seg(False, True),
            _seg(True, True),
        ])
        panel = _make_panel("L-multi", grid)
        proj = RuleProject(slab_panels=[panel])
        viols = [v for v in REGISTRY.check_all(proj) if v.rule_id == "STRUCT-004"]
        assert len(viols) == 2


class TestStructVMDeflection:
    def test_no_violation_when_deflection_ok(self):
        panel = _make_panel("L-ok", VMGrid(segments=[_seg(True, True)]))
        proj = RuleProject(slab_panels=[panel])
        viols = [v for v in REGISTRY.check_all(proj) if v.rule_id == "STRUCT-005"]
        assert viols == []

    def test_violation_when_deflection_fails(self):
        panel = _make_panel("L-fail-flecha", VMGrid(segments=[_seg(True, False, role="secundaria", model="VM80")]))
        proj = RuleProject(slab_panels=[panel])
        viols = [v for v in REGISTRY.check_all(proj) if v.rule_id == "STRUCT-005"]
        assert len(viols) == 1
        assert viols[0].severity == "error"
        assert "VM80" in viols[0].message

    def test_both_M_and_flecha_fail_emits_two_violations(self):
        grid = VMGrid(segments=[_seg(False, False)])
        panel = _make_panel("L-both", grid)
        proj = RuleProject(slab_panels=[panel])
        viols = REGISTRY.check_all(proj)
        ids = {v.rule_id for v in viols}
        assert "STRUCT-004" in ids
        assert "STRUCT-005" in ids


class TestStructVMLocation:
    def test_violation_carries_segment_midpoint(self):
        seg = VMSegment(
            role="primaria", model="VM130", length_mm=1550,
            start=(1.0, 2.0), end=(3.0, 2.0), axis="x",
            moment_kn_m=10.0, moment_adm_kn_m=5.0,
            flecha_mm=1.0, flecha_adm_mm=4.0,
            passes_moment=False, passes_deflection=True,
        )
        panel = _make_panel("L-loc", VMGrid(segments=[seg]))
        proj = RuleProject(slab_panels=[panel])
        viols = [v for v in REGISTRY.check_all(proj) if v.rule_id == "STRUCT-004"]
        assert len(viols) == 1
        # Midpoint = (2.0, 2.0)
        assert viols[0].location == (2.0, 2.0)
