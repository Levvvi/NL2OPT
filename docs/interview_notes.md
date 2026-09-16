# Interview Notes

## 30-second Version

NL2OPT is a controlled Chinese natural-language optimization modeling workflow. It classifies a business problem, uses DeepSeek to extract a structured `ProblemSpec`, solves it with OR-Tools templates, and independently checks feasibility and objective consistency. The project covers production planning, task assignment, jobshop scheduling, and CVRP. In the historical 2026-06-30 live eval with `deepseek-v4-flash`, `prompt_version=v3`, and `mock=false`, the self-built 20-case benchmark passes 20/20 end to end.

## Public Benchmark Status

NL4Opt/IndustryOR evaluation is a separate, pinned bilingual benchmark path.
The audited retry-off run passed 1,098/2,070 attempts at both 1e-6 and 1e-4
(53.0%); all attempts remain in the denominator, and its 105 sampled translation
decisions are terminal (93 approved, 12 rejected). An independent retry-on
rerun passed 1,083/2,070 (52.3%), recorded 412 checker retries, and has 95
approved plus 10 rejected audits. The retry-on rate is 0.7 percentage points
lower, but the runs are not a paired causal experiment, so this does not show
that checker retry improved or reduced accuracy. Tables and limitations are in
`reports/bench_report.md`, with sanitized evidence in `reports/artifacts/`.
This public benchmark remains separate from the self-built 20-case result above.

## 2-minute Version

Many business optimization problems are described in natural language, but solvers need structured data: entities, parameters, objectives, and constraints. NL2OPT bridges that gap for four common optimization families: production planning, task assignment, jobshop scheduling, and capacitated vehicle routing.

The core design is schema-first. DeepSeek is only responsible for extracting a strict JSON `ProblemSpec`, which is then validated by Pydantic. If required fields are missing or malformed, the case stops before solver execution.

I deliberately do not let the LLM freely write OR-Tools code. Instead, each problem family has a tested Jinja2 template that generates solver code from the validated schema. This keeps the modeling logic controlled and easier to debug.

After OR-Tools solves the model, an independent checker recomputes feasibility and objective value from the original spec and solver result. This is important because "the solver produced a JSON file" is not the same as "the solution is valid."

The project is evaluated with a 20-case Chinese benchmark: 8 easy, 8 medium, and 4 hard cases across all four problem types. In the historical 2026-06-30 real DeepSeek live eval, using `deepseek-v4-flash` and `prompt_version=v3`, all 20 cases pass end to end. For an AI application or operations research role, the project shows both LLM integration discipline and optimization-modeling judgment.

## Resume Bullets

Version A, AI application focus:

> Built NL2OPT, a controlled Chinese natural-language optimization modeling workflow: used DeepSeek API to extract entities and constraints for production planning, assignment, jobshop scheduling, and vehicle routing; validated outputs with Pydantic schemas, solved with template-based OR-Tools code, and verified solutions with independent checkers. Created a 20-case Chinese benchmark and achieved 20/20 end-to-end success in a real `deepseek-v4-flash` live eval.

Version B, operations research focus:

> Implemented an end-to-end optimization modeling and solving workflow for Chinese business descriptions: represented production, assignment, scheduling, and routing problems as structured `ProblemSpec` objects, solved them with OR-Tools, and independently checked feasibility and objective consistency; recorded 20/20 end-to-end passes on the self-built 20-case benchmark in the 2026-06-30 live run.

## Common Interview Questions

### Why not let the LLM directly generate OR-Tools code?

Free-form solver code generation is difficult to control and debug. NL2OPT restricts the LLM to structured extraction only. The solver code comes from tested templates, so fields, constraints, objective functions, and execution boundaries are predictable.

### Does 20/20 mean the system can solve arbitrary optimization problems?

No. The 20/20 result is for a self-built benchmark covering four supported problem families. NL2OPT is not a general automatic optimization modeling platform and does not claim support for arbitrary open-ended problems.

### What does the checker do?

The checker recomputes resource usage, assignment coverage, machine conflicts, route distances, capacities, and objective values from the extracted spec. It can reject a wrong candidate independently of the solver, but cannot prove that the spec preserved every original language requirement or independently certify global optimality.

### How does this relate to an operations research background?

The project turns optimization modeling concepts into an engineering pipeline: variables, objectives, constraints, feasibility checks, and evaluation are all made explicit. OR knowledge helps decide which information must be schema-controlled and which solver assumptions cannot be guessed by the model.

### What happens if a real business prompt is missing required fields?

The extractor can record missing information in `missing_fields`. If the missing field is required for the current problem type, NL2OPT stops before code generation and records the failure reason instead of guessing missing numbers.

### What would you improve next?

The immediate focus is reproducible evidence, checks at explicit boundaries, and a bounded demonstration service. I would expand problem families or add repair loops only after failure analysis establishes their value. The independent retry-on public run did not show improved accuracy. Current release validation is dated and versioned in `docs/nl2opt_audit.md`.
