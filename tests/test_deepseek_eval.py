from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "src" / "nl2opt" / "eval" / "extractor_cases_easy.jsonl"


class StaticClient:
    def __init__(self, payload: dict):
        self.payload = payload

    def complete_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.0):
        from nl2opt.agents.llm_client import LLMResponse

        return LLMResponse(
            content=json.dumps(self.payload, ensure_ascii=False),
            provider="deepseek",
            model="deepseek-v4-flash",
            usage={"prompt_tokens": 1, "completion_tokens": 1},
            raw={"id": "fake"},
        )


def write_single_case(tmp_path: Path) -> Path:
    case = {
        "case_id": "extractor_production_02",
        "text": "小工厂要生产 X 和 Y 两种产品，利润不同，都会消耗 labor 和 material 两类资源，想在资源容量内最大化 profit。",
        "expected_problem_type": "production",
        "difficulty": "easy",
        "gold_spec_path": "examples/specs/production_tiny.json",
        "expected_objective_value": 23,
    }
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(case, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def test_evaluate_deepseek_requires_api_key_or_client(monkeypatch, tmp_path):
    from nl2opt.eval.extractor_eval import evaluate_deepseek_extractor_cases

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        evaluate_deepseek_extractor_cases(write_single_case(tmp_path), tmp_path / "out")


def test_deepseek_eval_summary_schema(tmp_path):
    from nl2opt.eval.extractor_eval import evaluate_deepseek_extractor_cases

    spec_path = ROOT / "examples" / "specs" / "production_tiny.json"
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    cases_path = write_single_case(tmp_path)
    output_dir = tmp_path / "deepseek_eval"

    metrics = evaluate_deepseek_extractor_cases(
        cases_path,
        output_dir,
        client_factory=lambda case: StaticClient(payload),
    )

    assert metrics["total"] == 1
    assert metrics["router_accuracy"] == 1.0
    assert metrics["spec_pass_rate"] == 1.0
    assert metrics["checker_pass_rate"] == 1.0
    assert metrics["objective_match_rate"] == 1.0
    assert metrics["end_to_end_pass_rate"] == 1.0
    assert metrics["provider"] == "deepseek"
    assert metrics["mock"] is False
    assert metrics["model"] == "deepseek-v4-flash"
    assert metrics["summary_path"] == str(output_dir / "summary.json")

    case_dir = output_dir / "extractor_production_02"
    assert (case_dir / "raw_response.txt").exists()
    assert (case_dir / "parsed_spec.json").exists()
    assert (case_dir / "extractor_result.json").exists()
    assert (case_dir / "pipeline_report.json").exists()
    assert (output_dir / "summary.json").exists()


def test_deepseek_eval_cleans_stale_case_artifacts(tmp_path):
    from nl2opt.eval.extractor_eval import evaluate_deepseek_extractor_cases

    cases_path = write_single_case(tmp_path)
    output_dir = tmp_path / "deepseek_eval"
    case_dir = output_dir / "extractor_production_02"
    case_dir.mkdir(parents=True)
    (case_dir / "parsed_spec.json").write_text('{"stale": true}', encoding="utf-8")
    (case_dir / "pipeline_report.json").write_text('{"stale": true}', encoding="utf-8")

    bad_payload = {
        "problem_id": "bad",
        "problem_type": "production",
        "objective": {"sense": "maximize", "name": "profit"},
    }

    metrics = evaluate_deepseek_extractor_cases(
        cases_path,
        output_dir,
        client_factory=lambda case: StaticClient(bad_payload),
    )

    assert metrics["spec_success"] == 0
    assert not (case_dir / "parsed_spec.json").exists()
    assert not (case_dir / "pipeline_report.json").exists()
    assert (case_dir / "raw_response.txt").exists()
    assert (case_dir / "extractor_result.json").exists()
    assert (case_dir / "failure.json").exists()


def test_deepseek_eval_stops_before_pipeline_for_missing_required_fields(tmp_path):
    from nl2opt.eval.extractor_eval import evaluate_deepseek_extractor_cases

    payload = json.loads((ROOT / "examples" / "specs" / "production_tiny.json").read_text(encoding="utf-8"))
    payload["missing_fields"] = ["consumption.X.labor"]

    output_dir = tmp_path / "deepseek_eval"
    metrics = evaluate_deepseek_extractor_cases(
        write_single_case(tmp_path),
        output_dir,
        client_factory=lambda case: StaticClient(payload),
    )

    case_dir = output_dir / "extractor_production_02"
    failure = json.loads((case_dir / "failure.json").read_text(encoding="utf-8"))

    assert metrics["failure_breakdown"] == {"missing_required_fields": 1}
    assert metrics["spec_success"] == 1
    assert metrics["execution_success"] == 0
    assert failure["failure_stage"] == "missing_required_fields"
    assert not (case_dir / "pipeline_report.json").exists()


def test_extractor_eval_provider_mock_still_works(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.eval.extractor_eval",
            "--mock",
            "--cases",
            str(CASES_PATH),
            "--output-dir",
            str(tmp_path / "mock_eval"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert '"end_to_end_pass_rate": 1.0' in completed.stdout


def test_extractor_eval_cli_deepseek_missing_key_exits_nonzero(monkeypatch, tmp_path):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.eval.extractor_eval",
            "--provider",
            "deepseek",
            "--cases",
            str(CASES_PATH),
            "--output-dir",
            str(tmp_path / "deepseek_eval"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "DEEPSEEK_API_KEY" in completed.stdout


def test_extractor_eval_cli_defaults_to_deepseek_missing_key(monkeypatch, tmp_path):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.eval.extractor_eval",
            "--cases",
            str(CASES_PATH),
            "--output-dir",
            str(tmp_path / "deepseek_eval"),
            "--prompt-version",
            "v2",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "DEEPSEEK_API_KEY" in completed.stdout


def test_extractor_eval_check_env_does_not_print_secret(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "super-secret-value")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.eval.extractor_eval",
            "--check-env",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "DEEPSEEK_API_KEY_SOURCE=process_env" in completed.stdout
    assert "super-secret-value" not in completed.stdout
