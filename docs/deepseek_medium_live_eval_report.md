# DeepSeek Medium Extractor Live Eval Report

## Run Metadata

- Run time: 2026-06-30
- provider: deepseek
- model: deepseek-v4-flash
- mock: false
- prompt_version: v3
- difficulty: medium
- output_dir: `outputs/deepseek_extractor_eval/medium`
- API key handling: only key presence/source was checked; no key value, prefix, suffix, length, hash, request headers, or environment dump was written.

## Metrics

- total_cases: 8
- router_accuracy: 8/8
- spec_success: 8/8
- checker_success: 8/8
- objective_match: 8/8
- end_to_end_success: 8/8
- failure_breakdown: none

## Per-case Results

| case_id | category | objective_value | solver_status | checker | status |
| --- | --- | ---: | --- | --- | --- |
| extractor_production_medium_01 | production | 3000.0 | OPTIMAL | PASS | OK |
| extractor_production_medium_02 | production | 1480.0 | OPTIMAL | PASS | OK |
| extractor_assignment_medium_01 | assignment | 23.0 | OPTIMAL | PASS | OK |
| extractor_assignment_medium_02 | assignment | 21.0 | OPTIMAL | PASS | OK |
| extractor_jobshop_medium_01 | jobshop | 10.0 | OPTIMAL | PASS | OK |
| extractor_jobshop_medium_02 | jobshop | 9.0 | OPTIMAL | PASS | OK |
| extractor_vrp_medium_01 | vrp | 28.0 | FEASIBLE | PASS | OK |
| extractor_vrp_medium_02 | vrp | 28.0 | FEASIBLE | PASS | OK |

## Notes

The medium set contains 2 production, 2 assignment, 2 jobshop, and 2 VRP/CVRP cases. All cases passed the case quality gate before live evaluation. No checker logic or gold objective values were relaxed.

## Re-run Commands

```bash
python -m nl2opt.eval.case_quality --difficulty medium
python -m nl2opt.eval.extractor_eval --prompt-version v3 --difficulty medium
python -m nl2opt.eval.failure_analysis --eval-dir outputs/deepseek_extractor_eval/medium --report docs/deepseek_medium_failure_analysis.md
```
