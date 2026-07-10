from __future__ import annotations

import math

import pytest
from pydantic import ValidationError


def valid_generic_data() -> dict:
    return {
        "problem_id": "generic_schema",
        "problem_type": "generic_lp_milp",
        "variables": [
            {"name": "x", "lb": 0, "ub": 4, "is_integer": False},
            {"name": "y", "lb": -1, "ub": None, "is_integer": True},
        ],
        "objective": {
            "sense": "maximize",
            "name": "value",
            "terms": [{"var": "x", "coef": 3}, {"var": "y", "coef": 2}],
        },
        "constraints": [
            {
                "terms": [{"var": "x", "coef": 1}, {"var": "y", "coef": 1}],
                "op": "<=",
                "rhs": 4,
            }
        ],
        "assumptions": [],
        "missing_fields": [],
    }


def test_generic_lp_schema_accepts_valid_linear_milp():
    from nl2opt.schemas import GenericLpSpec, ProblemType

    spec = GenericLpSpec.model_validate(valid_generic_data())

    assert spec.problem_type is ProblemType.GENERIC_LP_MILP
    assert spec.variables[1].ub is None
    assert spec.objective.terms[0].coef == 3


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda data: data["variables"].append({"name": "x", "lb": 0, "ub": 1, "is_integer": False}), "unique"),
        (lambda data: data["variables"].__setitem__(0, {"name": "x", "lb": math.inf, "ub": 1, "is_integer": False}), "finite"),
        (lambda data: data["variables"].__setitem__(0, {"name": "x", "lb": 2, "ub": 1, "is_integer": False}), "greater"),
        (lambda data: data["objective"].__setitem__("terms", []), "at least"),
        (lambda data: data["constraints"][0].__setitem__("terms", []), "at least"),
        (lambda data: data["objective"]["terms"].__setitem__(0, {"var": "missing", "coef": 1}), "unknown variable"),
        (lambda data: data["constraints"][0].__setitem__("rhs", math.nan), "finite"),
    ],
)
def test_generic_lp_schema_rejects_invalid_bounds_terms_and_coefficients(mutate, message):
    from nl2opt.schemas import GenericLpSpec

    data = valid_generic_data()
    mutate(data)

    with pytest.raises(ValidationError, match=message):
        GenericLpSpec.model_validate(data)


def test_unsupported_problem_spec_is_only_accepted_by_generic_extraction():
    from nl2opt.agents.extractor import extract_problem_spec, validate_spec_dict
    from nl2opt.agents.llm_client import MockLLMClient
    from nl2opt.schemas import ProblemType, UnsupportedProblemSpec

    refusal = {
        "problem_id": "nonlinear_request",
        "problem_type": "unsupported",
        "reason": "The objective contains a product of decision variables.",
    }
    result = extract_problem_spec(
        "Maximize x times y subject to a nonlinear constraint.",
        problem_type=ProblemType.GENERIC_LP_MILP,
        client=MockLLMClient(refusal),
        prompt_version="v4",
    )

    assert result.success is True
    assert isinstance(result.spec, UnsupportedProblemSpec)
    assert result.spec.reason == refusal["reason"]
    with pytest.raises(ValidationError):
        validate_spec_dict(ProblemType.PRODUCTION, refusal)
