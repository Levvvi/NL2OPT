from __future__ import annotations

import json
from pathlib import Path


def continuous_generic_spec():
    from nl2opt.schemas import GenericLpSpec

    return GenericLpSpec.model_validate(
        {
            "problem_id": "continuous_generic",
            "problem_type": "generic_lp_milp",
            "variables": [
                {"name": "x", "lb": 0, "ub": None, "is_integer": False},
                {"name": "y", "lb": 0, "ub": None, "is_integer": False},
            ],
            "objective": {
                "sense": "maximize",
                "name": "value",
                "terms": [{"var": "x", "coef": 3}, {"var": "y", "coef": 2}],
            },
            "constraints": [
                {"terms": [{"var": "x", "coef": 1}, {"var": "y", "coef": 1}], "op": "<=", "rhs": 4},
                {"terms": [{"var": "x", "coef": 1}], "op": "<=", "rhs": 2},
                {"terms": [{"var": "y", "coef": 1}], "op": "<=", "rhs": 3},
            ],
            "assumptions": [],
            "missing_fields": [],
        }
    )


def test_generic_lp_pipeline_uses_glop_and_matches_objective(tmp_path):
    from nl2opt.pipeline import run_problem_spec

    result = run_problem_spec(continuous_generic_spec(), tmp_path, timeout_sec=5)

    assert result.solver_status == "OPTIMAL"
    assert result.checker_passed is True
    assert result.objective_value == 10.0
    solution = json.loads(Path(result.solution_path).read_text(encoding="utf-8"))
    assert solution["solver"] == "ortools.linear_solver:GLOP"
    assert solution["solution"]["variables"] == {"x": 2, "y": 2}


def test_generic_milp_pipeline_uses_scip(tmp_path):
    from nl2opt.pipeline import run_problem_spec
    from nl2opt.schemas import GenericLpSpec

    data = continuous_generic_spec().model_dump(mode="json")
    data["problem_id"] = "integer_generic"
    data["variables"] = [
        {"name": "x", "lb": 0, "ub": 2, "is_integer": True},
        {"name": "y", "lb": 0, "ub": 3, "is_integer": False},
    ]
    spec = GenericLpSpec.model_validate(data)

    result = run_problem_spec(spec, tmp_path, timeout_sec=5)

    assert result.solver_status == "OPTIMAL"
    assert result.checker_passed is True
    solution = json.loads(Path(result.solution_path).read_text(encoding="utf-8"))
    assert solution["solver"] == "ortools.linear_solver:SCIP"


def test_generic_lp_pipeline_reports_unbounded_status_without_checker_exception(tmp_path):
    from nl2opt.pipeline import run_problem_spec
    from nl2opt.schemas import GenericLpSpec

    spec = GenericLpSpec.model_validate(
        {
            "problem_id": "unbounded_generic",
            "problem_type": "generic_lp_milp",
            "variables": [{"name": "x", "lb": 0, "ub": None, "is_integer": False}],
            "objective": {
                "sense": "maximize",
                "name": "value",
                "terms": [{"var": "x", "coef": 1}],
            },
            "constraints": [],
            "assumptions": [],
            "missing_fields": [],
        }
    )

    result = run_problem_spec(spec, tmp_path, timeout_sec=5)

    assert result.solver_status == "UNBOUNDED"
    assert result.checker_passed is False
    assert result.error == "checker failed"
    assert result.violations == ["solver status is not feasible: UNBOUNDED"]
