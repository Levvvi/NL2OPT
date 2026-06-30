from __future__ import annotations

from pathlib import Path


SPEC_PATH = Path(__file__).resolve().parents[1] / "examples" / "specs" / "assignment_basic.json"


def load_spec():
    from nl2opt.schemas import AssignmentProblemSpec

    return AssignmentProblemSpec.model_validate_json(SPEC_PATH.read_text(encoding="utf-8"))


def valid_result():
    from nl2opt.schemas import SolverResult

    return SolverResult.model_validate(
        {
            "status": "OPTIMAL",
            "objective_value": 21,
            "solution": {
                "assignments": {
                    "T1": "Chen",
                    "T2": "Alice",
                    "T3": "Bob",
                    "T4": "Chen",
                },
                "employee_loads": {
                    "Alice": 1,
                    "Bob": 1,
                    "Chen": 2,
                },
                "total_cost": 21,
            },
            "runtime_sec": 0.01,
            "solver": "unit-test",
            "violations": [],
        }
    )


def test_assignment_checker_passes_valid_solution():
    from nl2opt.checkers.assignment_checker import check_assignment_solution

    report = check_assignment_solution(load_spec(), valid_result())

    assert report.passed is True
    assert report.violations == []
    assert report.computed_objective == 21
    assert report.details["employee_loads"] == {"Alice": 1, "Bob": 1, "Chen": 2}


def test_assignment_checker_rejects_missing_task():
    from nl2opt.checkers.assignment_checker import check_assignment_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["assignments"].pop("T4")
    result = SolverResult.model_validate(data)

    report = check_assignment_solution(load_spec(), result)

    assert report.passed is False
    assert any("missing task" in violation for violation in report.violations)


def test_assignment_checker_rejects_unknown_employee():
    from nl2opt.checkers.assignment_checker import check_assignment_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["assignments"]["T1"] = "Dana"
    result = SolverResult.model_validate(data)

    report = check_assignment_solution(load_spec(), result)

    assert report.passed is False
    assert any("unknown employee" in violation for violation in report.violations)


def test_assignment_checker_rejects_capacity_violation():
    from nl2opt.checkers.assignment_checker import check_assignment_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["assignments"] = {
        "T1": "Alice",
        "T2": "Alice",
        "T3": "Alice",
        "T4": "Chen",
    }
    result = SolverResult.model_validate(data)

    report = check_assignment_solution(load_spec(), result)

    assert report.passed is False
    assert any("capacity" in violation for violation in report.violations)


def test_assignment_checker_rejects_wrong_objective():
    from nl2opt.checkers.assignment_checker import check_assignment_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["objective_value"] = 99
    result = SolverResult.model_validate(data)

    report = check_assignment_solution(load_spec(), result)

    assert report.passed is False
    assert any("objective" in violation for violation in report.violations)


def test_assignment_checker_rejects_ineligible_employee_task_pair():
    from nl2opt.checkers.assignment_checker import check_assignment_solution
    from nl2opt.schemas import AssignmentProblemSpec, SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["assignments"]["T3"] = "Alice"
    result = SolverResult.model_validate(data)
    spec_data = load_spec().model_dump(mode="json")
    spec_data["costs"]["Alice"].pop("T3")
    spec = AssignmentProblemSpec.model_validate(spec_data)

    report = check_assignment_solution(spec, result)

    assert report.passed is False
    assert any("ineligible" in violation for violation in report.violations)
