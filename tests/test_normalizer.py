from __future__ import annotations


def test_normalize_production_objective_synonyms():
    from nl2opt.agents.normalizer import normalize_spec_dict
    from nl2opt.schemas import ProblemType

    data = {
        "problem_id": "p",
        "problem_type": "production",
        "objective": {"sense": "最大化", "name": "利润"},
        "products": [],
        "resources": [],
        "consumption": {},
        "assumptions": [],
        "missing_fields": [],
    }

    normalized = normalize_spec_dict(ProblemType.PRODUCTION, data)

    assert normalized["objective"] == {"sense": "maximize", "name": "profit"}


def test_normalize_assignment_cost_matrix_alias():
    from nl2opt.agents.normalizer import normalize_spec_dict
    from nl2opt.schemas import ProblemType

    data = {
        "problem_id": "a",
        "problem_type": "assignment",
        "objective": {"sense": "minimize", "name": "total_cost"},
        "employees": [{"name": "E1", "capacity": 1}],
        "tasks": [{"name": "T1"}],
        "cost_matrix": {"E1": {"T1": "3"}},
        "assumptions": [],
        "missing_fields": [],
    }

    normalized = normalize_spec_dict(ProblemType.ASSIGNMENT, data)

    assert "cost_matrix" not in normalized
    assert normalized["costs"] == {"E1": {"T1": 3}}
    assert normalized["objective"] == {"sense": "minimize", "name": "cost"}


def test_normalize_jobshop_operation_aliases_and_integer_strings():
    from nl2opt.agents.normalizer import normalize_spec_dict
    from nl2opt.schemas import ProblemType

    data = {
        "problem_id": "j",
        "problem_type": "jobshop",
        "objective": {"sense": "minimize", "name": "completion_time"},
        "machines": [{"name": "M1"}],
        "jobs": [
            {
                "name": "J1",
                "operations": [
                    {"machine_id": "M1", "processing_time": "2"},
                ],
            }
        ],
        "assumptions": [],
        "missing_fields": [],
    }

    normalized = normalize_spec_dict(ProblemType.JOBSHOP, data)

    assert normalized["objective"] == {"sense": "minimize", "name": "makespan"}
    assert normalized["jobs"][0]["operations"][0] == {"machine": "M1", "duration": 2}


def test_normalize_vrp_objective_and_distance_alias():
    from nl2opt.agents.normalizer import normalize_spec_dict
    from nl2opt.schemas import ProblemType

    data = {
        "problem_id": "v",
        "problem_type": "vrp",
        "objective": {"sense": "minimize", "name": "total_distance"},
        "depot": "depot",
        "vehicles": [{"name": "V1", "capacity": "10"}],
        "customers": [{"name": "C1", "demand": "2"}],
        "distances": {"depot": {"depot": 0, "C1": "2"}, "C1": {"depot": "2", "C1": 0}},
        "assumptions": [],
        "missing_fields": [],
    }

    normalized = normalize_spec_dict(ProblemType.VRP, data)

    assert "distances" not in normalized
    assert normalized["objective"] == {"sense": "minimize", "name": "distance"}
    assert normalized["vehicles"][0]["capacity"] == 10
    assert normalized["customers"][0]["demand"] == 2
    assert normalized["distance_matrix"]["C1"]["depot"] == 2


def test_normalizer_does_not_guess_missing_costs():
    from nl2opt.agents.normalizer import normalize_spec_dict
    from nl2opt.schemas import ProblemType

    data = {
        "problem_id": "a",
        "problem_type": "assignment",
        "objective": {"sense": "minimize", "name": "cost"},
        "employees": [{"name": "E1", "capacity": 1}],
        "tasks": [{"name": "T1"}],
        "assumptions": [],
        "missing_fields": ["costs"],
    }

    normalized = normalize_spec_dict(ProblemType.ASSIGNMENT, data)

    assert "costs" not in normalized
