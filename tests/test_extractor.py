from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_SPEC_PATH = ROOT / "examples" / "specs" / "production_basic.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_parse_json_object_plain_json():
    from nl2opt.agents.extractor import parse_json_object

    assert parse_json_object('{"a": 1}') == {"a": 1}


def test_parse_json_object_json_code_fence():
    from nl2opt.agents.extractor import parse_json_object

    raw = """```json
{"a": 1}
```"""

    assert parse_json_object(raw) == {"a": 1}


def test_parse_json_object_invalid_json():
    from nl2opt.agents.extractor import parse_json_object

    with pytest.raises(ValueError):
        parse_json_object("{not valid json")


def test_validate_spec_dict_production():
    from nl2opt.agents.extractor import validate_spec_dict
    from nl2opt.schemas import ProblemType, ProductionProblemSpec

    spec = validate_spec_dict(ProblemType.PRODUCTION, load_json(PRODUCTION_SPEC_PATH))

    assert isinstance(spec, ProductionProblemSpec)


def test_validate_spec_dict_applies_normalizer_before_pydantic():
    from nl2opt.agents.extractor import validate_spec_dict
    from nl2opt.schemas import JobshopProblemSpec, ProblemType

    spec = validate_spec_dict(
        ProblemType.JOBSHOP,
        {
            "problem_id": "jobshop_aliases",
            "problem_type": "jobshop",
            "objective": {"sense": "minimize", "name": "completion_time"},
            "machines": [{"name": "M1"}],
            "jobs": [
                {
                    "name": "J1",
                    "operations": [{"machine_id": "M1", "processing_time": "2"}],
                }
            ],
            "assumptions": [],
            "missing_fields": [],
        },
    )

    assert isinstance(spec, JobshopProblemSpec)
    assert spec.objective.name == "makespan"
    assert spec.jobs[0].operations[0].machine == "M1"
    assert spec.jobs[0].operations[0].duration == 2


def test_extract_problem_spec_with_mock_client_success():
    from nl2opt.agents.extractor import extract_problem_spec
    from nl2opt.agents.llm_client import MockLLMClient
    from nl2opt.schemas import ProblemType

    result = extract_problem_spec(
        "某工厂生产 A 和 B 两种产品，问如何安排产量使利润最大？",
        problem_type=ProblemType.PRODUCTION,
        client=MockLLMClient(load_json(PRODUCTION_SPEC_PATH)),
    )

    assert result.success is True
    assert result.spec.problem_id == "production_basic"
    assert result.provider == "mock"
    assert result.model == "mock-extractor"
    assert result.validation_errors == []


def test_extract_problem_spec_uses_router_when_problem_type_missing():
    from nl2opt.agents.extractor import extract_problem_spec
    from nl2opt.agents.llm_client import MockLLMClient

    result = extract_problem_spec(
        "某工厂生产 A 和 B 两种产品，工时和原料有限，问如何安排产量使利润最大？",
        client=MockLLMClient(load_json(PRODUCTION_SPEC_PATH)),
    )

    assert result.success is True
    assert result.problem_type == "production"


def test_extract_problem_spec_rejects_unsupported_text():
    from nl2opt.agents.extractor import extract_problem_spec
    from nl2opt.agents.llm_client import MockLLMClient

    result = extract_problem_spec(
        "帮我写一首诗",
        client=MockLLMClient({}),
    )

    assert result.success is False
    assert result.problem_type == "unsupported"
    assert result.error


def test_extract_problem_spec_rejects_schema_error():
    from nl2opt.agents.extractor import extract_problem_spec
    from nl2opt.agents.llm_client import MockLLMClient
    from nl2opt.schemas import ProblemType

    result = extract_problem_spec(
        "某工厂生产产品，资源有限",
        problem_type=ProblemType.PRODUCTION,
        client=MockLLMClient({"problem_id": "bad", "problem_type": "production"}),
    )

    assert result.success is False
    assert result.validation_errors


def test_extractor_cli_case_id_runs():
    completed = subprocess.run(
        [sys.executable, "-m", "nl2opt.agents.extractor", "--case-id", "extractor_production_01"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["success"] is True
    assert payload["problem_type"] == "production"
    assert payload["problem_id"] == "production_basic"


def test_extractor_cli_mock_spec_runs():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.agents.extractor",
            "某工厂生产 A 和 B 两种产品，工时和原料有限，问如何安排产量使利润最大？",
            "--problem-type",
            "production",
            "--mock-spec",
            str(PRODUCTION_SPEC_PATH),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["success"] is True
    assert payload["problem_type"] == "production"
