from __future__ import annotations

import copy
import json
from pathlib import Path

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
