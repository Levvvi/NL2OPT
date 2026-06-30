from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "src" / "nl2opt" / "eval" / "extractor_cases_easy.jsonl"
PRODUCTION_SPEC_PATH = ROOT / "examples" / "specs" / "production_basic.json"


def test_mock_extractor_eval_records_prompt_version(tmp_path):
    from nl2opt.eval.extractor_eval import evaluate_mock_extractor_cases

    metrics = evaluate_mock_extractor_cases(
        CASES_PATH,
        tmp_path / "mock_eval",
        prompt_version="v2",
    )

    assert metrics["prompt_version"] == "v2"
    assert metrics["provider"] == "mock"
    assert metrics["mock"] is True
    summary = json.loads((tmp_path / "mock_eval" / "summary.json").read_text(encoding="utf-8"))
    assert summary["prompt_version"] == "v2"
    assert summary["mock"] is True


def test_extractor_result_records_prompt_version():
    from nl2opt.agents.extractor import extract_problem_spec
    from nl2opt.agents.llm_client import MockLLMClient
    from nl2opt.schemas import ProblemType

    spec = json.loads(PRODUCTION_SPEC_PATH.read_text(encoding="utf-8"))
    result = extract_problem_spec(
        "某工厂生产 A 和 B 两种产品，问如何安排产量使利润最大？",
        problem_type=ProblemType.PRODUCTION,
        client=MockLLMClient(spec),
        prompt_version="v2",
    )

    assert result.success is True
    assert result.prompt_version == "v2"


def test_extractor_cli_prompt_version_mock_runs():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.agents.extractor",
            "--case-id",
            "extractor_production_01",
            "--provider",
            "mock",
            "--prompt-version",
            "v2",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["success"] is True
    assert payload["prompt_version"] == "v2"
