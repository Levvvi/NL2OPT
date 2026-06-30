from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError


def valid_vrp_data() -> dict:
    return {
        "problem_id": "vrp_basic",
        "problem_type": "vrp",
        "objective": {
            "sense": "minimize",
            "name": "distance",
        },
        "depot": "depot",
        "vehicles": [
            {"name": "V1", "capacity": 15},
            {"name": "V2", "capacity": 15},
        ],
        "customers": [
            {"name": "C1", "demand": 4},
            {"name": "C2", "demand": 6},
            {"name": "C3", "demand": 5},
            {"name": "C4", "demand": 7},
            {"name": "C5", "demand": 3},
        ],
        "distance_matrix": {
            "depot": {"depot": 0, "C1": 4, "C2": 6, "C3": 8, "C4": 12, "C5": 14},
            "C1": {"depot": 4, "C1": 0, "C2": 2, "C3": 4, "C4": 15, "C5": 17},
            "C2": {"depot": 6, "C1": 2, "C2": 0, "C3": 2, "C4": 16, "C5": 18},
            "C3": {"depot": 8, "C1": 4, "C2": 2, "C3": 0, "C4": 14, "C5": 16},
            "C4": {"depot": 12, "C1": 15, "C2": 16, "C3": 14, "C4": 0, "C5": 2},
            "C5": {"depot": 14, "C1": 17, "C2": 18, "C3": 16, "C4": 2, "C5": 0},
        },
        "assumptions": [
            "All vehicles start and end at the depot.",
            "Every customer must be visited exactly once.",
        ],
        "missing_fields": [],
    }


def test_parse_valid_vrp_spec():
    from nl2opt.schemas import ProblemType, VrpProblemSpec

    spec = VrpProblemSpec.model_validate(valid_vrp_data())

    assert spec.problem_type is ProblemType.VRP
    assert spec.depot == "depot"
    assert [vehicle.name for vehicle in spec.vehicles] == ["V1", "V2"]
    assert [customer.name for customer in spec.customers] == ["C1", "C2", "C3", "C4", "C5"]


def test_reject_duplicate_customer_name():
    from nl2opt.schemas import VrpProblemSpec

    data = valid_vrp_data()
    data["customers"].append({"name": "C1", "demand": 1})

    with pytest.raises(ValidationError):
        VrpProblemSpec.model_validate(data)


def test_reject_non_positive_vehicle_capacity():
    from nl2opt.schemas import VrpProblemSpec

    data = valid_vrp_data()
    data["vehicles"][0]["capacity"] = 0

    with pytest.raises(ValidationError):
        VrpProblemSpec.model_validate(data)


def test_reject_negative_customer_demand():
    from nl2opt.schemas import VrpProblemSpec

    data = valid_vrp_data()
    data["customers"][0]["demand"] = -1

    with pytest.raises(ValidationError):
        VrpProblemSpec.model_validate(data)


def test_reject_total_demand_exceeds_total_capacity():
    from nl2opt.schemas import VrpProblemSpec

    data = valid_vrp_data()
    data["vehicles"][0]["capacity"] = 10
    data["vehicles"][1]["capacity"] = 10

    with pytest.raises(ValidationError):
        VrpProblemSpec.model_validate(data)


def test_reject_missing_distance_matrix_row():
    from nl2opt.schemas import VrpProblemSpec

    data = copy.deepcopy(valid_vrp_data())
    data["distance_matrix"].pop("C5")

    with pytest.raises(ValidationError):
        VrpProblemSpec.model_validate(data)


def test_reject_missing_distance_matrix_column():
    from nl2opt.schemas import VrpProblemSpec

    data = copy.deepcopy(valid_vrp_data())
    data["distance_matrix"]["C1"].pop("C5")

    with pytest.raises(ValidationError):
        VrpProblemSpec.model_validate(data)


def test_reject_negative_distance():
    from nl2opt.schemas import VrpProblemSpec

    data = valid_vrp_data()
    data["distance_matrix"]["C1"]["C2"] = -1

    with pytest.raises(ValidationError):
        VrpProblemSpec.model_validate(data)


def test_reject_unsupported_objective():
    from nl2opt.schemas import VrpProblemSpec

    data = valid_vrp_data()
    data["objective"]["sense"] = "maximize"

    with pytest.raises(ValidationError):
        VrpProblemSpec.model_validate(data)
