# DeepSeek Extractor Failure Analysis

## Status
Analysis generated from the current DeepSeek eval artifacts.

## Metrics
- total: 20
- completed_cases: 20
- end_to_end_success: 20
- end_to_end_pass_rate: 1.0

## Failure Breakdown
- none

## Per-case Analysis
| case_id | type | stage | objective | message | suggested_action |
| --- | --- | --- | --- | --- | --- |
| extractor_assignment_01 | assignment | success | 21.0 / expected 21 |  | No action needed. |
| extractor_assignment_02 | assignment | success | 5.0 / expected 5 |  | No action needed. |
| extractor_assignment_hard_01 | assignment | success | 27.0 / expected 27 |  | No action needed. |
| extractor_assignment_medium_01 | assignment | success | 23.0 / expected 23 |  | No action needed. |
| extractor_assignment_medium_02 | assignment | success | 21.0 / expected 21 |  | No action needed. |
| extractor_jobshop_01 | jobshop | success | 7.0 / expected 7 |  | No action needed. |
| extractor_jobshop_02 | jobshop | success | 3.0 / expected 3 |  | No action needed. |
| extractor_jobshop_hard_01 | jobshop | success | 13.0 / expected 13 |  | No action needed. |
| extractor_jobshop_medium_01 | jobshop | success | 10.0 / expected 10 |  | No action needed. |
| extractor_jobshop_medium_02 | jobshop | success | 9.0 / expected 9 |  | No action needed. |
| extractor_production_01 | production | success | 2200.0 / expected 2200 |  | No action needed. |
| extractor_production_02 | production | success | 23.0 / expected 23 |  | No action needed. |
| extractor_production_hard_01 | production | success | 3300.0 / expected 3300 |  | No action needed. |
| extractor_production_medium_01 | production | success | 3000.0 / expected 3000 |  | No action needed. |
| extractor_production_medium_02 | production | success | 1480.0 / expected 1480 |  | No action needed. |
| extractor_vrp_01 | vrp | success | 44.0 / expected 44 |  | No action needed. |
| extractor_vrp_02 | vrp | success | 12.0 / expected 12 |  | No action needed. |
| extractor_vrp_hard_01 | vrp | success | 64.0 / expected 64 |  | No action needed. |
| extractor_vrp_medium_01 | vrp | success | 28.0 / expected 28 |  | No action needed. |
| extractor_vrp_medium_02 | vrp | success | 28.0 / expected 28 |  | No action needed. |

## Suggested Next Actions
- No immediate action.

## Re-run Commands
```bash
python -m nl2opt.eval.extractor_eval --provider deepseek --prompt-version v3
python -m nl2opt.eval.failure_analysis --eval-dir outputs/deepseek_extractor_eval --report docs/deepseek_easy_failure_analysis.md
```
