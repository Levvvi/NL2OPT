from __future__ import annotations

from pathlib import Path

from nl2opt.checkers.jobshop_checker import check_jobshop_solution
from nl2opt.runtime.runner import load_solver_result, run_python_code
from nl2opt.schemas import JobshopProblemSpec
from nl2opt.solvers.render import render_jobshop_code


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    spec_path = project_root / "examples" / "specs" / "jobshop_basic.json"
    output_dir = project_root / "outputs" / "jobshop_basic"

    spec = JobshopProblemSpec.model_validate_json(spec_path.read_text(encoding="utf-8"))
    code = render_jobshop_code(spec)
    run_result = run_python_code(code, output_dir)
    if run_result.timed_out:
        print("runner timed out")
        return 1
    if run_result.returncode != 0:
        print(run_result.stderr)
        return run_result.returncode or 1

    result = load_solver_result(run_result.solution_path)
    report = check_jobshop_solution(spec, result)

    print(f"solver status: {result.status.value}")
    print(f"objective_value: {result.objective_value}")
    print(f"makespan: {result.solution.get('makespan')}")
    print(f"operations: {result.solution.get('operations', [])}")
    print(f"checker passed: {report.passed}")
    print(f"violations: {report.violations}")

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
