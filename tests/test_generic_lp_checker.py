from __future__ import annotations


def feasible_generic_spec():
    from nl2opt.schemas import GenericLpSpec

    return GenericLpSpec.model_validate(
        {
            "problem_id": "generic_checker",
            "problem_type": "generic_lp_milp",
            "variables": [
                {"name": "x", "lb": 0, "ub": 3, "is_integer": True},
                {"name": "y", "lb": 0, "ub": None, "is_integer": False},
            ],
            "objective": {
                "sense": "maximize",
                "name": "value",
                "terms": [{"var": "x", "coef": 2}, {"var": "y", "coef": 1}],
            },
            "constraints": [
                {"terms": [{"var": "x", "coef": 1}, {"var": "y", "coef": 1}], "op": "<=", "rhs": 4}
            ],
            "assumptions": [],
            "missing_fields": [],
        }
    )


def infeasible_generic_spec():
    from nl2opt.schemas import GenericLpSpec

    return GenericLpSpec.model_validate(
        {
            "problem_id": "infeasible_generic",
            "problem_type": "generic_lp_milp",
            "variables": [{"name": "x", "lb": 0, "ub": 1, "is_integer": False}],
            "objective": {"sense": "maximize", "name": "value", "terms": [{"var": "x", "coef": 1}]},
            "constraints": [{"terms": [{"var": "x", "coef": 1}], "op": ">=", "rhs": 2}],
            "assumptions": [],
            "missing_fields": [],
        }
    )


def feasible_result():
    from nl2opt.schemas import SolverResult

    return SolverResult.model_validate(
        {
            "status": "OPTIMAL",
            "objective_value": 7,
            "solution": {"variables": {"x": 3, "y": 1}},
            "runtime_sec": 0.01,
            "solver": "unit-test",
            "violations": [],
        }
    )


def infeasible_result():
    from nl2opt.schemas import SolverResult

    return SolverResult.model_validate(
        {
            "status": "INFEASIBLE",
            "objective_value": None,
            "solution": {},
            "runtime_sec": 0.01,
            "solver": "unit-test",
            "violations": ["INFEASIBLE"],
        }
    )


def test_generic_checker_verifies_feasible_solution_and_objective():
    from nl2opt.checkers.generic_lp_checker import check_generic_solution

    report = check_generic_solution(feasible_generic_spec(), feasible_result())

    assert report.passed is True
    assert report.computed_objective == 7


def test_generic_checker_verifies_infeasible_by_independent_feasibility_model():
    from nl2opt.checkers.generic_lp_checker import check_generic_solution

    report = check_generic_solution(infeasible_generic_spec(), infeasible_result())

    assert report.passed is True
    assert report.details["infeasibility_verified"] is True


def test_generic_checker_bounds_infeasibility_verification_to_remaining_budget(monkeypatch):
    from ortools.linear_solver import pywraplp

    import nl2opt.checkers.generic_lp_checker as generic_lp_checker

    set_time_limits: list[int] = []

    class FeasibilitySolver:
        def SetTimeLimit(self, milliseconds: int) -> None:
            set_time_limits.append(milliseconds)

        def Solve(self) -> int:
            return pywraplp.Solver.INFEASIBLE

    monkeypatch.setattr(generic_lp_checker, "_create_feasibility_solver", lambda _spec: (FeasibilitySolver(), "GLOP"))
    monkeypatch.setattr(generic_lp_checker, "_add_model_constraints", lambda *_args: None)

    report = generic_lp_checker.check_generic_solution(
        infeasible_generic_spec(),
        infeasible_result(),
        timeout_sec=0.25,
    )

    assert report.passed is True
    assert set_time_limits == [250]


def test_generic_checker_fails_closed_when_no_infeasibility_budget_remains():
    from nl2opt.checkers.generic_lp_checker import check_generic_solution

    report = check_generic_solution(infeasible_generic_spec(), infeasible_result(), timeout_sec=0)

    assert report.passed is False
    assert report.details["infeasibility_verified"] is False
    assert "remaining" in report.violations[0]
