from __future__ import annotations

import json
from pathlib import Path

import nl2opt.pipeline as pipeline_module


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


def infeasible_generic_spec():
    from nl2opt.schemas import GenericLpSpec

    return GenericLpSpec.model_validate(
        {
            "problem_id": "infeasible_generic_pipeline",
            "problem_type": "generic_lp_milp",
            "variables": [{"name": "x", "lb": 0, "ub": 1, "is_integer": False}],
            "objective": {"sense": "maximize", "name": "value", "terms": [{"var": "x", "coef": 1}]},
            "constraints": [{"terms": [{"var": "x", "coef": 1}], "op": ">=", "rhs": 2}],
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


def test_generic_lp_pipeline_fails_closed_when_solver_exhausts_checker_budget(tmp_path, monkeypatch):
    from nl2opt.runtime.runner import RunResult

    output_dir = tmp_path / "pipeline"
    solution_path = output_dir / "solution.json"
    code_path = output_dir / "generated_model.py"
    output_dir.mkdir()
    solution_path.write_text(
        json.dumps(
            {
                "status": "INFEASIBLE",
                "objective_value": None,
                "solution": {},
                "runtime_sec": 0.01,
                "solver": "unit-test",
                "violations": ["INFEASIBLE"],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline_module, "render_code_for_spec", lambda _spec: "print('generated')")
    monkeypatch.setattr(
        pipeline_module,
        "run_python_code",
        lambda *_args, **_kwargs: RunResult(0, "", "", False, code_path, solution_path, 1.0),
    )
    ticks = iter((10.0, 11.0))
    monkeypatch.setattr(
        pipeline_module,
        "time",
        type("Clock", (), {"monotonic": staticmethod(lambda: next(ticks))})(),
        raising=False,
    )

    result = pipeline_module.run_problem_spec(infeasible_generic_spec(), output_dir, timeout_sec=1)

    assert result.checker_passed is False
    assert result.error == "checker failed"
    assert "remaining" in result.violations[0]
