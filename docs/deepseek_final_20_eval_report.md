# DeepSeek Final 20 Extractor Live Eval Report

## Run Metadata

- Run time: 2026-06-30
- provider: deepseek
- model: deepseek-v4-flash
- mock: false
- prompt_version: v3
- difficulty: all
- total_cases: 20
- output_dir: `outputs/deepseek_extractor_eval/all`
- API key handling: no key value, prefix, suffix, length, hash, request headers, or environment dump was written.

## Metrics By Difficulty

| difficulty | total | router_accuracy | spec_success | checker_success | objective_match | end_to_end_success | main_failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| easy | 8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | none |
| medium | 8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | none |
| hard | 4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | none |
| all | 20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | none |

## Case Results

| case_id | difficulty | category | objective_value | solver_status | checker | status |
| --- | --- | --- | ---: | --- | --- | --- |
| extractor_production_01 | easy | production | 2200.0 | OPTIMAL | PASS | OK |
| extractor_production_02 | easy | production | 23.0 | OPTIMAL | PASS | OK |
| extractor_assignment_01 | easy | assignment | 21.0 | OPTIMAL | PASS | OK |
| extractor_assignment_02 | easy | assignment | 5.0 | OPTIMAL | PASS | OK |
| extractor_jobshop_01 | easy | jobshop | 7.0 | OPTIMAL | PASS | OK |
| extractor_jobshop_02 | easy | jobshop | 3.0 | OPTIMAL | PASS | OK |
| extractor_vrp_01 | easy | vrp | 44.0 | FEASIBLE | PASS | OK |
| extractor_vrp_02 | easy | vrp | 12.0 | FEASIBLE | PASS | OK |
| extractor_production_medium_01 | medium | production | 3000.0 | OPTIMAL | PASS | OK |
| extractor_production_medium_02 | medium | production | 1480.0 | OPTIMAL | PASS | OK |
| extractor_assignment_medium_01 | medium | assignment | 23.0 | OPTIMAL | PASS | OK |
| extractor_assignment_medium_02 | medium | assignment | 21.0 | OPTIMAL | PASS | OK |
| extractor_jobshop_medium_01 | medium | jobshop | 10.0 | OPTIMAL | PASS | OK |
| extractor_jobshop_medium_02 | medium | jobshop | 9.0 | OPTIMAL | PASS | OK |
| extractor_vrp_medium_01 | medium | vrp | 28.0 | FEASIBLE | PASS | OK |
| extractor_vrp_medium_02 | medium | vrp | 28.0 | FEASIBLE | PASS | OK |
| extractor_production_hard_01 | hard | production | 3300.0 | OPTIMAL | PASS | OK |
| extractor_assignment_hard_01 | hard | assignment | 27.0 | OPTIMAL | PASS | OK |
| extractor_jobshop_hard_01 | hard | jobshop | 13.0 | OPTIMAL | PASS | OK |
| extractor_vrp_hard_01 | hard | vrp | 64.0 | FEASIBLE | PASS | OK |

## Failure Analysis

`docs/deepseek_final_20_failure_analysis.md` was generated from `outputs/deepseek_extractor_eval/all`.

- completed_cases: 20
- end_to_end_pass_rate: 1.0
- failure_breakdown: none

## Re-run Commands

```bash
python -m nl2opt.eval.case_quality --difficulty all
python -m nl2opt.eval.extractor_eval --prompt-version v3 --difficulty all
python -m nl2opt.eval.failure_analysis --eval-dir outputs/deepseek_extractor_eval/all --report docs/deepseek_final_20_failure_analysis.md
```
