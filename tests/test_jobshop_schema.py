from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError


def valid_jobshop_data() -> dict:
    return {
        "problem_id": "jobshop_basic",
        "problem_type": "jobshop",
        "objective": {
            "sense": "minimize",
            "name": "makespan",
        },
        "machines": [
            {"name": "M1"},
            {"name": "M2"},
        ],
        "jobs": [
            {
                "name": "J1",
                "operations": [
                    {"machine": "M1", "duration": 3},
                    {"machine": "M2", "duration": 2},
                ],
            },
            {
                "name": "J2",
                "operations": [
                    {"machine": "M2", "duration": 2},
                    {"machine": "M1", "duration": 4},
                ],
            },
        ],
        "assumptions": [
            "Operations in each job must run in list order.",
            "Each machine can process at most one operation at a time.",
        ],
        "missing_fields": [],
    }


def test_parse_valid_jobshop_spec():
    from nl2opt.schemas import JobshopProblemSpec, ProblemType

    spec = JobshopProblemSpec.model_validate(valid_jobshop_data())

    assert spec.problem_type is ProblemType.JOBSHOP
    assert [machine.name for machine in spec.machines] == ["M1", "M2"]
    assert [job.name for job in spec.jobs] == ["J1", "J2"]


def test_reject_unknown_machine_in_operation():
    from nl2opt.schemas import JobshopProblemSpec

    data = valid_jobshop_data()
    data["jobs"][0]["operations"][0]["machine"] = "M3"

    with pytest.raises(ValidationError):
        JobshopProblemSpec.model_validate(data)


def test_reject_duplicate_machine_name():
    from nl2opt.schemas import JobshopProblemSpec

    data = valid_jobshop_data()
    data["machines"].append({"name": "M1"})

    with pytest.raises(ValidationError):
        JobshopProblemSpec.model_validate(data)


def test_reject_duplicate_job_name():
    from nl2opt.schemas import JobshopProblemSpec

    data = valid_jobshop_data()
    data["jobs"].append(copy.deepcopy(data["jobs"][0]))

    with pytest.raises(ValidationError):
        JobshopProblemSpec.model_validate(data)


def test_reject_empty_operations():
    from nl2opt.schemas import JobshopProblemSpec

    data = valid_jobshop_data()
    data["jobs"][0]["operations"] = []

    with pytest.raises(ValidationError):
        JobshopProblemSpec.model_validate(data)


def test_reject_non_positive_duration():
    from nl2opt.schemas import JobshopProblemSpec

    data = valid_jobshop_data()
    data["jobs"][0]["operations"][0]["duration"] = 0

    with pytest.raises(ValidationError):
        JobshopProblemSpec.model_validate(data)


def test_reject_unsupported_objective():
    from nl2opt.schemas import JobshopProblemSpec

    data = valid_jobshop_data()
    data["objective"]["sense"] = "maximize"

    with pytest.raises(ValidationError):
        JobshopProblemSpec.model_validate(data)
