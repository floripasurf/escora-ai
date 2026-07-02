"""Testes do BOM de VMs (vigas metalicas) - manual §28."""
from __future__ import annotations


import pytest

from src.engine.vm_grid_builder import VMGrid, VMSegment
from src.generator.bom_generator import (
    aggregate_vm_bom,
    aggregate_vm_summary,
    write_vm_bom_csv,
)


class _StubSlabResult:
    """SlabResult minimo (sem pydantic) para isolar o BOM."""
    def __init__(self, vm_grid):
        self.vm_grid = vm_grid


def _seg(role: str, model: str, length_mm: int) -> VMSegment:
    return VMSegment(
        role=role, model=model, length_mm=length_mm,
        start=(0, 0), end=(1, 0), axis="x",
    )


def _grid_with(*segs: VMSegment) -> VMGrid:
    g = VMGrid()
    for s in segs:
        g.add_segment(s)
    return g


class TestAggregateVMBom:
    def test_empty_inputs(self):
        assert aggregate_vm_bom([]) == []
        # Slab sem vm_grid
        assert aggregate_vm_bom([_StubSlabResult(None)]) == []

    def test_single_slab_single_model(self):
        grid = _grid_with(
            _seg("primaria", "VM130", 1550),
            _seg("primaria", "VM130", 1550),
            _seg("primaria", "VM130", 1550),
        )
        rows = aggregate_vm_bom([_StubSlabResult(grid)])
        assert len(rows) == 1
        assert rows[0]["modelo"] == "VM130"
        assert rows[0]["comprimento_mm"] == 1550
        assert rows[0]["quantidade"] == 3
        assert rows[0]["metragem_total_m"] == pytest.approx(4.65)
        assert rows[0]["role_principal"] == "primaria"

    def test_multiple_lengths_aggregated_separately(self):
        grid = _grid_with(
            _seg("primaria", "VM130", 1550),
            _seg("primaria", "VM130", 2050),
            _seg("primaria", "VM130", 1550),
        )
        rows = aggregate_vm_bom([_StubSlabResult(grid)])
        assert len(rows) == 2
        # Ordered by model then length
        assert rows[0]["comprimento_mm"] == 1550
        assert rows[0]["quantidade"] == 2
        assert rows[1]["comprimento_mm"] == 2050
        assert rows[1]["quantidade"] == 1

    def test_multiple_slabs_sum_across(self):
        g1 = _grid_with(_seg("primaria", "VM130", 1550), _seg("primaria", "VM130", 1550))
        g2 = _grid_with(_seg("primaria", "VM130", 1550), _seg("secundaria", "VM80", 1000))
        rows = aggregate_vm_bom([_StubSlabResult(g1), _StubSlabResult(g2)])
        # 3 VM130@1550 + 1 VM80@1000
        vm130 = next(r for r in rows if r["modelo"] == "VM130")
        vm80 = next(r for r in rows if r["modelo"] == "VM80")
        assert vm130["quantidade"] == 3
        assert vm80["quantidade"] == 1


class TestAggregateVMSummary:
    def test_summary_sums_quantities_per_model(self):
        grid = _grid_with(
            _seg("primaria", "VM130", 1550),
            _seg("primaria", "VM130", 2050),
            _seg("secundaria", "VM80", 1000),
            _seg("secundaria", "VM80", 1000),
        )
        summary = aggregate_vm_summary([_StubSlabResult(grid)])
        assert summary["VM130"]["quantidade"] == 2
        assert summary["VM130"]["metragem_total_m"] == pytest.approx(3.6)
        assert summary["VM80"]["quantidade"] == 2
        assert summary["VM80"]["metragem_total_m"] == pytest.approx(2.0)


class TestWriteVMBomCsv:
    def test_csv_has_header_and_rows(self, tmp_path):
        grid = _grid_with(
            _seg("primaria", "VM130", 1550),
            _seg("secundaria", "VM80", 1000),
        )
        out = tmp_path / "vm_bom.csv"
        write_vm_bom_csv([_StubSlabResult(grid)], str(out))
        assert out.exists()
        content = out.read_text()
        assert "modelo,comprimento_mm,quantidade,metragem_total_m,role_principal" in content
        assert "VM130,1550,1,1.55,primaria" in content
        assert "VM80,1000,1,1.0,secundaria" in content

    def test_csv_empty_when_no_grids(self, tmp_path):
        out = tmp_path / "vm_bom_empty.csv"
        write_vm_bom_csv([_StubSlabResult(None)], str(out))
        content = out.read_text()
        # Just header
        lines = [l for l in content.strip().split("\n") if l]
        assert len(lines) == 1
