from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError


def valid_assignment_data() -> dict:
    return {
        "problem_id": "assignment_basic",
        "problem_type": "assignment",
        "objective": {
            "sense": "minimize",
            "name": "cost",
        },
        "employees": [
            {"name": "Alice", "capacity": 2},
            {"name": "Bob", "capacity": 2},
            {"name": "Chen", "capacity": 2},
        ],
        "tasks": [
            {"name": "T1"},
            {"name": "T2"},
            {"name": "T3"},
            {"name": "T4"},
        ],
        "costs": {
            "Alice": {"T1": 8, "T2": 6, "T3": 10, "T4": 9},
            "Bob": {"T1": 9, "T2": 7, "T3": 4, "T4": 8},
            "Chen": {"T1": 5, "T2": 8, "T3": 7, "T4": 6},
        },
        "assumptions": [
            "Every task must be assigned to exactly one employee.",
            "Each employee can take at most capacity tasks.",
        ],
        "missing_fields": [],
    }


def test_parse_valid_assignment_spec():
    from nl2opt.schemas import AssignmentProblemSpec, ProblemType

    spec = AssignmentProblemSpec.model_validate(valid_assignment_data())

    assert spec.problem_type is ProblemType.ASSIGNMENT
    assert [employee.name for employee in spec.employees] == ["Alice", "Bob", "Chen"]
    assert [task.name for task in spec.tasks] == ["T1", "T2", "T3", "T4"]


def test_reject_unknown_employee_in_costs():
    from nl2opt.schemas import AssignmentProblemSpec

    data = valid_assignment_data()
    data["costs"]["Dana"] = {"T1": 1}

    with pytest.raises(ValidationError):
        AssignmentProblemSpec.model_validate(data)


def test_reject_unknown_task_in_costs():
    from nl2opt.schemas import AssignmentProblemSpec

    data = valid_assignment_data()
    data["costs"]["Alice"]["T5"] = 1

    with pytest.raises(ValidationError):
        AssignmentProblemSpec.model_validate(data)


def test_reject_negative_cost():
    from nl2opt.schemas import AssignmentProblemSpec

    data = valid_assignment_data()
    data["costs"]["Alice"]["T1"] = -1

    with pytest.raises(ValidationError):
        AssignmentProblemSpec.model_validate(data)


def test_reject_duplicate_employee_name():
    from nl2opt.schemas import AssignmentProblemSpec

    data = valid_assignment_data()
    data["employees"].append({"name": "Alice", "capacity": 1})

    with pytest.raises(ValidationError):
        AssignmentProblemSpec.model_validate(data)


def test_reject_task_without_any_available_employee():
    from nl2opt.schemas import AssignmentProblemSpec

    data = copy.deepcopy(valid_assignment_data())
    for employee_costs in data["costs"].values():
        employee_costs.pop("T4")

    with pytest.raises(ValidationError):
        AssignmentProblemSpec.model_validate(data)
