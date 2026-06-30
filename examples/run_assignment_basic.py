from __future__ import annotations

from pathlib import Path

from nl2opt.checkers.assignment_checker import check_assignment_solution
from nl2opt.runtime.runner import load_solver_result, run_python_code
from nl2opt.schemas import AssignmentProblemSpec
from nl2opt.solvers.render import render_assignment_code


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    spec_path = project_root / "examples" / "specs" / "assignment_basic.json"
    output_dir = project_root / "outputs" / "assignment_basic"

    spec = AssignmentProblemSpec.model_validate_json(spec_path.read_text(encoding="utf-8"))
    code = render_assignment_code(spec)
    run_result = run_python_code(code, output_dir)
    if run_result.timed_out:
        print("runner timed out")
        return 1
    if run_result.returncode != 0:
        print(run_result.stderr)
        return run_result.returncode or 1

    result = load_solver_result(run_result.solution_path)
    report = check_assignment_solution(spec, result)

    print(f"solver status: {result.status.value}")
    print(f"objective_value: {result.objective_value}")
    print(f"assignments: {result.solution.get('assignments', {})}")
    print(f"employee_loads: {report.details.get('employee_loads', {})}")
    print(f"checker passed: {report.passed}")
    print(f"violations: {report.violations}")

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
