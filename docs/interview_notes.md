# Interview Notes

## 30-second Version

NL2OPT is a Chinese natural-language optimization modeling agent. It classifies a business problem, uses DeepSeek to extract a structured `ProblemSpec`, solves it with OR-Tools templates, and independently checks feasibility and objective consistency. The project covers production planning, task assignment, jobshop scheduling, and CVRP. In the final live eval with `deepseek-v4-flash`, `prompt_version=v3`, and `mock=false`, the self-built 20-case benchmark passes 20/20 end to end.

## 2-minute Version

Many business optimization problems are described in natural language, but solvers need structured data: entities, parameters, objectives, and constraints. NL2OPT bridges that gap for four common optimization families: production planning, task assignment, jobshop scheduling, and capacitated vehicle routing.

The core design is schema-first. DeepSeek is only responsible for extracting a strict JSON `ProblemSpec`, which is then validated by Pydantic. If required fields are missing or malformed, the case stops before solver execution.

I deliberately do not let the LLM freely write OR-Tools code. Instead, each problem family has a tested Jinja2 template that generates solver code from the validated schema. This keeps the modeling logic controlled and easier to debug.

After OR-Tools solves the model, an independent checker recomputes feasibility and objective value from the original spec and solver result. This is important because "the solver produced a JSON file" is not the same as "the solution is valid."

The project is evaluated with a 20-case Chinese benchmark: 8 easy, 8 medium, and 4 hard cases across all four problem types. In the final real DeepSeek live eval, using `deepseek-v4-flash` and `prompt_version=v3`, all 20 cases pass end to end. For an AI application or operations research role, the project shows both LLM integration discipline and optimization-modeling judgment.

## Resume Bullets

Version A, AI application focus:

> Built NL2OPT, a Chinese natural-language optimization modeling agent: used DeepSeek API to extract entities and constraints for production planning, assignment, jobshop scheduling, and vehicle routing; validated outputs with Pydantic schemas, solved with template-based OR-Tools code, and verified solutions with independent checkers. Created a 20-case Chinese benchmark and achieved 20/20 end-to-end success in a real `deepseek-v4-flash` live eval.

Version B, operations research focus:

> Implemented an end-to-end optimization modeling and solving workflow for Chinese business descriptions: represented production, assignment, scheduling, and routing problems as structured `ProblemSpec` objects, solved them with OR-Tools, and independently checked feasibility and objective consistency; achieved 100% end-to-end pass rate on a self-built 20-case benchmark.

## Common Interview Questions

### Why not let the LLM directly generate OR-Tools code?

Free-form solver code generation is difficult to control and debug. NL2OPT restricts the LLM to structured extraction only. The solver code comes from tested templates, so fields, constraints, objective functions, and execution boundaries are predictable.

### Does 20/20 mean the system can solve arbitrary optimization problems?

No. The 20/20 result is for a self-built benchmark covering four supported problem families. NL2OPT is not a general automatic optimization modeling platform and does not claim support for arbitrary open-ended problems.

### What does the checker do?

The checker independently verifies solver output instead of trusting `solution.json`. It recomputes resource usage, assignment coverage, machine conflicts, route distances, capacities, and objective values from the original spec.

### How does this relate to an operations research background?

The project turns optimization modeling concepts into an engineering pipeline: variables, objectives, constraints, feasibility checks, and evaluation are all made explicit. OR knowledge helps decide which information must be schema-controlled and which solver assumptions cannot be guessed by the model.

### What happens if a real business prompt is missing required fields?

The extractor can record missing information in `missing_fields`. If the missing field is required for the current problem type, NL2OPT stops before code generation and records the failure reason instead of guessing missing numbers.

### What would you improve next?

The next steps would be a repair loop for incomplete extraction, more problem families, stronger eval coverage, and safer execution isolation if the project were moved beyond local interview demos. For the current P3 scope, the project intentionally remains a small local MVP.
