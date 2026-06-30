from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CASES_PATH = PROJECT_ROOT / "src" / "nl2opt" / "eval" / "extractor_cases_easy.jsonl"
DEFAULT_FINAL_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "deepseek_extractor_eval" / "all" / "summary.json"
DEMO_CASE_IDS = (
    "extractor_production_01",
    "extractor_jobshop_01",
    "extractor_vrp_01",
)


@dataclass(frozen=True)
class DemoCase:
    case_id: str
    category: str
    difficulty: str
    prompt_zh: str
    expected_problem_type: str


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        data = json.loads(stripped)
        if isinstance(data, dict):
            rows.append(data)
    return rows


def load_demo_cases(path: Path = DEFAULT_CASES_PATH) -> list[DemoCase]:
    cases_by_id = {str(row.get("case_id")): row for row in _load_jsonl(path)}
    demo_cases: list[DemoCase] = []
    for case_id in DEMO_CASE_IDS:
        row = cases_by_id[case_id]
        demo_cases.append(
            DemoCase(
                case_id=case_id,
                category=str(row["expected_problem_type"]),
                difficulty=str(row["difficulty"]),
                prompt_zh=str(row.get("prompt_zh") or row["text"]),
                expected_problem_type=str(row["expected_problem_type"]),
            )
        )
    return demo_cases


def load_final_eval_summary(path: Path = DEFAULT_FINAL_SUMMARY_PATH) -> dict[str, Any]:
    if not path.exists():
        return {
            "found": False,
            "path": str(path),
            "total": None,
            "end_to_end_success": None,
            "spec_success": None,
            "checker_success": None,
            "objective_match": None,
            "failure_breakdown": None,
        }

    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "found": True,
        "path": str(path),
        "provider": data.get("provider"),
        "model": data.get("model"),
        "mock": data.get("mock"),
        "prompt_version": data.get("prompt_version"),
        "total": data.get("total"),
        "end_to_end_success": data.get("end_to_end_success"),
        "spec_success": data.get("spec_success"),
        "checker_success": data.get("checker_success"),
        "objective_match": data.get("objective_match"),
        "failure_breakdown": data.get("failure_breakdown"),
    }
