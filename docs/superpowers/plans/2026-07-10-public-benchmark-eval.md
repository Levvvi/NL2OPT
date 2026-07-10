# Public Benchmark Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible NL4Opt/IndustryOR public-benchmark evaluation path to NL2OPT without changing the existing v3 self-built evaluation contract.

**Architecture:** Extend the schema-first pipeline with a fifth strictly linear problem type and an independently checked generic solver. Add a separate benchmark package that pins public data, runs bilingual attempts with resumable artifacts, and renders reports from recorded CSV rows.

**Tech Stack:** Python 3.11, Pydantic v2, OR-Tools GLOP/SCIP, Jinja2, pytest, standard-library CSV/JSON/statistics.

## Global Constraints

- Use only repaired NL4Opt (245 rows) and IndustryOR fixedV2 (100 rows); manifest must pin source revision, SHA-256, source URL, license and expected row count.
- Use UTF-8 for every input and artifact; do not put API keys in files, output, reports or git.
- Benchmark defaults are temperature 0, timeout 60 seconds, 3 repetitions, tolerance 1e-6 and an additional 1e-4 result column.
- All non-numeric/infeasible/unsupported/API/timeout outcomes stay in the denominator.
- Keep existing prompt version v3 and its tests semantically unchanged; use v4 for language-neutral public-benchmark extraction.
- Do not add commercial solvers or non-standard runtime dependencies.

---

### Task 1: Generic LP/MILP pipeline support

**Files:**
- Create: `src/nl2opt/schemas/generic_lp.py`, `src/nl2opt/checkers/generic_lp_checker.py`, `src/nl2opt/solvers/templates/generic_lp.py.j2`, `tests/test_generic_lp_schema.py`, `tests/test_generic_lp_pipeline.py`, `tests/test_generic_lp_checker.py`
- Modify: `src/nl2opt/schemas/{base.py,__init__.py}`, `src/nl2opt/{pipeline.py,agents/router.py,agents/extractor.py,agents/normalizer.py,agents/prompts.py,solvers/render.py}`, relevant existing router/prompt tests.

**Interfaces:**
- Add `ProblemType.GENERIC_LP_MILP = "generic_lp_milp"`.
- `GenericVariableSpec(name: str, lb: float, ub: float | None, is_integer: bool)` requires unique names, finite `lb`, finite-or-null `ub`, and `ub >= lb`.
- `LinearTerm(var: str, coef: float)`, `LinearConstraint(terms: list[LinearTerm], op: Literal["<=", ">=", "=="], rhs: float)`, `GenericObjectiveSpec(sense: ObjectiveSense, name: str, terms: list[LinearTerm])`, and `GenericLpSpec(problem_id, problem_type, variables, objective, constraints, assumptions, missing_fields)` reject unknown variables, empty terms and non-finite coefficients/RHS.
- `UnsupportedProblemSpec(problem_id, problem_type="unsupported", reason)` is valid only for generic extraction; `extract_problem_spec` returns it as a successful explicit refusal.
- Generic feasible results use `solution["variables"]`; continuous models use GLOP and any integer model uses SCIP. A generic checker treats an independently verified infeasible result as checker-passed, but does not change legacy checker behavior.

- [ ] **Step 1: Write failing tests**

```python
def test_generic_lp_pipeline_uses_glop_and_matches_objective(tmp_path):
    result = run_problem_spec(continuous_generic_spec(), tmp_path, timeout_sec=5)
    assert result.solver_status == "OPTIMAL"
    assert result.checker_passed is True
    assert result.objective_value == 10.0

def test_generic_checker_verifies_infeasible_by_independent_feasibility_model():
    report = check_generic_solution(infeasible_generic_spec(), infeasible_result())
    assert report.passed is True
    assert report.details["infeasibility_verified"] is True
```

- [ ] **Step 2: Verify the tests fail before implementation**

Run: `pytest -q tests/test_generic_lp_schema.py tests/test_generic_lp_pipeline.py tests/test_generic_lp_checker.py --basetemp .tmp_pytest_basetemp_task1`

Expected: import failures because the generic modules and `ProblemType` member do not yet exist.

- [ ] **Step 3: Implement the smallest pipeline extension**

```python
if any(variable.is_integer for variable in SPEC["variables"]):
    solver = pywraplp.Solver.CreateSolver("SCIP")
else:
    solver = pywraplp.Solver.CreateSolver("GLOP")
```

Route Chinese and English linear wording to `generic_lp_milp`; reject clear nonlinear/stochastic/dynamic wording before generic matching. Add v4 prompt guidance that allows the `UnsupportedProblemSpec` variant only for non-representable problems.

- [ ] **Step 4: Verify task and regressions**

