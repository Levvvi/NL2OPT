# Task 9 audit recovery implementation report

## Status

Implemented crash-safe translation audit persistence and resume recovery, plus the audited numeric-mismatch rejection semantics required by the Task 9 brief.

## RED evidence

Command:

```powershell
pytest -q tests/test_benchmark.py::test_resume_repairs_missing_sampled_failure_audit_from_artifact_without_execution tests/test_benchmark.py::test_resume_missing_sampled_audit_fails_closed_without_changing_csvs tests/test_benchmark.py::test_runner_flushes_audit_and_result_rows_at_each_attempt_boundary tests/test_bench_report.py::test_report_accepts_rejected_number_mismatch_and_keeps_attempt_in_total tests/test_bench_report.py::test_report_refuses_non_rejected_number_mismatch --basetemp .tmp_pytest_basetemp_task9_red
```

Result: `7 failed, 3 warnings in 0.88s` (exit 1). Failures showed that resume left the missing audit row absent, missing/inconsistent artifacts did not fail closed, audit/result rows were not visible at attempt boundaries, rejected mismatches were refused, and approved/waived mismatch diagnostics did not enforce rejected status.

## GREEN evidence

Focused command:

```powershell
pytest -q tests/test_benchmark.py::test_resume_repairs_missing_sampled_failure_audit_from_artifact_without_execution tests/test_benchmark.py::test_resume_missing_sampled_audit_fails_closed_without_changing_csvs tests/test_benchmark.py::test_runner_flushes_audit_and_result_rows_at_each_attempt_boundary tests/test_bench_report.py::test_report_accepts_rejected_number_mismatch_and_keeps_attempt_in_total tests/test_bench_report.py::test_report_refuses_non_rejected_number_mismatch --basetemp .tmp_pytest_basetemp_task9_green
```

Result: `7 passed, 3 warnings in 0.50s` (exit 0).

Full scoped command:

```powershell
pytest -q tests/test_benchmark.py tests/test_bench_report.py --basetemp .tmp_pytest_basetemp_task9
```

Result: `127 passed, 3 warnings in 2.88s` (exit 0).

## Changed files

- `src/nl2opt/eval/benchmark.py`
- `src/nl2opt/eval/bench_report.py`
- `tests/test_benchmark.py`
- `tests/test_bench_report.py`
- `.superpowers/sdd/task-9-audit-recovery-report.md`

## Recovery design

Resume retains the existing manifest-validation order, then identifies persisted sampled Chinese result keys missing from the audit CSV. It loads and validates every required failure artifact before either CSV is opened for append. Validation binds dataset, item ID, Chinese track, repetition, checker mode, and source text to the selected benchmark item and requires a complete non-null translation mapping. Any missing or inconsistent artifact raises a contextual `ValueError` without changing the result or audit CSV.

Validated translations are converted through the same CSV serialization rules as live audit writes, appended as `pending` with empty notes, and flushed individually. Existing audit keys are updated after each repair, making repeated resume idempotent. Live sampled Chinese audit writes are flushed before attempt execution and result rows are flushed immediately after each write, preserving audit-before-result persistence.

Report validation now permits `numbers_match == false` only for a human `rejected` row. Approved and waived mismatches still fail, pending/unknown statuses remain incomplete, and existing coverage, matrix, duplicate, protocol, model, and output gates are unchanged.

## Concerns

- The test process emits three pre-existing SWIG deprecation warnings; there are no test failures.
- Recovery intentionally cannot recreate a lost audit row for a successful result because successful rows have no failure artifact. Such a resume fails closed and requires external operator intervention, as specified.
