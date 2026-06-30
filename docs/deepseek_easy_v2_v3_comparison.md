# DeepSeek Easy v2/v3 Comparison

## Summary

All rows below are live / real DeepSeek API runs with `deepseek-v4-flash`, not mock runs.

| prompt_version | case set | total | router_accuracy | spec_success | checker_success | objective_match | end_to_end_success | main_failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| v2 | original underspecified easy cases | 8 | 8/8 | 2/8 | 1/8 | 0/8 | 0/8 | schema_validation_error=6; checker_failed=1; objective_mismatch=2 |
| v3 | original underspecified easy cases | 8 | 8/8 | 2/8 | 1/8 | 1/8 | 1/8 | schema_validation_error=6; checker_failed=1; objective_mismatch=1 |
| v3 | repaired complete easy cases | 8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | none |

## What Changed in P3-T14

- Repaired the 8 easy case prompts so they are complete UTF-8 Chinese problem statements.
- Added all required numeric information to the prompt text instead of expecting DeepSeek to infer it.
- Added `id` and `prompt_zh` while keeping `text` for backward compatibility.
- Added `case_quality` audit to detect missing matrices, missing numeric information, and mojibake-like text.
- Added `missing_required_fields` as a separate eval failure stage before solver/checker.

## Interpretation

The T13 v3 prompt and normalizer improved only one case on the original underspecified easy set. T14 shows that the main blocker was case quality: the original easy prompts did not contain enough information to reconstruct the gold specs.

After the easy prompts were repaired, the same v3 extractor path produced valid specs for all 8 cases and the existing codegen, solver, checker, and objective checks all passed.

## Recommendation

Use the repaired easy set as the baseline before expanding. The next step can move toward medium cases or a 20-case set, but only with a case quality gate applied first. For every future case, the prompt must include the required schema data needed by the gold spec, especially:

- production: full resource capacities and consumption matrix.
- assignment: full employee-task cost matrix.
- jobshop: full operation machine/duration sequence.
- vrp: full vehicle capacity, customer demand, and distance matrix.
