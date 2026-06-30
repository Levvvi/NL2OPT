from __future__ import annotations

from pathlib import Path


SPEC_PATH = Path(__file__).resolve().parents[1] / "examples" / "specs" / "jobshop_basic.json"


def load_spec():
    from nl2opt.schemas import JobshopProblemSpec

    return JobshopProblemSpec.model_validate_json(SPEC_PATH.read_text(encoding="utf-8"))


def valid_result():
    from nl2opt.schemas import SolverResult

    return SolverResult.model_validate(
        {
            "status": "OPTIMAL",
            "objective_value": 7,
            "solution": {
                "makespan": 7,
                "operations": [
                    {
                        "job": "J1",
                        "op_index": 0,
                        "machine": "M1",
                        "start": 0,
                        "end": 3,
                        "duration": 3,
                    },
                    {
                        "job": "J1",
                        "op_index": 1,
                        "machine": "M2",
                        "start": 3,
                        "end": 5,
                        "duration": 2,
                    },
                    {
                        "job": "J2",
                        "op_index": 0,
                        "machine": "M2",
                        "start": 0,
                        "end": 2,
                        "duration": 2,
                    },
                    {
                        "job": "J2",
                        "op_index": 1,
                        "machine": "M1",
                        "start": 3,
                        "end": 7,
                        "duration": 4,
                    },
                ],
                "machine_schedules": {
                    "M1": [
                        {"job": "J1", "op_index": 0, "start": 0, "end": 3, "duration": 3},
                        {"job": "J2", "op_index": 1, "start": 3, "end": 7, "duration": 4},
                    ],
                    "M2": [
                        {"job": "J2", "op_index": 0, "start": 0, "end": 2, "duration": 2},
                        {"job": "J1", "op_index": 1, "start": 3, "end": 5, "duration": 2},
                    ],
                },
            },
            "runtime_sec": 0.01,
            "solver": "unit-test",
            "violations": [],
        }
    )


def test_jobshop_checker_passes_valid_solution():
    from nl2opt.checkers.jobshop_checker import check_jobshop_solution

    report = check_jobshop_solution(load_spec(), valid_result())

    assert report.passed is True
    assert report.violations == []
    assert report.computed_objective == 7
    assert report.details["makespan"] == 7


def test_jobshop_checker_rejects_missing_operation():
    from nl2opt.checkers.jobshop_checker import check_jobshop_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["operations"].pop()
    result = SolverResult.model_validate(data)

    report = check_jobshop_solution(load_spec(), result)

    assert report.passed is False
    assert any("missing operation" in violation for violation in report.violations)


def test_jobshop_checker_rejects_duplicate_operation():
    from nl2opt.checkers.jobshop_checker import check_jobshop_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["operations"].append(data["solution"]["operations"][0])
    result = SolverResult.model_validate(data)

    report = check_jobshop_solution(load_spec(), result)

    assert report.passed is False
    assert any("duplicate operation" in violation for violation in report.violations)


def test_jobshop_checker_rejects_precedence_violation():
    from nl2opt.checkers.jobshop_checker import check_jobshop_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["operations"][1]["start"] = 2
    data["solution"]["operations"][1]["end"] = 4
    result = SolverResult.model_validate(data)

    report = check_jobshop_solution(load_spec(), result)

    assert report.passed is False
    assert any("precedence" in violation for violation in report.violations)


def test_jobshop_checker_rejects_machine_overlap():
    from nl2opt.checkers.jobshop_checker import check_jobshop_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["operations"][3]["start"] = 2
    data["solution"]["operations"][3]["end"] = 6
    result = SolverResult.model_validate(data)

    report = check_jobshop_solution(load_spec(), result)

    assert report.passed is False
    assert any("overlap" in violation for violation in report.violations)


def test_jobshop_checker_rejects_wrong_duration():
    from nl2opt.checkers.jobshop_checker import check_jobshop_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["solution"]["operations"][0]["end"] = 4
    result = SolverResult.model_validate(data)

    report = check_jobshop_solution(load_spec(), result)

    assert report.passed is False
    assert any("duration" in violation for violation in report.violations)


def test_jobshop_checker_rejects_wrong_objective():
    from nl2opt.checkers.jobshop_checker import check_jobshop_solution
    from nl2opt.schemas import SolverResult

    data = valid_result().model_dump(mode="json")
    data["objective_value"] = 99
    result = SolverResult.model_validate(data)

    report = check_jobshop_solution(load_spec(), result)

    assert report.passed is False
    assert any("objective" in violation for violation in report.violations)
