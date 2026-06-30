from __future__ import annotations

from pathlib import Path


SPEC_PATH = Path(__file__).resolve().parents[1] / "examples" / "specs" / "assignment_basic.json"


def test_assignment_basic_end_to_end(tmp_path):
    from nl2opt.checkers.assignment_checker import check_assignment_solution
    from nl2opt.runtime.runner import load_solver_result, run_python_code
    from nl2opt.schemas import AssignmentProblemSpec
    from nl2opt.solvers.render import render_assignment_code

    spec = AssignmentProblemSpec.model_validate_json(SPEC_PATH.read_text(encoding="utf-8"))
    code = render_assignment_code(spec)
    run_result = run_python_code(code, tmp_path)

    assert run_result.returncode == 0, run_result.stderr
    result = load_solver_result(run_result.solution_path)
    report = check_assignment_solution(spec, result)

    assert report.passed is True
    assert result.objective_value == 21
    assert result.solution["assignments"] == {
        "T1": "Chen",
        "T2": "Alice",
        "T3": "Bob",
        "T4": "Chen",
    }
    assert result.solution["employee_loads"] == {"Alice": 1, "Bob": 1, "Chen": 2}
