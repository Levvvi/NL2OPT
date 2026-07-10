# Task 4 smoke-calibration repair: RED/GREEN report

Date: 2026-07-10
Worktree: C:\Users\levil\Documents\NL2OPT\.worktrees\benchmark-eval
Branch: codex/benchmark-eval

## Scope and safeguards

- Implemented only the router and benchmark harness repair described in
  task-4-smoke-repair-brief.md, plus its focused tests.
- Did not make DeepSeek or other live API calls.
- Did not edit vendored datasets or any public benchmark claim.
- Preserved the pre-existing, untracked eval/results/smoke-20260710/ smoke
  evidence and excluded it from the commit.
- Did not run the slow full suite.

## Root cause

The preserved smoke failure artifacts showed ordinary English LP prompts such
as the duck-transport example being routed as unsupported. The router only
recognized explicit generic-LP labels and therefore missed ordinary
objective/constraint wording such as "minimize", "at most", and "at least".

_run_default_attempt then passed ProblemType.UNSUPPORTED to
extract_problem_spec, producing an avoidable extraction error:

"unsupported problem_type; extractor only supports production, assignment,
jobshop, vrp, and generic_lp_milp"

The CSV and failure-artifact serializers also had no failure category, router
route, extractor identity, wall-clock, or evaluation-time fields. The manifest
had no start/completion timestamps.

## RED

Added focused tests before implementation for:

- ordinary English and Chinese generic optimization wording;
- nonlinear rejection precedence (the existing rejection regression remains);
- unsupported-router short-circuiting without invoking the extractor;
- response-backed extractor telemetry in CSV and failure artifacts;
- UTC started_at / completed_at manifest fields;
- each required failure-category outcome, including translation-number
  mismatch as EXTRACT_ERR.

Command:

~~~
pytest -q tests/test_router.py tests/test_benchmark.py tests/test_bench_report.py --basetemp .tmp_pytest_basetemp_task4_repair_red
~~~

Result: 11 failed, 38 passed, 3 warnings in 1.16s.

Expected failures:

1. The ordinary English minimization statement routed to unsupported.
2. The unsupported route still invoked the extractor and returned ERROR.
3. Failure telemetry and category assertions raised KeyError because
   failure_category and related CSV fields did not exist.
4. The category parametrization and translation mismatch regression failed for
   the same missing telemetry field.

## GREEN implementation

- Added generic objective/constraint fallback signals in English and Chinese.
  The fallback runs only after the existing nonlinear/stochastic/dynamic
  rejection check and only if no specialized-family rule matched, preserving
  specialized and rejection precedence.
- Made _run_default_attempt return BenchmarkAttempt(status="UNSUPPORTED")
  immediately for an unsupported route. It records router_problem_type and
  router_reason without calling the extractor.
- Captured routed type/reason for every default extraction attempt and copied
  actual extractor provider/model from response-backed extraction results.
- Added failure_category, router_problem_type, extractor_provider,
  extractor_model, wall_sec, and evaluated_at to every CSV row.
- Added matching category/route, extractor, wall-clock, and evaluation-time
  metadata to failure artifacts.
- Added UTC ISO-8601 started_at and completed_at values ending in Z to
  run_manifest.json.
- Implemented the protocol mapping:

  | Condition | Category |
  | --- | --- |
  | Route/spec refusal | UNSUPPORTED |
  | Transport/client failure | API_ERR |
  | Extraction or translation failure | EXTRACT_ERR |
  | Solver timeout | SOLVE_TIMEOUT |
  | Infeasibility judgment failure | INFEASIBLE_MISMATCH |
  | Numeric objective mismatch | WRONG_OPT |
  | Other solver/checker execution failure | CODEGEN_ERR |

  Passing rows receive an empty failure_category.

## Final verification

Command:

~~~
pytest -q tests/test_router.py tests/test_benchmark.py tests/test_bench_report.py --basetemp .tmp_pytest_basetemp_task4_repair_green
~~~

Result: 49 passed, 3 warnings in 0.99s.

The three warnings are pre-existing SWIG deprecation warnings emitted while
importing the solver stack; no test failed. git diff --check also completed
without whitespace errors.

## Concerns

- The requested focused suite passes, but the slow full suite was intentionally
  not run per task scope.
- Existing untracked smoke artifacts remain in the worktree and are not part of
  this repair commit.

## Review follow-up: TDD repair

Review identified three protocol gaps in the first repair:

1. A lone constraint phrase could trigger the generic fallback.
2. Resume could append rows beneath an older, incompatible telemetry header.
3. PermissionError, a filesystem/codegen failure, inherited from OSError and
   was incorrectly treated as a transport/API failure.

The existing failure-artifact telemetry regression was also extended to verify
router_reason, extractor provider/model, nonnegative wall duration, and a UTC
evaluation timestamp.

### RED

Command:

~~~
pytest -q tests/test_router.py tests/test_benchmark.py tests/test_bench_report.py --basetemp .tmp_pytest_basetemp_task4_review_red
~~~

Result: 3 failed, 49 passed, 3 warnings in 1.18s.

- "Please write a poem with at most twelve lines." routed as
  generic_lp_milp instead of unsupported.
- A two-column legacy CSV reached KeyError for the missing track column instead
  of receiving an explicit schema error before append.
- A mocked pipeline PermissionError was emitted as API_ERROR instead of ERROR
  with CODEGEN_ERR classification.

### GREEN

- Split generic routing terms into objective, modeling, and constraint groups.
  A no-specialist route now needs an objective signal, or at least two modeling
  signals. A constraint-only phrase is explicitly unsupported.
- Validate every nonempty results CSV header exactly against _RESULT_FIELDS
  before any append or resume processing.
- Removed broad OSError transport treatment, retaining connection and timeout
  failures as transport failures so local filesystem/codegen errors remain
  CODEGEN_ERR.

Command:

~~~
pytest -q tests/test_router.py tests/test_benchmark.py tests/test_bench_report.py --basetemp .tmp_pytest_basetemp_task4_review_green
~~~

Result: 52 passed, 3 warnings in 1.06s.

The warnings are the pre-existing SWIG deprecation warnings from the solver
stack. No live benchmark or API request was run.

## Final router follow-up: TDD repair

The final review found that the multi-signal generic fallback was too strict
for direct LP/MILP declarations and too permissive for bare objective nouns.

### RED

Command:

~~~
pytest -q tests/test_router.py tests/test_benchmark.py tests/test_bench_report.py --basetemp .tmp_pytest_basetemp_task4_final_router_red
~~~

Result: 2 failed, 52 passed, 3 warnings in 1.09s.

- "This is a linear program." was unsupported because it had one modeling
  signal and no objective verb.
- "The cost of this book is five dollars." routed to generic_lp_milp because
  cost alone was treated as an objective signal.

### GREEN

- Added a direct LP/MILP keyword route immediately after the nonlinear,
  stochastic, and dynamic rejection check. It covers linear program, linear
  programming, integer programming, mixed integer, MILP, and the direct
  Chinese equivalents.
- Split objective verbs from objective nouns. Only minimize/maximize and their
  Chinese equivalents qualify as a one-signal fallback; noun-only wording now
  needs modeling and constraint structure.
- Existing specialized routing remains before the non-direct generic fallback,
  and rejection precedence remains unchanged.

Command:

~~~
pytest -q tests/test_router.py tests/test_benchmark.py tests/test_bench_report.py --basetemp .tmp_pytest_basetemp_task4_final_router_green
~~~

Result: 54 passed, 3 warnings in 1.01s.

The warnings are the pre-existing SWIG deprecation warnings from the solver
stack. No live benchmark or API request was run.
