# DeepSeek Extractor Failure Analysis

## Status
Analysis generated from the current DeepSeek eval artifacts.

## Metrics
- total: 4
- completed_cases: 4
- end_to_end_success: 4
- end_to_end_pass_rate: 1.0

## Failure Breakdown
- none

## Per-case Analysis
| case_id | type | stage | objective | message | suggested_action |
| --- | --- | --- | --- | --- | --- |
| extractor_assignment_hard_01 | assignment | success | 27.0 / expected 27 |  | No action needed. |
| extractor_jobshop_hard_01 | jobshop | success | 13.0 / expected 13 |  | No action needed. |
| extractor_production_hard_01 | production | success | 3300.0 / expected 3300 |  | No action needed. |
| extractor_vrp_hard_01 | vrp | success | 64.0 / expected 64 |  | No action needed. |

## Suggested Next Actions
- No immediate action.

## Re-run Commands
```bash
python -m nl2opt.eval.extractor_eval --provider deepseek --prompt-version v3
python -m nl2opt.eval.failure_analysis --eval-dir outputs/deepseek_extractor_eval --report docs/deepseek_easy_failure_analysis.md
```
