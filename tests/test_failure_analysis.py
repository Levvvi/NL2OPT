from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_cases(path: Path) -> None:
    case = {
        "case_id": "extractor_production_02",
        "text": "小工厂生产 X 和 Y。",
        "expected_problem_type": "production",
        "difficulty": "easy",
        "gold_spec_path": "examples/specs/production_tiny.json",
        "expected_objective_value": 23,
    }
    path.write_text(json.dumps(case, ensure_ascii=False) + "\n", encoding="utf-8")


def test_analyze_missing_eval_dir_returns_no_live_data(tmp_path):
    from nl2opt.eval.failure_analysis import analyze_deepseek_eval_outputs

    summary = analyze_deepseek_eval_outputs(tmp_path / "missing")

    assert summary["failure_breakdown"] == {"no_live_data": 1}
    assert summary["cases"][0]["failure_stage"] == "no_live_data"
    assert summary["completed_cases"] == 0


def test_analyze_empty_eval_dir_returns_no_live_data(tmp_path):
    from nl2opt.eval.failure_analysis import analyze_deepseek_eval_outputs

    eval_dir = tmp_path / "empty_eval"
    eval_dir.mkdir()
    cases_path = tmp_path / "cases.jsonl"
    write_cases(cases_path)

    summary = analyze_deepseek_eval_outputs(eval_dir, cases_path)

    assert summary["failure_breakdown"] == {"no_live_data": 1}
    assert summary["cases"][0]["failure_stage"] == "no_live_data"


def test_analyze_summary_json_success(tmp_path):
    from nl2opt.eval.failure_analysis import analyze_deepseek_eval_outputs

    eval_dir = tmp_path / "eval"
    write_json(
        eval_dir / "summary.json",
        {
            "total": 1,
            "end_to_end_success": 1,
            "end_to_end_pass_rate": 1.0,
            "failure_breakdown": {},
            "case_results": [
                {
                    "case_id": "extractor_production_02",
                    "problem_type": "production",
                    "objective_value": 23,
                    "checker_passed": True,
                    "end_to_end_passed": True,
                }
            ],
        },
    )

    summary = analyze_deepseek_eval_outputs(eval_dir)

    assert summary["total"] == 1
    assert summary["completed_cases"] == 1
    assert summary["end_to_end_success"] == 1
    assert summary["end_to_end_pass_rate"] == 1.0


def test_analyze_failure_json_schema_validation_error(tmp_path):
    from nl2opt.eval.failure_analysis import analyze_deepseek_eval_outputs

    eval_dir = tmp_path / "eval"
    case_dir = eval_dir / "extractor_production_02"
    cases_path = tmp_path / "cases.jsonl"
    write_cases(cases_path)
    write_json(
        case_dir / "extractor_result.json",
        {
            "case_id": "extractor_production_02",
            "expected_problem_type": "production",
            "routed_problem_type": "production",
            "router_correct": True,
            "extractor_success": False,
            "validation_errors": ["products: Field required"],
            "error": "schema validation failed",
        },
    )
    write_json(
        case_dir / "failure.json",
        {
            "case_id": "extractor_production_02",
            "failure_stage": "schema_validation_error",
            "message": "products: Field required",
            "raw_response_path": str(case_dir / "raw_response.txt"),
        },
    )

    summary = analyze_deepseek_eval_outputs(eval_dir, cases_path)
    case = summary["cases"][0]

    assert case["failure_stage"] == "schema_validation_error"
    assert "schema" in case["suggested_action"].lower()
    assert summary["failure_breakdown"] == {"schema_validation_error": 1}


def test_analyze_pipeline_objective_mismatch(tmp_path):
    from nl2opt.eval.failure_analysis import analyze_deepseek_eval_outputs

    eval_dir = tmp_path / "eval"
    case_dir = eval_dir / "extractor_production_02"
    cases_path = tmp_path / "cases.jsonl"
    write_cases(cases_path)
    write_json(
        case_dir / "extractor_result.json",
        {
            "case_id": "extractor_production_02",
            "expected_problem_type": "production",
            "routed_problem_type": "production",
            "router_correct": True,
            "extractor_success": True,
        },
    )
    write_json(
        case_dir / "pipeline_report.json",
        {
            "problem_id": "production_tiny",
            "problem_type": "production",
            "objective_value": 20,
            "checker_passed": True,
            "error": None,
        },
    )

    summary = analyze_deepseek_eval_outputs(eval_dir, cases_path)
    case = summary["cases"][0]

    assert case["failure_stage"] == "objective_mismatch"
    assert case["expected_objective_value"] == 23
    assert case["objective_value"] == 20


def test_analyze_missing_required_fields(tmp_path):
    from nl2opt.eval.failure_analysis import analyze_deepseek_eval_outputs

    eval_dir = tmp_path / "eval"
    case_dir = eval_dir / "extractor_production_02"
    cases_path = tmp_path / "cases.jsonl"
    write_cases(cases_path)
    write_json(
        case_dir / "extractor_result.json",
        {
            "case_id": "extractor_production_02",
            "expected_problem_type": "production",
            "routed_problem_type": "production",
            "router_correct": True,
            "extractor_success": True,
            "validation_errors": [],
            "error": None,
        },
    )
    write_json(
        case_dir / "failure.json",
        {
            "case_id": "extractor_production_02",
            "failure_stage": "missing_required_fields",
            "message": "missing required fields: consumption.X.labor",
            "raw_response_path": str(case_dir / "raw_response.txt"),
        },
    )

    summary = analyze_deepseek_eval_outputs(eval_dir, cases_path)

    assert summary["failure_breakdown"] == {"missing_required_fields": 1}
    assert summary["cases"][0]["failure_stage"] == "missing_required_fields"


