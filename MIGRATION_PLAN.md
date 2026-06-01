# Escora.AI — Migration to Rule-Driven Architecture

**Purpose of this document:** This is an executable migration plan to break out of the current development plateau by shifting from ad-hoc fixes to a rule-driven architecture. Each task in this document is a self-contained unit of work for Claude Code, with clear acceptance criteria and verification gates.

**Operator (you):** Raphael
**Executor:** Claude Code (or any coding agent following this plan)
**Estimated total time:** 3–4 weeks of focused work, plus ongoing maintenance.

---

## How to use this document

1. Save this file as `MIGRATION_PLAN.md` at the repository root.
2. Save the companion `AGENTS.md` (covered in Task 1.1) at the repository root.
3. Work through phases sequentially. **Do not skip phases.** Phase 0 looks like "doing nothing" but it produces the inventory that informs every subsequent decision.
4. For each task, paste the task block into Claude Code as a prompt, including the **Verification gate** at the end. Do not let Claude Code declare a task complete without running the verification command.
5. After each task, commit. Use the task ID in the commit message: `git commit -m "P1.2: Add Rule and Violation schema"`.
6. If a task introduces test failures in `tests/regression/`, **revert and reframe** before continuing. The plateau exists because regressions accumulate silently.

---

## The hard rules of this migration

These apply to every task. Claude Code must be reminded of them at the start of any session.

1. **Do not weaken any test to make it pass.** If a test fails, the implementation is wrong, not the test. The only exception is when the test itself was written incorrectly — in which case fix it explicitly with a commit message documenting why.
2. **Do not invent norm references or numeric values.** Every cited NBR section, every numeric threshold, every spacing rule must come from `AGENTS.md`, the Orguel training extracts, or the engineer Q&A. If something seems necessary but isn't documented, flag it as a `# TODO(engineer-confirmation)` and stop.
3. **Every numeric output must carry a `Source` citation.** This is non-negotiable. If you find a path through the code that produces a `LoadValue` without a source, that's a bug.
4. **Do not modify the regression suite to make it pass.** The 12 Orguel projects are ground truth. If your change breaks them, your change is wrong.
5. **No silent fallbacks.** If the code can't determine something (slab thickness, beam section, etc.), it must raise a typed exception, not silently substitute a default. Defaults are explicit decisions, not error recovery.

---

## Project context (brief)

Escora.AI generates shoring (escoramento) layouts for Brazilian civil construction. Inputs: structural plan DXFs (typically from TQS, AutoCAD, or Eberick). Outputs: shoring layout DXF (Orguel symbology), BOM CSV, Memória de Cálculo PDF, IFC for BIM integration. Calibrated against 12 executive Orguel projects (April 2026). Equipment partner: Grupo Orguel.

Current state: working prototype, hit development plateau. Symptoms: shores positioned outside slab polygons; missing shores at structural intersections; Claude Code edits causing regressions in unaffected projects.

Goal of this migration: externalize all engineering rules into a queryable, testable registry so that every change is automatically checked against every known rule, across every reference project.

For detailed engineering context see `AGENTS.md`.

---

# PHASE 0 — Diagnose (do not fix anything)

**Objective:** Build a complete inventory of current defects and tacit rules. This phase produces no code changes. It produces a list of bugs you currently have, a list of rules you currently lack, and a list of patterns from real Orguel projects that your system fails to reproduce.

**Why this comes first:** Without this inventory, every subsequent fix is a local optimization. With it, you have a prioritized backlog that the rule system will systematically address.

## Task 0.1 — Run the current pipeline against all 12 calibration projects

**Prompt for Claude Code:**

> Working from the existing Escora.AI codebase, write a script `scripts/diagnose/run_all_calibration.py` that:
> 1. Discovers all reference projects under `tests/calibration/` (or wherever the 12 Orguel DXFs live — confirm location with the operator before proceeding).
> 2. For each project, runs the current pipeline end-to-end and saves outputs to `diagnostics/<project_id>/`: the generated DXF, BOM CSV, and any intermediate JSON the pipeline already produces.
> 3. Captures any uncaught exceptions per project to `diagnostics/<project_id>/errors.log`.
> 4. Produces a summary `diagnostics/summary.csv` with columns: project_id, ran_to_completion, bom_kg_total, kg_per_m3, tower_count, telescopic_count, exceptions_count.
>
> Do not modify any pipeline code. This is a read-only inventory.
>
> **Verification gate:** After running, the operator and you will manually inspect 3 of the output DXFs in QCAD or LibreCAD. The script is complete when `diagnostics/summary.csv` exists for all 12 projects (rows may show errors; that's fine — that's the point).

## Task 0.2 — Build the visual defect inventory

**Prompt for Claude Code:**

