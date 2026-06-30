# DeepSeek Extractor Failure Analysis

## Status
Analysis generated from the current DeepSeek eval artifacts.

## Metrics
- total: 8
- completed_cases: 8
- end_to_end_success: 8
- end_to_end_pass_rate: 1.0

## Failure Breakdown
- none

## Per-case Analysis
| case_id | type | stage | objective | message | suggested_action |
| --- | --- | --- | --- | --- | --- |
| extractor_assignment_medium_01 | assignment | success | 23.0 / expected 23 |  | No action needed. |
| extractor_assignment_medium_02 | assignment | success | 21.0 / expected 21 |  | No action needed. |
| extractor_jobshop_medium_01 | jobshop | success | 10.0 / expected 10 |  | No action needed. |
| extractor_jobshop_medium_02 | jobshop | success | 9.0 / expected 9 |  | No action needed. |
| extractor_production_medium_01 | production | success | 3000.0 / expected 3000 |  | No action needed. |
| extractor_production_medium_02 | production | success | 1480.0 / expected 1480 |  | No action needed. |
| extractor_vrp_medium_01 | vrp | success | 28.0 / expected 28 |  | No action needed. |
| extractor_vrp_medium_02 | vrp | success | 28.0 / expected 28 |  | No action needed. |

## Suggested Next Actions
- No immediate action.

## Re-run Commands
```bash
python -m nl2opt.eval.extractor_eval --provider deepseek --prompt-version v3
python -m nl2opt.eval.failure_analysis --eval-dir outputs/deepseek_extractor_eval --report docs/deepseek_easy_failure_analysis.md
```