Run: `pytest -q tests/test_generic_lp_schema.py tests/test_generic_lp_pipeline.py tests/test_generic_lp_checker.py tests/test_router.py tests/test_prompt_v3.py tests/test_prompt_versions.py --basetemp .tmp_pytest_basetemp_task1_green`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/nl2opt tests
git commit -m "feat: add generic LP MILP pipeline"
```

### Task 2: Pinned data and resumable benchmark harness

**Files:**
- Create: `eval/datasets/{NL4Opt_fixed.jsonl,IndustryOR_fixedV2.jsonl,manifest.json}`, `src/nl2opt/eval/{benchmark.py,run_bench.py}`, `tests/test_benchmark.py`
- Modify: `README.md` only to document the benchmark command, without publishing unverified metrics.

**Interfaces:**
- `load_benchmark_dataset(name: str, datasets_dir: Path) -> list[BenchmarkItem]` verifies manifest hash and exact expected count before returning UTF-8 rows.
- `judge_benchmark_result(prediction, ground_truth, spec, checker_passed, tolerance)` returns both 1e-6 and 1e-4 verdicts. It accepts an infeasible answer only for status `INFEASIBLE` with an independently verified checker report.
- `run_benchmark(config: BenchmarkRunConfig) -> Path` stores one CSV row per `(dataset,item_id,track,repetition,checker_retry)` and skips an existing key only when `resume=True`.
- CLI accepts `--dataset {all,nl4opt,industryor}`, `--track {all,en,zh}`, `--repetitions`, `--checker-retry {on,off}`, `--resume`, `--limit`, `--timeout-sec`, and `--run-id`.

- [ ] **Step 1: Write failing tests**

```python
def test_loader_rejects_manifest_hash_mismatch(tmp_path):
    with pytest.raises(ValueError, match="sha256"):
        load_benchmark_dataset("nl4opt", tmp_path)

def test_resume_does_not_duplicate_completed_attempt(tmp_path):
    run_benchmark(fake_config(tmp_path))
    run_benchmark(fake_config(tmp_path, resume=True))
    assert count_csv_rows(tmp_path / "results.csv") == 1
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q tests/test_benchmark.py --basetemp .tmp_pytest_basetemp_task2`

Expected: import failure for `nl2opt.eval.benchmark`.

- [ ] **Step 3: Implement data, translations and artifacts**

Use a fixed terminology map for Chinese translations; rerun translation for every repetition, store its model/usage, and compare all Arabic-number tokens before extraction. Retry API transport failures at 2, 4, 8, 16 and 32 seconds. Save full artifacts only for failures, and write a deterministic 10% translation-audit CSV.

- [ ] **Step 4: Verify task**

Run: `pytest -q tests/test_benchmark.py --basetemp .tmp_pytest_basetemp_task2_green`

Expected: all manifest, judge, retry, resume, artifact and translation-diff tests pass.

- [ ] **Step 5: Commit**

```bash
git add eval src/nl2opt/eval tests/test_benchmark.py README.md
git commit -m "feat: add reproducible public benchmark runner"
```

### Task 3: Reporting, claims and external material

**Files:**
- Create: `src/nl2opt/eval/bench_report.py`, `tests/test_bench_report.py`, `docs/claim_registry.md`
- Modify: `README.md`, `docs/interview_notes.md`; create `reports/bench_report.md` only after a completed, audited real run.

**Interfaces:**
- `wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]` produces per-repetition intervals.
- `render_benchmark_report(results_csv: Path, run_manifest: Path, audit_csv: Path, output: Path) -> Path` refuses a public result report when the audit is incomplete.

- [ ] **Step 1: Write failing tests**

```python
def test_wilson_interval_for_all_successes_is_bounded():
    low, high = wilson_interval(10, 10)
    assert 0 < low < 1
    assert high == 1

def test_report_refuses_incomplete_translation_audit(tmp_path):
    with pytest.raises(ValueError, match="audit"):
        render_benchmark_report(results_csv, manifest, incomplete_audit, tmp_path / "report.md")
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q tests/test_bench_report.py --basetemp .tmp_pytest_basetemp_task3`

Expected: import failure for `nl2opt.eval.bench_report`.

- [ ] **Step 3: Implement report rendering and claim placeholders**

Render Chinese results with an English executive summary, main dual-track table, per-repetition Wilson bounds, IndustryOR type/difficulty decomposition, failure distribution, 1e-4 sensitivity, retry ablation and the four required limitations. Keep literature values in a separate sourced reference section. Claim registry contains provenance and a result template; README/interview content must not state public numbers before a verified run.

- [ ] **Step 4: Verify task**

Run: `pytest -q tests/test_bench_report.py --basetemp .tmp_pytest_basetemp_task3_green`

Expected: all interval and report-gating/snapshot tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/nl2opt/eval tests/test_bench_report.py docs README.md
git commit -m "feat: add benchmark reporting and claims"
```

### Task 4: Live calibration and publication gate

**Files:**
- Create only run artifacts under ignored `eval/results/<run-id>/`; after audit, create `reports/bench_report.md` and update claims/README/interview copy with actual values.

**Interfaces:**
- Smoke command: `python -m nl2opt.eval.run_bench --dataset all --track all --repetitions 1 --checker-retry off --limit 5 --timeout-sec 60 --run-id smoke-YYYYMMDD`.
- Full command: `python -m nl2opt.eval.run_bench --dataset all --track all --repetitions 3 --checker-retry on --timeout-sec 60 --run-id public-YYYYMMDD` and a matching `checker-retry off` run.

- [ ] **Step 1: Run the 5-item live smoke test and inspect model/version/cost artifacts**
- [ ] **Step 2: Run both full ablation configurations and resume any interrupted rows**
- [ ] **Step 3: Complete all rows in the deterministic 10% Chinese translation audit CSV**
- [ ] **Step 4: Render the audited report and update externally visible claims with the observed numbers only**
- [ ] **Step 5: Run the full test suite using a project-local pytest base temp directory and commit all publishable artifacts**

## Self-review

- Tasks 1-3 cover Schema, router, prompts, solvers, checker, data provenance, benchmark execution, retry/resume, reporting, claims and documentation.
- Task 4 is intentionally separate because it incurs API cost and requires human translation review; no public metric is fabricated before that gate.
- Public type names, CLI flags, tolerances, sample counts and solver choices are consistent across all tasks.