> Create `diagnostics/defects.md` as a structured table. Fields per row:
> - `defect_id` (D-001, D-002, …)
> - `project_id` (which calibration project)
> - `category` (placement | spacing | sizing | missing | extra | other)
> - `coordinates` (DXF XY of the defect)
> - `description_pt` (one sentence in Portuguese describing what's wrong)
> - `expected_rule` (a guess at what rule, when added, would catch this — e.g., "shore must be inside slab polygon")
> - `severity` (error | warning)
>
> Pre-populate the table with placeholder rows D-001 through D-020. The operator (Raphael) will fill these in by visually reviewing the outputs from Task 0.1 in QCAD/LibreCAD. Your job is to set up the document structure, not to invent defects.
>
> **Verification gate:** `diagnostics/defects.md` exists with empty rows. Operator fills in real defects manually after Task 0.1.

## Task 0.3 — Catalog tacit rules

**Prompt for Claude Code:**

> Create `diagnostics/tacit_rules.md`. This is an inventory of rules that exist in the current codebase but are not documented anywhere. Walk through the source tree and identify:
> 1. Hardcoded numeric constants (distances, angles, ratios, capacities)
> 2. Magic threshold conditions in `if` statements
> 3. Implicit defaults when data is missing
> 4. Order-dependent decision logic
>
> For each, record: source file, line number, the constant/condition, and a guess at what rule it implements. Group by category (geometric, load, equipment, decision).
>
> Do NOT change any code. This is read-only.
>
> **Verification gate:** `diagnostics/tacit_rules.md` exists and contains at least 30 entries. Operator reviews and tags each as "documented" (matches `AGENTS.md`), "undocumented but correct" (real rule, just needs to be externalized), or "unclear" (needs engineer confirmation).

## Task 0.4 — Phase 0 sign-off

Before proceeding to Phase 1, confirm:
- [ ] All 12 calibration projects have output in `diagnostics/`
- [ ] `defects.md` has at least 10 real, located defects
- [ ] `tacit_rules.md` has at least 30 entries categorized
- [ ] Operator has read both and prioritized the top 5 defects to address first

---

# PHASE 1 — Foundation (the rule system itself)

**Objective:** Build the core architecture: `Rule`, `Source`, `Violation` types, the rules registry, and the regression harness. No actual rules yet — those come in Phase 2.

## Task 1.1 — Write AGENTS.md

**Prompt for Claude Code:**

> Create `AGENTS.md` at the repository root. Use the template provided by the operator. The template is included as Appendix A of `MIGRATION_PLAN.md`. Fill in any project-specific values that already exist in the codebase. For values that are uncertain, mark them as `# TODO(engineer-confirmation)` and do not invent.
>
> One specific item: the current code uses `sobrecarga de trabalho = 1.50 kN/m²` but NBR 15696 §4.2 specifies a minimum of 2.0 kN/m². Mark this in `AGENTS.md` under "Open Engineering Questions" with the exact quote from the Orguel training PDF (page where it specifies the 2.0 minimum). Do not change the constant in code yet.
>
> **Verification gate:** `AGENTS.md` exists at repo root, parses as valid Markdown, references real NBR sections, and has at least one `# TODO(engineer-confirmation)` flag.

## Task 1.2 — Rule, Source, Violation schema

**Prompt for Claude Code:**

> Create `src/escora/rules/__init__.py` and `src/escora/rules/schema.py`. Use the schema provided in Appendix B of `MIGRATION_PLAN.md`. Implementation requirements:
> - All models are Pydantic v2.
> - `Source` is required everywhere — no default factories that allow None.
> - `Rule.id` follows the pattern `<CATEGORY>-<NUMBER>` where category is one of: GEOM, SPACE, STRUCT, LOAD, EQUIP, ENV, DECIDE, OUTPUT.
> - The `Violation.location` field uses DXF coordinates (model space).
> - Add a `RuleRegistry` class with methods: `register(rule, verifier)`, `get(rule_id)`, `all()`, `by_category(cat)`, `run_all(project) -> list[Violation]`.
> - The registry is module-level singleton; import it as `from escora.rules import REGISTRY`.
>
> Write `tests/unit/test_rules_schema.py` proving:
> 1. `Source` cannot be constructed without `type` and `ref`.
> 2. `Rule.id` is rejected if it doesn't match the pattern.
> 3. `RuleRegistry.run_all` calls every registered verifier and aggregates results.
> 4. Severity ordering: `error` violations sort before `warning` in any output.
>
> **Verification gate:** `pytest tests/unit/test_rules_schema.py -v` — all tests pass. No test is skipped.

## Task 1.3 — Project type for verifier inputs

**Prompt for Claude Code:**

> Verifiers need a stable input type. Create or extend `src/escora/domain/project.py` with a `Project` Pydantic model that aggregates everything a verifier might need: structural geometry (slabs, beams, columns with their polygons), load values, placement results (shore positions, tower positions, VM placements), BOM, and decision trace.
>
> The `Project` type must be constructible from the current pipeline's outputs without modifying the pipeline. If the pipeline produces dicts or different types, write an adapter `escora.adapters.from_pipeline_output(raw) -> Project`.
>
> **Verification gate:** `pytest tests/unit/test_project_model.py -v` includes at least one test that loads a real calibration project's output (from Task 0.1) and constructs a `Project` from it without errors.

## Task 1.4 — Regression harness skeleton

**Prompt for Claude Code:**

> Create `tests/regression/conftest.py` with a parameterized fixture `calibration_project` that yields each of the 12 Orguel projects. Each yielded value is a tuple `(project_id, input_dxf_path, signed_bom_path)`.
>
> Create `tests/regression/test_pipeline_runs.py` with one test:
> ```python
> def test_pipeline_runs_to_completion(calibration_project):
>     project_id, input_dxf, _ = calibration_project
>     result = run_full(input_dxf)
>     assert result is not None
> ```
>
> This test will likely fail for some projects right now. That's expected and fine. Mark known-failing project IDs with `pytest.xfail` and a comment referencing the defect IDs from `diagnostics/defects.md`.
>
> Create `tests/regression/test_envelope.py`:
> ```python
> def test_kg_per_m3_envelope(calibration_project):
>     project_id, input_dxf, signed_bom = calibration_project
>     result = run_full(input_dxf)
>     assert 12 <= result.kg_per_m3 <= 16, (
>         f"{project_id}: {result.kg_per_m3:.1f} outside [12, 16] envelope"
>     )
> ```
>
> Mark this test with `xfail` per project as needed.
>
> **Verification gate:** `pytest tests/regression/ -v` runs to completion. Output is the baseline — every xfail is a documented current defect. After this, no future change may turn an xfail into an unexpected pass without explanation, and no current pass may regress to fail.

## Task 1.5 — Phase 1 sign-off

- [ ] `AGENTS.md` at repo root, with explicit engineer-confirmation flags
- [ ] `src/escora/rules/schema.py` with full schema and registry
- [ ] `src/escora/domain/project.py` with `Project` aggregate
- [ ] `tests/regression/` runs all 12 projects and produces a baseline of pass/xfail
- [ ] All Phase 1 unit tests pass

---

# PHASE 2 — First rules (manual extraction)

**Objective:** Encode the first ~15 rules that can be extracted unambiguously from `AGENTS.md`, the engineer Q&A, and the Orguel training. These prove the architecture works end-to-end and establish the pattern for all subsequent rules.

The full list of rules to encode in this phase is in **Appendix C** of this document. Each rule is one task.

## Task 2.1 — Implement rule GEOM-001 (column setback)

**Prompt for Claude Code:**

> Implement rule `GEOM-001`: every shore must be at least 0.70 m from any column face. Source: NBR 6118:2023 §19.5 (zona de punção), reinforced by the operator's `AGENTS.md`.
>
> Create `src/escora/rules/verifiers/geom.py` and add the verifier function:
> ```python
> def verify_column_setback(project: Project) -> list[Violation]:
>     ...
> ```
>
> Use `shapely` for geometric distance calculations. The function must return one `Violation` per shore-column pair that violates the rule, with `location` set to the shore's XY and `element_id` set to the shore's ID.
>
> Register the rule and verifier in the registry via the module's import side effects (use a `register_all()` function called from `escora.rules.__init__`).
>
> Write `tests/unit/test_geom_001.py` with at least:
> 1. A synthetic project with one shore 1.0m from a column → no violation.
> 2. A synthetic project with one shore 0.5m from a column → one violation, severity=error.
> 3. A synthetic project with one shore exactly 0.70m from a column → no violation (boundary case).
> 4. A synthetic project with no columns → no violations.
>
> Then run the regression suite and report any project that newly fails. Do NOT fix those failures in this task — record them as `defects.md` entries D-NNN with category=placement.
>
> **Verification gate:** Unit tests pass. Regression test count of new failures recorded.

## Task 2.2 through 2.15

Repeat the pattern of Task 2.1 for each rule in Appendix C. Each rule gets its own task. Each task ends with the same verification pattern: unit tests + regression delta recorded.

**One task per rule — do not batch.** Batching loses traceability and makes it impossible to identify which rule introduced which regression.

The order to implement, prioritized by likely impact based on current defect patterns:

1. GEOM-001 — column setback 0.70m (Task 2.1, above)
2. GEOM-002 — slab edge setback 0.15m
3. GEOM-003 — minimum spacing between shores 0.30m
4. GEOM-poly — point-in-polygon containment (this catches "shore outside slab" defects directly)
5. SPACE-001 — slab thickness → max spacing table
6. SPACE-002 — cruzeta spacing 0.80m under beams
7. STRUCT-001 — every beam intersection without column has support within radius
8. STRUCT-002 — cantilever tip support within 20–40cm
9. LOAD-001 — sobrecarga de trabalho ≥ 2.0 kN/m² (this is the one flagged in AGENTS.md — implementing the check forces the engineer-confirmation conversation)
10. LOAD-002 — total static load ≥ 4.0 kN/m²
11. LOAD-003 — hyperestaticity +25% on continuous central reactions
12. LOAD-004 — γf = 1.4 majoration applied
13. EQUIP-001 — altura > 4.50m → no telescópicas in BOM
14. EQUIP-003 — tower utilization in [0.55, 0.85]
15. ENV-001 — kg/m³ in [12, 16]

## Task 2.16 — Wire verifiers into pipeline output

**Prompt for Claude Code:**

> Modify the main pipeline to invoke `REGISTRY.run_all(project)` after layout generation. Attach the resulting violations to the `Project` object as `project.violations`.
>
> Modify the Memória de Cálculo PDF generation so that any `error`-severity violations are listed in a "Pendências para revisão do engenheiro responsável" section at the front of the document. `warning`-severity violations go in a separate appendix.
>
> Modify the BOM generator: if any error-severity violation exists, the BOM CSV first line is a comment `# AVISO: {N} violações de regras detectadas. Revisar antes de uso.`
>
> **Verification gate:** Run the full pipeline against one calibration project that you know has defects. Confirm: violations appear in the PDF, BOM CSV has the warning header. Run the full pipeline against a clean project — confirm no spurious warnings.

## Task 2.17 — Phase 2 sign-off

- [ ] All 15 rules from Appendix C have implementations
- [ ] Each rule has dedicated unit tests with at least 4 cases each
- [ ] Pipeline integrates verifier output into PDF and BOM
- [ ] Regression suite has clear baseline: per-project xfail list documented in `tests/regression/baseline.md`
- [ ] No previously-passing test now fails

---

# PHASE 3 — Empirical extraction from real DXFs

**Objective:** Use the 12 Orguel project DXFs as ground truth. Extract empirical patterns. Anywhere your system's output systematically differs from real Orguel work, that's a missing rule.

## Task 3.1 — Pattern extractor for Orguel reference DXFs

**Prompt for Claude Code:**

> Create `scripts/empirical/extract_patterns.py`. It reads each Orguel reference DXF (the *output* DXFs from real signed projects, not the input structural plans) and computes per project:
>
> 1. Shore positions per layer.
> 2. For each shore: distance to nearest column face, distance to nearest slab edge, distance to nearest neighbor shore.
> 3. Spacing distribution (min, p25, mean, median, p75, max) per slab thickness category.
> 4. Per slab panel: shore density (shores per m²), tower-to-telescópica ratio, total mass.
> 5. For each beam-beam intersection without a column: distance to nearest support.
> 6. For each cantilever tip: distance to nearest support.
> 7. VM type usage frequency per beam length range.
>
> Output: `diagnostics/orguel_patterns.yaml` with one section per project plus an `aggregate` section summarizing across all 12.
>
> Use ezdxf + shapely. Pure read; no modifications to anything.
>
> **Verification gate:** `orguel_patterns.yaml` exists with all 12 projects + aggregate. Operator reviews aggregate values and confirms they match expectations (e.g., median tower-to-telescópica ratio is in the expected range).

## Task 3.2 — Compare system output against patterns

**Prompt for Claude Code:**

> Create `scripts/empirical/compare_outputs.py`. For each calibration project, compare the system's generated output against the Orguel reference output along the same dimensions extracted in Task 3.1.
>
> Output: `diagnostics/output_deltas.yaml` with per-project comparison: where does the system differ systematically? Categorize each delta as:
> - `<5%` (acceptable variance)
> - `5–15%` (worth investigating)
> - `>15%` (likely missing rule)
>
> **Verification gate:** `output_deltas.yaml` exists. Operator reviews. Each delta >15% becomes a candidate rule entry.

## Task 3.3 — Convert significant deltas into rule candidates

**Prompt for Claude Code:**

> For each delta categorized as `>15%` in Task 3.2, propose a rule. Add to `rules/candidates.md` with:
> - The pattern observed in Orguel projects (with quantitative summary)
> - The pattern produced by the system (with quantitative summary)
> - A proposed rule that, if enforced, would close the gap
> - A confidence score (high / medium / low) based on how consistent the pattern is across the 12 projects
>
> High-confidence candidates become tasks in Phase 4. Medium go to a backlog. Low get flagged for engineer review.
>
> Do NOT add candidates to the registry yet. They need engineer confirmation first.
>
> **Verification gate:** `rules/candidates.md` exists with at least one entry per delta. Operator reviews and approves which to promote.

## Task 3.4 — Phase 3 sign-off

- [ ] `orguel_patterns.yaml` extracted from all 12 reference DXFs
- [ ] `output_deltas.yaml` quantifies system vs Orguel differences
- [ ] `rules/candidates.md` populated with rule proposals from significant deltas
- [ ] Operator has reviewed and tagged candidates for promotion

---

# PHASE 4 — Rule expansion sprint

**Objective:** Encode the next ~30 rules. Mix of: high-confidence empirical candidates from Phase 3, rules extracted from the Orguel training PDF, and rules from the engineer Q&A that didn't make Phase 2.

## Task 4.1 — Extract rules from Orguel training PDF

**Prompt for Claude Code:**

> Read the Orguel training material text (already extracted to `docs/orguel_training_extract.md` from the original PDF). Walk through it section by section. For every operational rule you can identify, add an entry to `rules/from_orguel_training.md` with:
> - Quote from the training (Portuguese, with section number)
> - Proposed rule ID and category
> - Proposed verifier description
> - Whether it's testable from DXF output alone, or needs additional input
>
> Focus especially on: section 3 (Projeto), section 6 (Travamento de pilares e vigas), section 7 (Cálculo do escoramento), section 8 (Regras básicas).
>
> Do NOT implement verifiers yet. This task produces the catalog only.
>
> **Verification gate:** `rules/from_orguel_training.md` has at least 30 candidate rules with citations. Operator reviews and approves implementation order.

## Task 4.2 through 4.N — Implement approved rules

For each rule the operator approves from `rules/from_orguel_training.md` and `rules/candidates.md`, repeat the Task 2.1 pattern: unit tests + regression delta + commit per rule.

Suggested batches of related rules to keep momentum without losing the one-rule-per-task discipline:
- Batch 1: column bracing rules (faces > 40cm, > 90cm, etc.)
- Batch 2: lateral beam bracing (panel > 60cm)
- Batch 3: ribbed slab specifics (positioning over rib intersections)
- Batch 4: alvenaria estrutural setbacks (≤ 5cm)
- Batch 5: cantilever extremity rules (20–40cm)

## Task 4.N+1 — Phase 4 sign-off

- [ ] At least 30 additional rules implemented
- [ ] Total rule count in registry ≥ 45
- [ ] Calibration projects: number of xfail tests reduced by at least 50% from Phase 1 baseline
- [ ] kg/m³ envelope: at least 10 of 12 projects within [12, 16]

---

# PHASE 5 — Bug-to-rule workflow (ongoing)

**Objective:** Lock in the new development pattern. Every bug becomes a rule. The plateau is broken because the system gets stronger over time, not just patched.

## The new prompt pattern for Claude Code

When a defect is found, do NOT prompt:

> ❌ "Fix the shoring at coordinates (12.5, 8.3) in projeto_05 — it's outside the slab."

Instead, prompt:

> ✅ "In projeto_05, a shore is positioned at (12.5, 8.3) which is outside the slab polygon. Determine: (a) is there a verifier in `escora.rules.verifiers` that should fire for this case? If yes, why didn't it fire? If no, write the verifier as a new rule, register it, and run the regression suite. Then either (i) the placement code that produced this output has a bug — find and fix it; or (ii) the verifier is correct and the failure exposes a missing input/preprocessing step. In all cases, do not modify the verifier to make the failing case pass. Show me the regression diff before and after."

This pattern forces every bug to either strengthen the rule system or fix a real underlying bug, never to mask the symptom.

## The standing prompt prefix

For every Claude Code session on this codebase, start with:

```
Read AGENTS.md and MIGRATION_PLAN.md before doing anything else.

Hard rules:
1. Do not weaken any test to make it pass.
2. Do not invent norm references or numeric values.
3. Every numeric output carries a Source citation.
4. Do not modify the regression suite unless explicitly approved by the operator.
5. No silent fallbacks — raise typed exceptions instead.

Before declaring any task complete, run:
  pytest tests/unit/ tests/regression/ -v
and report the diff in pass/fail/xfail counts vs the previous run.

Now: <your specific task>
```

## The recurring tasks

These run continuously, not as a phase:

### Weekly task: Triage defects.md

Walk through `diagnostics/defects.md`. For each entry: is there a rule that would have caught this? If yes, has the rule fired? If no, draft the rule.

### Per-bug task: Reproduce → rule → fix

For every reported bug:
1. Reproduce as a synthetic test case in `tests/regression/`
2. Determine if it's a missing rule or an implementation bug behind an existing rule
3. If missing rule: implement the verifier, then fix until it passes
4. If implementation bug: fix without weakening the verifier
5. Commit with message: `fix: {rule_id} catches {brief description}` or `feat: add rule {rule_id} for {description}`

### Per-PR gate: Regression delta must be non-positive

CI must enforce: `pytest tests/regression/` produces ≥ as many passes as the main branch and ≤ as many fails. PRs that increase the failure count are auto-rejected.

---

# Appendices

The appendices contain content for Claude Code to use directly: the AGENTS.md template, the rule schema source, and the initial rules to encode.


---

## Appendix A — AGENTS.md template

Save this as `AGENTS.md` at the repository root. Fill in `# TODO` items based on the current codebase. Mark uncertain values as `# TODO(engineer-confirmation)`.

```markdown
# Escora.AI — Engineering Context

## Product
Automated shoring (escoramento) design system for Brazilian civil 
construction. Input: structural plan DXF (TQS, AutoCAD, Eberick). 
Output: shoring layout DXF with Orguel symbology, BOM CSV, Memória 
de Cálculo PDF, IFC for BIM integration.

## Domain Authority (in priority order)
1. ABNT NBR 15696:2009 — Fôrmas e escoramentos para estruturas de 
   concreto — Projeto, dimensionamento e procedimentos executivos.
2. ABNT NBR 6118:2023 — Projeto de estruturas de concreto.
3. ABNT NBR 6120:2019 — Cargas para o cálculo de estruturas.
4. ABNT NBR 14931 — Execução de estruturas de concreto.
5. ABNT NBR 6123 — Forças devidas ao vento.
6. ABNT NBR 7190 — Projeto de estruturas de madeira.
7. ABNT NBR 8800 — Projeto de estruturas de aço.
8. Orguel internal training (Treinamento Técnico Escoramento, 
   Nov 2020) — operational rules and worked examples.
9. Orguel engineer Q&A (calibration date 2026-04-07, n=12 executive 
   projects).

## Hard Constraints from Norms
| Constraint | Value | Source |
|---|---|---|
| Sobrecarga de trabalho mínima (concrete ops) | 2.0 kN/m² | NBR 15696 §4.2 |
| Plataformas de trabalho | 1.5 kN/m² | NBR 15696 §4.2 |
| Carga estática total mínima | 4.0 kN/m² | NBR 15696 §4.2 |
| Vento mínimo (escoramento >10m ou aberto) | 0.6 kN/m² | NBR 15696 §4.2 + NBR 6123 |
| γc (concreto) | 25 kN/m³ | NBR 6120 |
| γf (majoração) | 1.4 | NBR 15696 |
| Acréscimo de carga em apoio central contínuo | +25% | Orguel training §7 (hiperestaticidade) |

## Open Engineering Questions (require engineer confirmation)
- The current code uses `sobrecarga de trabalho = 1.50 kN/m²` but 
  NBR 15696 §4.2 specifies a minimum of 2.0 kN/m². Resolution: 
  confirm with Orguel engineers whether this is intentional 
  (combined value with platforms?) or an error. Until resolved, 
  rule LOAD-001 will flag projects using <2.0.

## Geometric Setbacks
| Setback | Min Distance | Source |
|---|---|---|
| Distância da face do pilar | 0.70 m | NBR 6118:2023 §19.5 (zona de punção) |
| Distância da borda da laje | 0.15 m | Practice (Orguel-validated) |
| Espaçamento entre escoras | 0.30 m | Practice (Orguel-validated) |
| Distância de alvenaria estrutural | ≤ 5 cm | Orguel training §8 (regra 12) |
| Cantilever (balanço): tip → support | 20–40 cm | Orguel training §8 (regra 11) |

## Spacing Rules — Slabs by Thickness
| Slab thickness | Max shore spacing |
|---|---|
| 10–16 cm | 1.30 m |
| 17–24 cm | 1.20 m |
| 25–30 cm | 1.10 m |
| 31+ cm | 1.00 m |

## Spacing Rules — Beams
- Telescopic shores under beams: max 1.00 m
- Towers under beams: max 1.50 m
- Cruzetas (crossbars) under beams: every 0.80 m

## Lateral Bracing
- Beam panels with height > 60 cm: lateral bracing required
- Beam lateral bracing VM50 spacing: 0.80–1.00 m
- Column bracing: 2× VM50 + 2× anchor bars per set
- Column face > 40 cm: metal bracing on all 4 sides
- Column face > 90 cm: additional vertical VM

## Decision Chain (engineer-validated, do not reorder)
1. Altura > 4.50 m → 100% torre
2. Carga × 1.4 > capacidade derateada (Euler) de TODAS as 
   telescópicas → 100% torre
3. Sem torres em estoque (modo inventário) → 100% telescópica
4. Vão > 15 m → 100% torre (cimbramento pesado)
5. Viga com (laje ≥ 15 cm OR vão > 6 m) → MISTO 35% torres em 
   extremidades e interseções (Orguel calibration 2026-04-07)
6. Laje com espessura ≥ 20 cm → MISTO 18% torres em grid
7. Painel de laje ≥ 40 m² → MISTO 15% torres em grid largo
8. Laje nervurada ≥ 25 cm → MISTO 20% torres
9. Default → 100% telescópica (ESC310 ou ESC450 conforme altura)

## Validated Calibration Envelope (Orguel, 2026-04-07, n=12)
- Tower fraction in beams (mixed mode): 29–44%, default 35%
- Tower fraction in slabs (mixed mode): 13–22%, default 15–18%
- kg/m³ envelope: 12–16 kg/m³ (final BOM mass / concrete volume)
- Tower utilization (light structures): 60–80%

## Equipment Catalog
Single source of truth: `catalog/equipment.yaml`. 
Do NOT hardcode equipment dimensions, capacities, or weights anywhere 
else in the codebase.

## Output Traceability Rule (CRITICAL)
Every numeric output MUST carry a `Source` citation. The `LoadValue` 
type and `Project.violations` enforce this at the type level. 
Any code path producing a numeric output without a Source is a bug.

## Validation Gates
A change ships only if:
1. All unit tests pass (`pytest tests/unit/ -v`)
2. Regression suite has ≥ baseline pass count and ≤ baseline fail 
   count (`pytest tests/regression/ -v`)
3. No new error-severity violations introduced on calibration set
4. kg/m³ envelope holds for ≥ 10 of 12 calibration projects

## Engineering Sign-off
This system produces auditable drafts. Final approval requires a 
CREA-registered engineer's ART. The system MUST NOT remove or hide 
the ART block from any generated PDF. The PDF must list any active 
violations in a "Pendências para revisão do engenheiro responsável" 
section before the ART block.
```

---

## Appendix B — Rule schema source code

Save this as `src/escora/rules/schema.py`.

```python
"""Rule, Source, Violation schema for Escora.AI.

Every engineering rule in the system is represented here. The 
registry is module-level and singleton-imported as REGISTRY.

Design principles:
- Source citation is mandatory on every Rule.
- Verifiers are pure functions: Project -> list[Violation].
- Severity is a closed enum: error or warning.
- Rule IDs follow the pattern <CATEGORY>-<NUMBER>.
"""
from __future__ import annotations

import re
from typing import Callable, Literal, Protocol, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from escora.domain.project import Project


_RULE_ID_PATTERN = re.compile(
    r"^(GEOM|SPACE|STRUCT|LOAD|EQUIP|ENV|DECIDE|OUTPUT)-\d{3,4}$"
)

SourceType = Literal["norm", "manual", "dxf_pattern", "engineer_qa"]
Severity = Literal["error", "warning"]
Category = Literal[
    "GEOM", "SPACE", "STRUCT", "LOAD", "EQUIP", "ENV", "DECIDE", "OUTPUT"
]


class Source(BaseModel):
    """Citation for any rule or numeric value."""
    type: SourceType
    ref: str = Field(
        ..., 
        description="Citation: 'NBR 15696:2009 §4.2.1' or 'Orguel "
                    "training p.42' or 'Engineer Q&A #5'"
    )
    calibration: Optional[str] = Field(
        None, 
        description="When applicable: 'Orguel 2026-04-07 (n=12)'"
    )

    model_config = {"frozen": True}


class Violation(BaseModel):
    """A specific rule violation found in a project."""
    rule_id: str
    severity: Severity
    location: Optional[tuple[float, float]] = Field(
        None, description="DXF model-space XY"
    )
    element_id: Optional[str] = None
    message_pt: str = Field(..., description="Portuguese explanation")
    expected: str = Field(..., description="What the rule requires")
    actual: str = Field(..., description="What was found")

    @field_validator("rule_id")
    @classmethod
    def _validate_rule_id(cls, v: str) -> str:
        if not _RULE_ID_PATTERN.match(v):
            raise ValueError(
                f"Rule ID '{v}' does not match pattern "
                f"<CATEGORY>-<NUMBER>"
            )
        return v


class Rule(BaseModel):
    """An engineering rule, citation-traceable."""
    id: str
    category: Category
    source: Source
    description_pt: str
    description_en: str
    severity: Severity = "error"

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        if not _RULE_ID_PATTERN.match(v):
            raise ValueError(
                f"Rule ID '{v}' does not match pattern "
                f"<CATEGORY>-<NUMBER>"
            )
        return v

    @field_validator("id")
    @classmethod
    def _category_matches_id(cls, v: str, info) -> str:
        # Cross-check that id prefix matches category if both set
        if "category" in info.data:
            prefix = v.split("-")[0]
            if prefix != info.data["category"]:
                raise ValueError(
                    f"Rule id prefix '{prefix}' does not match "
                    f"category '{info.data['category']}'"
                )
        return v


class Verifier(Protocol):
    def __call__(self, project: "Project") -> list[Violation]: ...


class RuleRegistry:
    """Module-level singleton holding all registered rules and verifiers."""

    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}
        self._verifiers: dict[str, Verifier] = {}

    def register(self, rule: Rule, verifier: Verifier) -> None:
        if rule.id in self._rules:
            raise ValueError(f"Rule {rule.id} already registered")
        self._rules[rule.id] = rule
        self._verifiers[rule.id] = verifier

    def get(self, rule_id: str) -> Rule:
        return self._rules[rule_id]

    def all(self) -> list[Rule]:
        return list(self._rules.values())

    def by_category(self, category: Category) -> list[Rule]:
        return [r for r in self._rules.values() if r.category == category]

    def run_all(self, project: "Project") -> list[Violation]:
        violations: list[Violation] = []
        for rule_id, verifier in self._verifiers.items():
            try:
                violations.extend(verifier(project))
            except Exception as e:
                # A verifier crash is itself a finding
                violations.append(Violation(
                    rule_id=rule_id,
                    severity="error",
                    message_pt=(
                        f"Verificador da regra {rule_id} falhou "
                        f"durante execução: {type(e).__name__}: {e}"
                    ),
                    expected="Verificador executa sem erro",
                    actual=f"Exceção: {e}",
                ))
        # Errors before warnings, then by rule_id
        violations.sort(key=lambda v: (v.severity != "error", v.rule_id))
        return violations


REGISTRY = RuleRegistry()
```

---

## Appendix C — Initial rules to encode in Phase 2

Each of these maps to one task in Phase 2. Encode in this order. The "Source" column is the citation that goes into the `Source.ref` field.

| Rule ID | Category | Description (PT) | Source | Severity |
|---|---|---|---|---|
| GEOM-001 | GEOM | Distância mínima de 0.70 m da face de qualquer pilar (zona de punção) | NBR 6118:2023 §19.5 | error |
| GEOM-002 | GEOM | Distância mínima de 0.15 m da borda da laje | Orguel practice + AGENTS.md | error |
| GEOM-003 | GEOM | Espaçamento mínimo de 0.30 m entre escoras adjacentes | Orguel practice + AGENTS.md | error |
| GEOM-004 | GEOM | Toda escora posicionada deve estar dentro do polígono real da laje | Implícito (definição de "escora suportando laje") | error |
| GEOM-005 | GEOM | Distância máxima de barrotes para alvenaria estrutural ≤ 5 cm | Orguel training §8 regra 12 | warning |
| GEOM-006 | GEOM | Extremidade de barrote em balanço: distância da última escora entre 20 e 40 cm | Orguel training §8 regra 11 | warning |
| SPACE-001 | SPACE | Espaçamento máximo de escoras em laje conforme tabela por espessura (10-16cm:1.30m; 17-24cm:1.20m; 25-30cm:1.10m; 31+:1.00m) | AGENTS.md spacing table | error |
| SPACE-002 | SPACE | Cruzetas sob vigas a cada 0.80 m | Engineer Q&A #5 | error |
| SPACE-003 | SPACE | VM50 em travamento lateral de viga: espaçamento entre 0.80 e 1.00 m | Engineer Q&A #4 | warning |
| STRUCT-001 | STRUCT | Toda interseção viga-viga sem pilar deve ter torre ou escora dentro de raio configurável | Engineer Q&A #3 | error |
| STRUCT-002 | STRUCT | Cantilever (balanço): suporte presente a ≤ 40 cm da extremidade | Orguel training §8 regra 11 | error |
| LOAD-001 | LOAD | Sobrecarga de trabalho ≥ 2.0 kN/m² | NBR 15696 §4.2 | error |
| LOAD-002 | LOAD | Carga estática total ≥ 4.0 kN/m² | NBR 15696 §4.2 | error |
| LOAD-003 | LOAD | Em vigas contínuas com 3+ apoios: acréscimo de 25% na reação central | Orguel training §7 (hiperestaticidade) | error |
| LOAD-004 | LOAD | Coeficiente de majoração γf = 1.4 aplicado a todas as cargas | NBR 15696 | error |
| EQUIP-001 | EQUIP | Altura > 4.50 m: nenhuma escora telescópica no BOM | Decision chain Q1 | error |
| EQUIP-002 | EQUIP | Equipamento selecionado existe no catálogo Orguel | catalog/equipment.yaml | error |
| EQUIP-003 | EQUIP | Utilização de torres entre 55% e 85% da capacidade | Engineer Q&A #10 | warning |
| ENV-001 | ENV | kg/m³ total no envelope [12, 16] | Engineer Q&A #8, Orguel 2026-04-07 (n=12) | warning |

---

## Appendix D — Standing prompt for Claude Code

Save this as `prompts/standing_prefix.md` and prepend it to every Claude Code session prompt:

```
You are working on Escora.AI, a shoring layout system for Brazilian 
civil construction. Read AGENTS.md and MIGRATION_PLAN.md before doing 
anything else.

Hard rules (non-negotiable):
1. Do not weaken any test to make it pass. If a test fails, the 
   implementation is wrong, not the test.
2. Do not invent norm references or numeric values. Every cited NBR 
   section, every numeric threshold, every spacing rule must come 
   from AGENTS.md, the Orguel training extracts, or the engineer 
   Q&A. If a value seems necessary but isn't documented, flag it as 
   `# TODO(engineer-confirmation)` and stop.
3. Every numeric output must carry a Source citation. The LoadValue 
   type enforces this. Any code path producing a numeric value 
   without a source is a bug.
4. Do not modify the regression suite (tests/regression/) without 
   explicit operator approval. The 12 Orguel projects are ground 
   truth.
5. No silent fallbacks. If the code cannot determine something, 
   raise a typed exception, not a default value.

Before declaring any task complete, run:
  pytest tests/unit/ tests/regression/ -v
and report the diff in pass/fail/xfail counts vs the previous run. 
If the regression suite shows MORE failures than before, you have 
introduced a regression — stop, revert, reframe.

Current task: <paste task block from MIGRATION_PLAN.md>
```

