# DeepSeek Easy Extractor Live Eval Report

## Run Metadata

- Run time: 2026-06-30 16:47:40 +07:00
- prompt_version: v3
- model: deepseek-v4-flash
- Mode: live / real DeepSeek API
- Mock: false
- API key source: process_env
- API key handling: only key presence/source was checked; no key value, prefix, suffix, length, hash, request headers, or environment dump was written.

## Metrics

- total cases: 8
- passed: 8
- failed: 0
- pass rate: 100.0%
- router_accuracy: 8/8
- spec_success: 8/8
- execution_success: 8/8
- checker_success: 8/8
- objective_match: 8/8
- missing_required_fields: 0
- schema_validation_error: 0
- summary_path: `outputs/deepseek_extractor_eval/summary.json`

## Per-case Results

| case_id | category | difficulty | status | objective_value | failure_reason |
| --- | --- | --- | --- | ---: | --- |
| extractor_production_01 | production | easy | PASS | 2200.0 | none |
| extractor_production_02 | production | easy | PASS | 23.0 | none |
| extractor_assignment_01 | assignment | easy | PASS | 21.0 | none |
| extractor_assignment_02 | assignment | easy | PASS | 5.0 | none |
| extractor_jobshop_01 | jobshop | easy | PASS | 7.0 | none |
| extractor_jobshop_02 | jobshop | easy | PASS | 3.0 | none |
| extractor_vrp_01 | vrp | easy | PASS | 44.0 | none |
| extractor_vrp_02 | vrp | easy | PASS | 12.0 | none |

## Failure Breakdown

No failures were recorded in the latest live run.

`docs/deepseek_easy_failure_analysis.md` was regenerated from the same artifacts:

- completed_cases: 8
- end_to_end_pass_rate: 1.0
- failure_breakdown: {}

## What Changed in P3-T14

- Rewrote all 8 easy case prompts as complete UTF-8 Chinese text.
- Added the full numeric data required by each gold spec: production capacities/consumption, assignment cost matrices, jobshop operation durations, and VRP demands/capacities/distance matrices.
- Added case quality audit: `python -m nl2opt.eval.case_quality --difficulty easy`.
- Added `missing_required_fields` handling so valid extracted specs with missing required data stop before solver/checker.

## Interpretation

The previous low score was primarily an eval-input quality problem, not only a model quality problem. Once easy cases contained the information required by the schema and gold specs, DeepSeek v3 extracted valid specs for all 8 cases and the existing solver/checker pipeline passed them without relaxing constraints.

## Next Recommendation

Proceed to P3-T15 only if the next objective is to harden the evaluation framework before expanding. Suggested T15 scope:

1. Add the same case quality audit gate to future medium/20-case datasets.
2. Keep `missing_required_fields` as a separate failure category.
3. Add a small regression report comparing prompt v3 on the repaired easy cases.

It is also reasonable to start medium cases after preserving this easy-case baseline, because the repaired easy set is now 8/8 live.

## Safety Note

No API key, raw secret, request headers, or full environment dump were written to this report.
