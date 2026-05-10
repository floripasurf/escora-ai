# Escora Supplier Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Iterar o motor Escora até produzir DXF/BOM/PDF em padrão e detalhamento comparáveis aos projetos Supplier calibrados, preservando a política Escora de preferir escoras simples até 3,5 m, mix até 4,5 m e torres acima de 4,5 m.

**Architecture:** Seguir a migração do `MIGRATION_PLAN.md`: diagnosticar primeiro, transformar defeitos em regras rastreáveis, então corrigir em ciclos pequenos. O harness de diagnóstico roda os 12 DXFs Supplier e materializa artefatos em `diagnostics/`, sem alterar o pipeline durante a Phase 0.

**Tech Stack:** Python 3.12+, `ezdxf`, `shapely`, `pydantic`, FastAPI service pipeline, DXF Supplier em `input/supplier/` e `input/supplier_estrutural/`.

---

### Task 1: Phase 0 Harness

**Files:**
- Create: `scripts/diagnose/run_all_calibration.py`
- Create: `tests/diagnose/test_calibration_inventory.py`
- Create: `diagnostics/defects.md`
- Create: `diagnostics/tacit_rules.md`

- [x] **Step 1: Write failing inventory tests**

Run: `python3 -m unittest discover -s tests/diagnose -t . -p 'test_*.py' -v`

Expected before implementation: missing script failure.

- [x] **Step 2: Implement calibration discovery and summary writer**

`scripts/diagnose/run_all_calibration.py` must discover 12 shoring DXFs in `input/supplier/`, pair 11 structural DXFs in `input/supplier_estrutural/`, and write `diagnostics/<run>/summary.csv` even when dependencies are missing.

- [x] **Step 3: Verify tests pass**

Run: `python3 -m unittest discover -s tests/diagnose -t . -p 'test_*.py' -v`

Expected: 3 tests pass.

- [x] **Step 4: Run initial baseline**

Run: `python3 scripts/diagnose/run_all_calibration.py --root . --out diagnostics/supplier_phase0`

Expected in current environment: `0/12 completed` with explicit `DependencyUnavailable` rows.

### Task 2: Environment Unblock

**Files:**
- Modify: `requirements-dev.txt` only if a missing direct dependency is discovered.
- Do not modify pipeline code.

- [ ] **Step 1: Install dependencies into a Python 3.12 venv**

Run: `.venv312/bin/python -m pip install -r requirements-dev.txt`

Expected: succeeds once DNS/PyPI is available.

- [ ] **Step 2: Re-run calibration baseline**

Run: `.venv312/bin/python scripts/diagnose/run_all_calibration.py --root . --out diagnostics/supplier_phase0_live`

Expected: `diagnostics/supplier_phase0_live/summary.csv` has one row per Supplier project and generated artefacts for projects that complete.

### Task 3: Visual Iteration Loop

**Files:**
- Append: `diagnostics/defects.md`
- Modify pipeline files only after a defect has a coordinate/print and a failing test.

- [ ] **Step 1: Render or open three generated outputs**

Inspect one low-rise project, one mid-height project and one tower-heavy project.

- [ ] **Step 2: Record defects**

Fill at least 10 real rows in `diagnostics/defects.md` with coordinates, category and expected rule.

- [ ] **Step 3: Pick one defect**

Write a failing unit/regression test that captures that defect.

- [ ] **Step 4: Implement the minimal fix**

No production code without the failing test first.

- [ ] **Step 5: Re-run all 12 calibration projects**

Compare summary metrics and output screenshots before committing.

### Task 4: Equipment Policy Rule

**Files:**
- Test: `tests/engine/test_support_type_policy.py`
- Modify: support decision logic in `src/engine/` or `src/pipeline/stage_calculate.py`

- [ ] **Step 1: Write tests for Raphael policy**

Cases:
- `pe_direito <= 3.5`: prefer telescopic shores if catalog capacity supports the load.
- `3.5 < pe_direito <= 4.5`: allow mixed support.
- `pe_direito > 4.5`: require towers.

Guardrail:
- Do not collapse this height-based policy into tacit rule `T-038`. `T-038`
  is a beam-length rule (`viga longa > 4.5 m` gets towers at supports),
  while this task is a clear-height rule (`pe_direito > 4.5 m`). They share
  the `4.5 m` threshold but protect different engineering concerns. Tests for
  this task must verify the height policy without regressing long-beam support
  behavior.

- [ ] **Step 2: Implement policy with source comments**

Use Raphael/Supplier calibration rationale as the source until formalized in the rule registry.

- [ ] **Step 3: Re-run calibration and compare output**

Do not tune parameters blindly without recording the effect in diagnostics.
