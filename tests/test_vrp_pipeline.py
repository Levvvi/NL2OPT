from __future__ import annotations

from pathlib import Path


SPEC_PATH = Path(__file__).resolve().parents[1] / "examples" / "specs" / "vrp_basic.json"


def test_vrp_basic_end_to_end(tmp_path):
    from nl2opt.checkers.vrp_checker import check_vrp_solution
    from nl2opt.runtime.runner import load_solver_result, run_python_code
    from nl2opt.schemas import VrpProblemSpec
    from nl2opt.solvers.render import render_vrp_code

    spec = VrpProblemSpec.model_validate_json(SPEC_PATH.read_text(encoding="utf-8"))
    code = render_vrp_code(spec)
    run_result = run_python_code(code, tmp_path, timeout_sec=10)

    assert run_result.returncode == 0, run_result.stderr
    result = load_solver_result(run_result.solution_path)
    report = check_vrp_solution(spec, result)
    visited_customers = [
        stop
        for route in result.solution["routes"]
        for stop in route["stops"]
        if stop != spec.depot
    ]

    assert report.passed is True
    assert result.objective_value == 44
    assert sorted(visited_customers) == ["C1", "C2", "C3", "C4", "C5"]
    assert len(visited_customers) == 5
