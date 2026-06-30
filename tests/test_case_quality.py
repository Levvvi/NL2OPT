from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "src" / "nl2opt" / "eval" / "extractor_cases_easy.jsonl"
MEDIUM_CASES_PATH = ROOT / "src" / "nl2opt" / "eval" / "extractor_cases_medium.jsonl"
HARD_CASES_PATH = ROOT / "src" / "nl2opt" / "eval" / "extractor_cases_hard.jsonl"


def test_audit_easy_cases_passes_project_cases():
    from nl2opt.eval.case_quality import audit_case_file

    summary = audit_case_file(CASES_PATH, difficulty="easy")

    assert summary["total"] == 8
    assert summary["passed"] == 8, summary["cases"]
    assert summary["failed"] == 0


def test_audit_medium_cases_passes_project_cases():
    from nl2opt.eval.case_quality import audit_case_file

    summary = audit_case_file(MEDIUM_CASES_PATH, difficulty="medium")

    assert summary["total"] == 8
    assert summary["passed"] == 8, summary["cases"]
    assert summary["failed"] == 0


def test_audit_hard_cases_passes_project_cases():
    from nl2opt.eval.case_quality import audit_case_file

    summary = audit_case_file(HARD_CASES_PATH, difficulty="hard")

    assert summary["total"] == 4
    assert summary["passed"] == 4, summary["cases"]
    assert summary["failed"] == 0


def test_audit_all_cases_passes_project_cases():
    from nl2opt.eval.case_quality import audit_case_file

    summary = audit_case_file(None, difficulty="all")

    assert summary["total"] == 20
    assert summary["passed"] == 20, summary["cases"]
    assert summary["failed"] == 0


def test_case_quality_detects_mojibake_and_missing_numbers(tmp_path):
    from nl2opt.eval.case_quality import audit_case_file

    bad_case = {
        "case_id": "bad_assignment",
        "id": "bad_assignment",
        "text": "闇€瑕佹妸 T1 鍒?T4 鍒嗛厤缁欏憳宸ワ紝鎴愭湰鏈€浣庛€?",
        "prompt_zh": "闇€瑕佹妸 T1 鍒?T4 鍒嗛厤缁欏憳宸ワ紝鎴愭湰鏈€浣庛€?",
        "expected_problem_type": "assignment",
        "difficulty": "easy",
        "gold_spec_path": "examples/specs/assignment_basic.json",
        "expected_objective_value": 21,
    }
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(bad_case, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = audit_case_file(path, difficulty="easy")

    assert summary["failed"] == 1
    reasons = " ".join(summary["cases"][0]["reasons"])
    assert "mojibake" in reasons
    assert "cost matrix" in reasons


def test_case_quality_cli_runs():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.eval.case_quality",
            "--difficulty",
            "easy",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["total"] == 8
    assert payload["failed"] == 0


def test_case_quality_cli_medium_and_all_run():
    for difficulty, total in [("medium", 8), ("hard", 4), ("all", 20)]:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "nl2opt.eval.case_quality",
                "--difficulty",
                difficulty,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        assert completed.returncode == 0, completed.stdout + completed.stderr
        payload = json.loads(completed.stdout)
        assert payload["total"] == total
        assert payload["failed"] == 0
