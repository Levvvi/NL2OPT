from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from nl2opt.schemas import ProductionProblemSpec, SolverResult


SPEC_PATH = Path(__file__).resolve().parents[1] / "examples" / "specs" / "production_basic.json"


def load_spec() -> ProductionProblemSpec:
    return ProductionProblemSpec.model_validate_json(SPEC_PATH.read_text(encoding="utf-8"))


def valid_result() -> SolverResult:
    return SolverResult.model_validate(
        {
            "status": "OPTIMAL",
            "objective_value": 2200,
            "solution": {
                "quantities": {
                    "A": 40,
                    "B": 20,
                },
                "resource_usage": {
                    "labor": 100,
                    "material": 80,
                },
            },
            "runtime_sec": 0.01,
            "solver": "unit-test",
            "violations": [],
        }
    )


def test_checker_passes_valid_solution():
    from nl2opt.checkers.production_checker import check_production_solution

    report = check_production_solution(load_spec(), valid_result())

    assert report.passed is True
    assert report.violations == []
    assert report.computed_objective == 2200
    assert report.resource_usage == {"labor": 100, "material": 80}


def test_checker_rejects_resource_violation():
    from nl2opt.checkers.production_checker import check_production_solution

    data = valid_result().model_dump(mode="json")
    data["solution"]["quantities"]["A"] = 41
    result = SolverResult.model_validate(data)

    report = check_production_solution(load_spec(), result)

    assert report.passed is False
    assert any("capacity" in violation for violation in report.violations)


def test_checker_rejects_wrong_objective():
    from nl2opt.checkers.production_checker import check_production_solution

    data = valid_result().model_dump(mode="json")
    data["objective_value"] = 999
    result = SolverResult.model_validate(data)

    report = check_production_solution(load_spec(), result)

    assert report.passed is False
    assert any("objective" in violation for violation in report.violations)


def test_checker_rejects_unknown_product():
    from nl2opt.checkers.production_checker import check_production_solution

    data = valid_result().model_dump(mode="json")
    data["solution"]["quantities"]["C"] = 1
    result = SolverResult.model_validate(data)

    report = check_production_solution(load_spec(), result)

    assert report.passed is False
    assert any("unknown product" in violation for violation in report.violations)


@pytest.mark.parametrize("quantity", [0.5, True, "40", float("nan"), float("inf"), -float("inf")])
def test_checker_rejects_invalid_production_quantities(quantity):
    from nl2opt.checkers.production_checker import check_production_solution

    # Exercise the checker itself even if a caller bypasses SolverResult parsing.
    result = valid_result().model_copy(update={
        "solution": {"quantities": {"A": quantity, "B": 0}},
        "objective_value": 20,
    })

    report = check_production_solution(load_spec(), result)

    assert report.passed is False
    assert any("quantity for A" in violation for violation in report.violations)


@pytest.mark.parametrize("objective", [float("nan"), float("inf"), -float("inf")])
def test_checker_rejects_nonfinite_objective(objective):
    from nl2opt.checkers.production_checker import check_production_solution

    result = valid_result().model_copy(update={"objective_value": objective})

    report = check_production_solution(load_spec(), result)

    assert report.passed is False
    assert "objective_value must be a finite number" in report.violations


def test_checker_accepts_solver_rounding_within_integer_tolerance():
    from nl2opt.checkers.production_checker import check_production_solution

    result = valid_result().model_copy(update={
        "solution": {"quantities": {"A": 40 + 1e-9, "B": 20}},
    })

    assert check_production_solution(load_spec(), result).passed is True
