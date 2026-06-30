from __future__ import annotations


def test_build_extractor_prompt_v3_contains_strict_schema_rules():
    from nl2opt.agents.prompts import build_extractor_prompt
    from nl2opt.schemas import ProblemType

    system_prompt, user_prompt = build_extractor_prompt(
        "Assign tasks to workers with minimum cost.",
        ProblemType.ASSIGNMENT,
        {"type": "object"},
        prompt_version="v3",
    )

    combined = system_prompt + "\n" + user_prompt
    assert "Return exactly one JSON object" in combined
    assert "Do not add fields that are not in the JSON schema" in combined
    assert "costs must be an object of objects" in combined
    assert "employees" in combined
    assert "tasks" in combined


def test_build_extractor_prompt_v3_contains_jobshop_vrp_and_production_hints():
    from nl2opt.agents.prompts import build_extractor_prompt
    from nl2opt.schemas import ProblemType

    _, production_prompt = build_extractor_prompt(
        "Production planning.",
        ProblemType.PRODUCTION,
        {},
        prompt_version="v3",
    )
    _, jobshop_prompt = build_extractor_prompt(
        "Job shop.",
        ProblemType.JOBSHOP,
        {},
        prompt_version="v3",
    )
    _, vrp_prompt = build_extractor_prompt(
        "Vehicle routing.",
        ProblemType.VRP,
        {},
        prompt_version="v3",
    )

    assert "consumption must be nested by product then resource" in production_prompt
    assert "duration must be a positive integer" in jobshop_prompt
    assert "objective must be exactly" in vrp_prompt
    assert "distance_matrix must be a complete nested object" in vrp_prompt
