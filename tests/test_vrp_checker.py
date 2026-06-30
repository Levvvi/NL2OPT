from __future__ import annotations

from pathlib import Path


SPEC_PATH = Path(__file__).resolve().parents[1] / "examples" / "specs" / "vrp_basic.json"


def load_spec():
    from nl2opt.schemas import VrpProblemSpec

    return VrpProblemSpec.model_validate_json(SPEC_PATH.read_text(encoding="utf-8"))


def valid_result():
    from nl2opt.schemas import SolverResult

    return SolverResult.model_validate(
        {
            "status": "FEASIBLE",
            "objective_value": 44,
            "solution": {
                "routes": [
                    {
                        "vehicle": "V1",
                        "stops": ["depot", "C1", "C2", "C3", "depot"],
                        "load": 15,
                        "distance": 16,
                    },
                    {
                        "vehicle": "V2",
                        "stops": ["depot", "C4", "C5", "depot"],
                        "load": 10,
                        "distance": 28,
                    },
                ],
                "total_distance": 44,
                "total_load": 25,
                "dropped_customers": [],
            },
            "runtime_sec": 0.01,
            "solver": "unit-test",
            "violations": [],
        }
    )


def test_vrp_checker_passes_valid_solution():
    from nl2opt.checkers.vrp_checker import check_vrp_solution

    report = check_vrp_solution(load_spec(), valid_result())

    assert report.passed is True
    assert report.violations == []
    assert report.computed_objective == 44
    assert report.details["total_load"] == 25
    assert report.details["visited_customers"] == ["C1", "C2", "C3", "C4", "C5"]


def test_vrp_checker_rejects_missing_customer():
    from nl2opt.checkers.vrp_checker import check_vrp_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["routes"][0]["stops"].remove("C3")
    result = SolverResult.model_validate(data)

    report = check_vrp_solution(load_spec(), result)

    assert report.passed is False
    assert any("missing customer" in violation for violation in report.violations)


def test_vrp_checker_rejects_duplicate_customer():
    from nl2opt.checkers.vrp_checker import check_vrp_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["routes"][1]["stops"].insert(1, "C1")
    result = SolverResult.model_validate(data)

    report = check_vrp_solution(load_spec(), result)

    assert report.passed is False
    assert any("duplicate customer" in violation for violation in report.violations)


def test_vrp_checker_rejects_unknown_stop():
    from nl2opt.checkers.vrp_checker import check_vrp_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["routes"][0]["stops"].insert(1, "C9")
    result = SolverResult.model_validate(data)

    report = check_vrp_solution(load_spec(), result)

    assert report.passed is False
    assert any("unknown stop" in violation for violation in report.violations)


def test_vrp_checker_rejects_route_not_starting_at_depot():
    from nl2opt.checkers.vrp_checker import check_vrp_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["routes"][0]["stops"][0] = "C1"
    result = SolverResult.model_validate(data)

    report = check_vrp_solution(load_spec(), result)

    assert report.passed is False
    assert any("start at depot" in violation for violation in report.violations)


def test_vrp_checker_rejects_route_not_ending_at_depot():
    from nl2opt.checkers.vrp_checker import check_vrp_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["routes"][0]["stops"][-1] = "C3"
    result = SolverResult.model_validate(data)

    report = check_vrp_solution(load_spec(), result)

    assert report.passed is False
    assert any("end at depot" in violation for violation in report.violations)


def test_vrp_checker_rejects_capacity_violation():
    from nl2opt.checkers.vrp_checker import check_vrp_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["routes"][0]["stops"] = ["depot", "C1", "C2", "C3", "C4", "depot"]
    data["solution"]["routes"][1]["stops"] = ["depot", "C5", "depot"]
    result = SolverResult.model_validate(data)

    report = check_vrp_solution(load_spec(), result)

    assert report.passed is False
    assert any("capacity" in violation for violation in report.violations)


def test_vrp_checker_rejects_wrong_route_distance():
    from nl2opt.checkers.vrp_checker import check_vrp_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["routes"][0]["distance"] = 999
    result = SolverResult.model_validate(data)

    report = check_vrp_solution(load_spec(), result)

    assert report.passed is False
    assert any("route distance" in violation for violation in report.violations)


def test_vrp_checker_rejects_wrong_objective():
    from nl2opt.checkers.vrp_checker import check_vrp_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["objective_value"] = 999
    result = SolverResult.model_validate(data)

    report = check_vrp_solution(load_spec(), result)

    assert report.passed is False
    assert any("objective" in violation for violation in report.violations)
