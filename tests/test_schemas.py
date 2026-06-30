from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest


EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "examples" / "specs" / "production_basic.json"


def load_valid_production_data() -> dict:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_parse_valid_production_spec():
    from nl2opt.schemas import ProblemType, ProductionProblemSpec

    spec = ProductionProblemSpec.model_validate(load_valid_production_data())

    assert spec.problem_type is ProblemType.PRODUCTION
    assert spec.objective.name == "profit"
    assert [product.name for product in spec.products] == ["A", "B"]
    assert [resource.name for resource in spec.resources] == ["labor", "material"]


def test_reject_unknown_product_in_consumption():
    from pydantic import ValidationError

    from nl2opt.schemas import ProductionProblemSpec

    data = copy.deepcopy(load_valid_production_data())
    data["consumption"]["unknown_product"] = {"labor": 1, "material": 1}

    with pytest.raises(ValidationError):
        ProductionProblemSpec.model_validate(data)


def test_reject_unknown_resource_in_consumption():
    from pydantic import ValidationError

    from nl2opt.schemas import ProductionProblemSpec

    data = copy.deepcopy(load_valid_production_data())
    data["consumption"]["A"]["unknown_resource"] = 1

    with pytest.raises(ValidationError):
        ProductionProblemSpec.model_validate(data)


def test_parse_solver_result():
    from nl2opt.schemas import SolverResult, SolverStatus

    result = SolverResult.model_validate(
        {
            "status": "OPTIMAL",
            "objective_value": 180.0,
            "solution": {"A": 20, "B": 10},
            "runtime_sec": 0.05,
            "solver": "unit-test",
            "violations": [],
        }
    )

    assert result.status is SolverStatus.OPTIMAL
    assert result.objective_value == 180.0
