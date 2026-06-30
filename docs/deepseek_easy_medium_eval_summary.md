# DeepSeek Easy + Medium + Hard Eval Summary

## Summary

All rows are live / real DeepSeek API runs with `deepseek-v4-flash`, prompt v3.

| difficulty | total | end_to_end_success | spec_success | checker_success | objective_match | main_failures |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| easy | 8 | 8/8 | 8/8 | 8/8 | 8/8 | none |
| medium | 8 | 8/8 | 8/8 | 8/8 | 8/8 | none |
| hard | 4 | 4/4 | 4/4 | 4/4 | 4/4 | none |
| all | 20 | 20/20 | 20/20 | 20/20 | 20/20 | none |

## Case Quality Gate

| difficulty | quality_result |
| --- | --- |
| easy | 8 passed, 0 failed |
| medium | 8 passed, 0 failed |
| hard | 4 passed, 0 failed |
| all | 20 passed, 0 failed |

## Output Locations

- easy live summary: `outputs/deepseek_extractor_eval/summary.json`
- medium live summary: `outputs/deepseek_extractor_eval/medium/summary.json`
- hard live summary: `outputs/deepseek_extractor_eval/hard/summary.json`
- final 20 live summary: `outputs/deepseek_extractor_eval/all/summary.json`
- medium failure analysis: `docs/deepseek_medium_failure_analysis.md`
- medium live report: `docs/deepseek_medium_live_eval_report.md`
- hard failure analysis: `docs/deepseek_hard_failure_analysis.md`
- hard live report: `docs/deepseek_hard_live_eval_report.md`
- final 20 failure analysis: `docs/deepseek_final_20_failure_analysis.md`
- final 20 live report: `docs/deepseek_final_20_eval_report.md`

## Next Step

The full 20-case live eval is now closed. The next work item should package the project results in README/report form rather than tune the prompt further.
