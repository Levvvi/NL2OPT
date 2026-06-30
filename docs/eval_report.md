# Final Evaluation Report

## Scope

This report summarizes the final NL2OPT 20-case live evaluation. The run uses real DeepSeek API responses, not mock outputs.

## Run Metadata

- Evaluation date: 2026-06-30
- Provider: `deepseek`
- Model: `deepseek-v4-flash`
- Prompt version: `v3`
- Mock: `false`
- Artifacts: `outputs/deepseek_extractor_eval/all/`
- Summary: `outputs/deepseek_extractor_eval/all/summary.json`

## Case Distribution

| difficulty | total | production | assignment | jobshop | vrp |
| --- | ---: | ---: | ---: | ---: | ---: |
| easy | 8 | 2 | 2 | 2 | 2 |
| medium | 8 | 2 | 2 | 2 | 2 |
| hard | 4 | 1 | 1 | 1 | 1 |
| all | 20 | 5 | 5 | 5 | 5 |

## Final 20 Live Eval

| difficulty | total | router_accuracy | spec_success | checker_success | objective_match | end_to_end_success | failure_breakdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| easy | 8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | `{}` |
| medium | 8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | `{}` |
| hard | 4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | `{}` |
| all | 20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | `{}` |

## Metric Definitions

- `router_accuracy`: Router predicted the expected problem type.
- `spec_success`: Extractor output parsed as JSON and passed the Pydantic schema.
- `checker_success`: Solver output passed the independent checker.
- `objective_match`: Solver objective matched the expected objective value for the case.
- `end_to_end_success`: Router, extractor, solver, checker, and objective matching all passed.

## Failure Breakdown

The final 20-case live eval has no recorded failures:

```json
{}
```

Detailed failure analysis is available in [deepseek_final_20_failure_analysis.md](deepseek_final_20_failure_analysis.md).

## Interpretation

The 20/20 result means the current system works on the self-built 20-case benchmark covering production, assignment, jobshop, and VRP/CVRP. It does not mean NL2OPT can solve arbitrary open-ended optimization problems. The current scope is four small problem families with schemas, templates, and checkers built specifically for those families.
