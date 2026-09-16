from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "src" / "nl2opt" / "eval" / "extractor_cases_easy.jsonl"
MEDIUM_CASES_PATH = ROOT / "src" / "nl2opt" / "eval" / "extractor_cases_medium.jsonl"
HARD_CASES_PATH = ROOT / "src" / "nl2opt" / "eval" / "extractor_cases_hard.jsonl"


def test_load_extractor_cases_easy():
    from nl2opt.eval.extractor_eval import load_extractor_cases

    cases = load_extractor_cases(CASES_PATH)

    assert len(cases) == 8


def test_load_extractor_cases_medium_hard_and_all():
    from nl2opt.eval.extractor_eval import load_extractor_cases

    medium_cases = load_extractor_cases(None, difficulty="medium")
    hard_cases = load_extractor_cases(None, difficulty="hard")
    all_cases = load_extractor_cases(None, difficulty="all")

    assert len(medium_cases) == 8
    assert all(case["difficulty"] == "medium" for case in medium_cases)
    assert len(hard_cases) == 4
    assert all(case["difficulty"] == "hard" for case in hard_cases)
    assert len(all_cases) == 20


def test_extractor_cases_distribution():
    from nl2opt.eval.extractor_eval import load_extractor_cases

    cases = load_extractor_cases(CASES_PATH)
    by_type = Counter(case["expected_problem_type"] for case in cases)

    assert by_type == {
        "production": 2,
        "assignment": 2,
        "jobshop": 2,
        "vrp": 2,
    }
    assert {case["difficulty"] for case in cases} == {"easy"}


def test_extractor_cases_gold_spec_paths_exist():
    from nl2opt.eval.extractor_eval import load_extractor_cases

    for case in load_extractor_cases(CASES_PATH):
        assert (ROOT / case["gold_spec_path"]).exists()


def test_extractor_cases_router_classification():
    from nl2opt.agents.router import route_text
    from nl2opt.eval.extractor_eval import load_extractor_cases

    failures = []
    for case in load_extractor_cases(CASES_PATH):
        result = route_text(case["text"])
        if result.problem_type.value != case["expected_problem_type"]:
            failures.append((case["case_id"], result.problem_type.value, result.reason))

    assert failures == []


def test_evaluate_mock_extractor_cases_metrics(tmp_path):
    from nl2opt.eval.extractor_eval import evaluate_mock_extractor_cases

    metrics = evaluate_mock_extractor_cases(CASES_PATH, tmp_path / "mock_eval", timeout_sec=30)

    assert metrics["total"] == 8
    assert metrics["router_accuracy"] == 1.0
    assert metrics["spec_pass_rate"] == 1.0
    assert metrics["checker_pass_rate"] == 1.0
    assert metrics["end_to_end_pass_rate"] == 1.0


def test_evaluate_mock_extractor_cases_medium_metrics(tmp_path):
    from nl2opt.eval.extractor_eval import evaluate_mock_extractor_cases

    metrics = evaluate_mock_extractor_cases(
        MEDIUM_CASES_PATH,
        tmp_path / "mock_medium",
        prompt_version="v3",
        difficulty="medium",
        timeout_sec=30,
    )

    assert metrics["total"] == 8
    assert metrics["difficulty"] == "medium"
    assert metrics["end_to_end_success"] == 8
    assert metrics["end_to_end_pass_rate"] == 1.0
    assert metrics["failures"] == []
    assert (tmp_path / "mock_medium" / "summary.json").exists()


def test_evaluate_mock_extractor_cases_hard_metrics(tmp_path):
    from nl2opt.eval.extractor_eval import evaluate_mock_extractor_cases

    metrics = evaluate_mock_extractor_cases(
        HARD_CASES_PATH,
        tmp_path / "mock_hard",
        prompt_version="v3",
        difficulty="hard",
        timeout_sec=30,
    )

    assert metrics["total"] == 4
    assert metrics["difficulty"] == "hard"
    assert metrics["end_to_end_success"] == 4
    assert metrics["end_to_end_pass_rate"] == 1.0
    assert metrics["failures"] == []
    assert (tmp_path / "mock_hard" / "summary.json").exists()


def test_evaluate_mock_extractor_cases_all_metrics(tmp_path):
    from nl2opt.eval.extractor_eval import evaluate_mock_extractor_cases

    metrics = evaluate_mock_extractor_cases(
        None,
        tmp_path / "mock_all",
        prompt_version="v3",
        difficulty="all",
        timeout_sec=30,
    )

    assert metrics["total"] == 20
    assert metrics["difficulty"] == "all"
    assert metrics["end_to_end_success"] == 20
    assert metrics["end_to_end_pass_rate"] == 1.0
    assert metrics["failures"] == []


def test_extractor_eval_cli_runs(tmp_path):
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
            "--timeout-sec",
            "30",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=270,  # Eight cases at 30 seconds each, plus CLI startup headroom.
    )

    assert completed.returncode == 0, completed.stderr
    assert '"total": 8' in completed.stdout
    assert '"end_to_end_pass_rate": 1.0' in completed.stdout