def test_write_failure_report_markdown(tmp_path):
    from nl2opt.eval.failure_analysis import write_failure_report

    summary = {
        "status": "no_live_data",
        "total": 0,
        "completed_cases": 0,
        "end_to_end_success": 0,
        "end_to_end_pass_rate": 0.0,
        "failure_breakdown": {"no_live_data": 1},
        "cases": [],
        "suggested_next_actions": ["Run DeepSeek eval first."],
    }
    report_path = write_failure_report(summary, tmp_path / "report.md")

    text = report_path.read_text(encoding="utf-8")
    assert "# DeepSeek Extractor Failure Analysis" in text
    assert "no_live_data" in text
    assert "Re-run Commands" in text


def test_failure_analysis_cli_missing_eval_dir(tmp_path):
    report_path = tmp_path / "deepseek_easy_failure_analysis.md"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.eval.failure_analysis",
            "--eval-dir",
            str(tmp_path / "missing"),
            "--report",
            str(report_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["failure_breakdown"] == {"no_live_data": 1}
    assert report_path.exists()


def test_failure_analysis_cli_infers_medium_cases_from_eval_dir(tmp_path):
    eval_dir = tmp_path / "medium"
    report_path = tmp_path / "report.md"
    medium_case_ids = [
        "extractor_production_medium_01",
        "extractor_production_medium_02",
        "extractor_assignment_medium_01",
        "extractor_assignment_medium_02",
        "extractor_jobshop_medium_01",
        "extractor_jobshop_medium_02",
        "extractor_vrp_medium_01",
        "extractor_vrp_medium_02",
    ]
    write_json(
        eval_dir / "summary.json",
        {
            "total": 8,
            "difficulty": "medium",
            "case_results": [
                {
                    "case_id": case_id,
                    "problem_type": case_id.split("_")[1],
                    "router_problem_type": "production",
                    "spec_success": True,
                    "checker_passed": True,
                    "objective_matched": True,
                    "objective_value": 3000,
                    "end_to_end_passed": True,
                    "status": "OK",
                }
                for case_id in medium_case_ids
            ],
        },
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.eval.failure_analysis",
            "--eval-dir",
            str(eval_dir),
            "--report",
            str(report_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["failure_breakdown"] == {}


def test_failure_analysis_cli_infers_hard_cases_from_eval_dir(tmp_path):
    eval_dir = tmp_path / "hard"
    report_path = tmp_path / "report.md"
    hard_case_ids = [
        "extractor_production_hard_01",
        "extractor_assignment_hard_01",
        "extractor_jobshop_hard_01",
        "extractor_vrp_hard_01",
    ]
    write_json(
        eval_dir / "summary.json",
        {
            "total": 4,
            "difficulty": "hard",
            "case_results": [
                {
                    "case_id": case_id,
                    "problem_type": case_id.split("_")[1],
                    "router_problem_type": case_id.split("_")[1],
                    "spec_success": True,
                    "checker_passed": True,
                    "objective_matched": True,
                    "objective_value": 1,
                    "end_to_end_passed": True,
                    "status": "OK",
                }
                for case_id in hard_case_ids
            ],
        },
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.eval.failure_analysis",
            "--eval-dir",
            str(eval_dir),
            "--report",
            str(report_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["total"] == 4
    assert payload["failure_breakdown"] == {}


def test_failure_analysis_cli_infers_all_cases_from_eval_dir(tmp_path):
    eval_dir = tmp_path / "all"
    report_path = tmp_path / "report.md"
    all_case_ids = [
        "extractor_production_01",
        "extractor_production_02",
        "extractor_assignment_01",
        "extractor_assignment_02",
        "extractor_jobshop_01",
        "extractor_jobshop_02",
        "extractor_vrp_01",
        "extractor_vrp_02",
        "extractor_production_medium_01",
        "extractor_production_medium_02",
        "extractor_assignment_medium_01",
        "extractor_assignment_medium_02",
        "extractor_jobshop_medium_01",
        "extractor_jobshop_medium_02",
        "extractor_vrp_medium_01",
        "extractor_vrp_medium_02",
        "extractor_production_hard_01",
        "extractor_assignment_hard_01",
        "extractor_jobshop_hard_01",
        "extractor_vrp_hard_01",
    ]
    write_json(
        eval_dir / "summary.json",
        {
            "total": 20,
            "difficulty": "all",
            "case_results": [
                {
                    "case_id": case_id,
                    "problem_type": "production",
                    "router_problem_type": "production",
                    "spec_success": True,
                    "checker_passed": True,
                    "objective_matched": True,
                    "objective_value": 1,
                    "end_to_end_passed": True,
                    "status": "OK",
                }
                for case_id in all_case_ids
            ],
        },
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.eval.failure_analysis",
            "--eval-dir",
            str(eval_dir),
            "--report",
            str(report_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["total"] == 20
    assert payload["failure_breakdown"] == {}
