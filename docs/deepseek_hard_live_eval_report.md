# DeepSeek Hard Extractor Live Eval Report

## Run Metadata

- Run time: 2026-06-30
- provider: deepseek
- model: deepseek-v4-flash
- mock: false
- prompt_version: v3
- difficulty: hard
- output_dir: `outputs/deepseek_extractor_eval/hard`
- API key handling: only key presence/source was checked; no key value, prefix, suffix, length, hash, request headers, or environment dump was written.

## Metrics

- total_cases: 4
- router_accuracy: 4/4
- spec_success: 4/4
- checker_success: 4/4
- objective_match: 4/4
- end_to_end_success: 4/4
- failure_breakdown: none

## Per-case Results

| case_id | category | objective_value | solver_status | checker | status |
| --- | --- | ---: | --- | --- | --- |
| extractor_production_hard_01 | production | 3300.0 | OPTIMAL | PASS | OK |
| extractor_assignment_hard_01 | assignment | 27.0 | OPTIMAL | PASS | OK |
| extractor_jobshop_hard_01 | jobshop | 13.0 | OPTIMAL | PASS | OK |
| extractor_vrp_hard_01 | vrp | 64.0 | FEASIBLE | PASS | OK |

## Failure Analysis

`docs/deepseek_hard_failure_analysis.md` was generated from the hard live artifacts.

- completed_cases: 4
- end_to_end_pass_rate: 1.0
- failure_breakdown: none

## Re-run Commands

```bash
python -m nl2opt.eval.case_quality --difficulty hard
python -m nl2opt.eval.extractor_eval --prompt-version v3 --difficulty hard
python -m nl2opt.eval.failure_analysis --eval-dir outputs/deepseek_extractor_eval/hard --report docs/deepseek_hard_failure_analysis.md
```
