# Task 5 full-run readiness report

## Scope delivered

- Captured response-backed extraction usage in `BenchmarkAttempt.details`, serialized it as `extractor_usage` in every result row, and recorded it in every failure artifact. Rows without an extraction request remain empty, and downstream pipeline errors retain already captured extraction telemetry.
- Added `summarize_token_usage(rows)`, a standard-library-only helper that separately totals translation and extraction prompt, completion, and total tokens from parseable CSV JSON fields.
- Extended report rendering with independently validated off/on retry-comparison artifacts. Comparison runs require complete public matrices and audits, matching dataset revisions and selected IDs, primary `checker_retry="off"`, and comparison `checker_retry="on"`.
- Rendered a two-row retry-ablation table only when both matching runs are present; otherwise the one-row table carries a Chinese pending-ablation warning that does not claim the ablation ran.
- Added `python -m nl2opt.eval.bench_report` CLI arguments for primary and optional comparison artifacts.

## RED evidence

Command:

```text
pytest -q tests/test_benchmark.py::test_runner_serializes_extractor_usage_for_response_backed_failure tests/test_benchmark.py::test_summarize_token_usage_separates_translation_and_extraction_tokens tests/test_bench_report.py::test_report_renders_two_complete_checker_retry_runs_as_an_ablation tests/test_bench_report.py::test_report_rejects_retry_comparison_with_incompatible_dataset_scope tests/test_bench_report.py::test_report_marks_checker_retry_ablation_pending_without_comparison_artifacts tests/test_bench_report.py::test_report_cli_accepts_primary_and_optional_comparison_artifacts --basetemp .tmp_pytest_basetemp_task5_red
```

Observed expected failure before implementation:

```text
ImportError: cannot import name 'summarize_token_usage'
ImportError: cannot import name 'build_parser'
```

The tests therefore failed because the requested helper and report CLI did not exist yet.

Independent review identified a downstream-exception edge case. Its dedicated RED command was:

```text
pytest -q tests/test_benchmark.py::test_pipeline_error_preserves_response_backed_extractor_usage --basetemp .tmp_pytest_basetemp_task5_review_red
```

It failed as expected because the row had an empty `extractor_usage` field after a real extraction response followed by a `run_problem_spec` exception. The minimal fix preserves `extraction_details` in the outer error handler.

## GREEN evidence

Focused coverage after implementation:

```text
7 passed, 3 warnings in 0.39s
```

Required task command:

```text
pytest -q tests/test_benchmark.py tests/test_bench_report.py --basetemp .tmp_pytest_basetemp_task5_green
48 passed, 3 warnings in 0.93s
```

The three warnings are existing OR-Tools SWIG deprecation warnings emitted during imports; no test errors or failures occurred.

## Tests added or extended

- Extraction usage reaches failed CSV rows and their failure artifacts.
- Extraction usage remains available when a successful real extraction is followed by a downstream pipeline exception.
- Token usage sums translation and extraction fields independently and ignores absent or invalid JSON.
- A complete matching off/on pair produces exactly two retry-ablation rows.
- Mismatched dataset revisions and selected item scopes are rejected.
- A single run explicitly labels the retry ablation as pending.
- Report CLI accepts all primary and optional comparison artifact arguments.
- Rows that skip extraction keep `extractor_usage` empty.

## Changed files

- `src/nl2opt/eval/benchmark.py`
- `src/nl2opt/eval/bench_report.py`
- `tests/test_benchmark.py`
- `tests/test_bench_report.py`

## Self-review

- `git diff --check` completed without whitespace errors.
- No live API calls were made while implementing or testing; test coverage uses `MockLLMClient` and synthetic artifacts.
- No dependencies, vendor data, dataset files, or public claims were changed.
- The existing untracked real smoke artifacts in `eval/results/` were preserved and excluded from the task change set.
- Comparison validation occurs before writing the report, so invalid partial, mismatched, incomplete, or unaudited comparison artifacts cannot produce an ablation claim.
- Independent read-only review found and verified the downstream-exception telemetry fix; no remaining Critical or Important issue was identified after the regression test and final full test run.
