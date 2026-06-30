# DeepSeek Easy Case Diagnostics

## Context

This report was updated after P3-T14. The easy extractor cases were rewritten as complete UTF-8 Chinese prompts with the numeric data required by their gold specs. The checker, gold answers, solver templates, and OR-Tools pipeline were not relaxed.

## Case Quality Summary

- audit command: `python -m nl2opt.eval.case_quality --difficulty easy`
- total: 8
- passed: 8
- failed: 0

## Case Table

| case_id | category | prompt_quality | schema_status | missing_fields | main_failure | fix_applied |
| --- | --- | --- | --- | --- | --- | --- |
| extractor_production_01 | production | PASS | PASS | [] | none | Added product profits, labor/material capacities, full product-resource consumption matrix, integer quantity statement, and objective. |
| extractor_production_02 | production | PASS | PASS | [] | none | Added X/Y profits, labor/material capacities, full consumption matrix, integer quantity statement, and objective. |
| extractor_assignment_01 | assignment | PASS | PASS | [] | none | Added Alice/Bob/Chen capacities and full employee-task cost matrix. |
| extractor_assignment_02 | assignment | PASS | PASS | [] | none | Added E1/E2 capacities and full 2x2 cost matrix. |
| extractor_jobshop_01 | jobshop | PASS | PASS | [] | none | Added machine sequence and numeric duration for each J1/J2 operation. |
| extractor_jobshop_02 | jobshop | PASS | PASS | [] | none | Added machine sequence and numeric duration for each tiny jobshop operation. |
| extractor_vrp_01 | vrp | PASS | PASS | [] | none | Added vehicle capacities, customer demands, complete depot/customer distance matrix, and objective. |
| extractor_vrp_02 | vrp | PASS | PASS | [] | none | Added single vehicle capacity, customer demands, complete depot/customer distance matrix, and objective. |

## Required-field Rule

If extraction succeeds but `missing_fields` contains required schema inputs, the eval now records `missing_required_fields` and stops before code generation, solver execution, and checker. Required fields include:

- production: products, profit, resources, capacity, consumption, resource names.
- assignment: employees/workers, tasks, capacity, costs/cost matrix.
- jobshop: machines, jobs, operations, machine, duration.
- vrp: depot, vehicles, capacity, customers, demand, distance_matrix.

This rule prevents underspecified prompts from accidentally entering OR-Tools with placeholder values.

## Latest Live Result

The latest real DeepSeek v3 run passed all 8 easy cases end to end:

- spec_success: 8/8
- checker_success: 8/8
- objective_match: 8/8
- end_to_end_success: 8/8
- failure_breakdown: none

## Notes

The improvement came from aligning the eval inputs with the existing schema and gold specs, plus keeping prompt v3 and deterministic normalization from P3-T13. No checker constraints were relaxed, and no gold objective values were changed.
