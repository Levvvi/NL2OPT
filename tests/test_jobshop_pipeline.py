from __future__ import annotations

from pathlib import Path


SPEC_PATH = Path(__file__).resolve().parents[1] / "examples" / "specs" / "jobshop_basic.json"


def test_jobshop_basic_end_to_end(tmp_path):
    from nl2opt.checkers.jobshop_checker import check_jobshop_solution
    from nl2opt.runtime.runner import load_solver_result, run_python_code
    from nl2opt.schemas import JobshopProblemSpec
    from nl2opt.solvers.render import render_jobshop_code

    spec = JobshopProblemSpec.model_validate_json(SPEC_PATH.read_text(encoding="utf-8"))
    code = render_jobshop_code(spec)
    run_result = run_python_code(code, tmp_path)

    assert run_result.returncode == 0, run_result.stderr
    result = load_solver_result(run_result.solution_path)
    report = check_jobshop_solution(spec, result)

    assert report.passed is True
    assert result.objective_value == 7
    assert len(result.solution["operations"]) == 4
    assert result.solution["makespan"] == 7
