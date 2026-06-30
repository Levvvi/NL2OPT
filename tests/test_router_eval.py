from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "src" / "nl2opt" / "eval" / "router_cases.jsonl"


def test_load_router_cases():
    from nl2opt.eval.router_eval import load_router_cases

    cases = load_router_cases(CASES_PATH)

    assert len(cases) == 20


def test_router_cases_have_required_fields():
    from nl2opt.eval.router_eval import load_router_cases

    cases = load_router_cases(CASES_PATH)

    for case in cases:
        assert {"case_id", "text", "expected_problem_type", "difficulty"} <= set(case)
        assert case["text"]


def test_router_cases_distribution():
    from nl2opt.eval.router_eval import load_router_cases

    cases = load_router_cases(CASES_PATH)
    by_type = Counter(case["expected_problem_type"] for case in cases)
    by_difficulty = Counter(case["difficulty"] for case in cases)

    assert by_type == {
        "production": 6,
        "assignment": 5,
        "jobshop": 5,
        "vrp": 4,
    }
    assert by_difficulty == {
        "easy": 8,
        "medium": 8,
        "hard": 4,
    }


def test_evaluate_router_cases_accuracy():
    from nl2opt.eval.router_eval import evaluate_router_cases

    metrics = evaluate_router_cases(CASES_PATH)

    assert metrics["total"] == 20
    assert metrics["correct"] == 20, metrics["failures"]
    assert metrics["router_accuracy"] == 1.0
    assert metrics["by_type"]["production"] == {"total": 6, "correct": 6}
    assert metrics["by_type"]["assignment"] == {"total": 5, "correct": 5}
    assert metrics["by_type"]["jobshop"] == {"total": 5, "correct": 5}
    assert metrics["by_type"]["vrp"] == {"total": 4, "correct": 4}


def test_router_eval_cli_runs():
    completed = subprocess.run(
        [sys.executable, "-m", "nl2opt.eval.router_eval"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert '"total": 20' in completed.stdout
    assert '"router_accuracy": 1.0' in completed.stdout
