from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CASES_PATH = Path(__file__).with_name("extractor_cases_easy.jsonl")
DEFAULT_MEDIUM_CASES_PATH = Path(__file__).with_name("extractor_cases_medium.jsonl")
DEFAULT_HARD_CASES_PATH = Path(__file__).with_name("extractor_cases_hard.jsonl")

MOJIBAKE_MARKERS = ("�", "鏌", "鐢", "鍜", "涓", "浠", "绋", "€")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        data = json.loads(stripped)
        if not isinstance(data, dict):
            raise ValueError(f"line {line_number} is not a JSON object")
        rows.append(data)
    return rows


def _resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _number_count(text: str) -> int:
    return len(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", text))


def _has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _quality_reasons_for_type(problem_type: str, text: str) -> list[str]:
    reasons: list[str] = []
    numbers = _number_count(text)

    if problem_type == "production":
        checks = [
            ("products", _has_any(text, ["产品", "生产"])),
            ("profit or cost", _has_any(text, ["利润", "profit", "成本", "cost"])),
            ("resource capacity", _has_any(text, ["容量", "capacity"])),
            ("resource consumption", _has_any(text, ["消耗", "consumption"])),
            ("objective", _has_any(text, ["最大化", "最小化", "目标"])),
        ]
        if numbers < 6:
            reasons.append("production case should include profits, capacities, and consumption numbers")
    elif problem_type == "assignment":
        checks = [
            ("workers", _has_any(text, ["员工", "Alice", "Bob", "Chen", "E1", "E2"])),
            ("tasks", _has_any(text, ["任务", "T1", "A", "B"])),
            ("cost matrix", _has_any(text, ["成本矩阵", "costs", "cost"])),
            ("worker capacity", _has_any(text, ["capacity", "最多", "承担"])),
            ("objective", _has_any(text, ["最小化", "最低", "目标"])),
        ]
        if numbers < 4:
            reasons.append("assignment case should include cost matrix numbers")
    elif problem_type == "jobshop":
        checks = [
            ("jobs", _has_any(text, ["工件", "订单", "Order", "J1", "J2"])),
            ("machines", _has_any(text, ["机器", "M1", "M2"])),
            ("operations", _has_any(text, ["工序", "先", "再"])),
            ("durations", _has_any(text, ["加工"])),
            ("objective", _has_any(text, ["makespan", "完工时间", "最小化"])),
        ]
        if numbers < 4:
            reasons.append("jobshop case should include operation duration numbers")
    elif problem_type == "vrp":
        checks = [
            ("depot", "depot" in text),
            ("customers", _has_any(text, ["客户", "C1", "C2"])),
            ("distance_matrix", _has_any(text, ["距离矩阵", "distance"])),
            ("demands", _has_any(text, ["需求量", "需求"])),
            ("vehicle capacity", _has_any(text, ["capacity", "容量"])),
            ("objective", _has_any(text, ["最小化", "最短", "目标"])),
        ]
        if numbers < 8:
            reasons.append("vrp case should include demand, capacity, and distance matrix numbers")
    else:
        checks = []
        reasons.append(f"unsupported expected_problem_type: {problem_type}")

    for label, ok in checks:
        if not ok:
            reasons.append(f"missing {label}")
    return reasons


def audit_case(case: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case.get("case_id") or case.get("id") or "")
    prompt_zh = case.get("prompt_zh")
    text = str(prompt_zh or case.get("text") or "")
    expected_type = str(case.get("expected_problem_type") or "")
    reasons: list[str] = []

    if not case_id:
        reasons.append("missing id/case_id")
    if not case.get("id"):
        reasons.append("missing id")
    if not isinstance(prompt_zh, str) or not prompt_zh.strip():
        reasons.append("missing prompt_zh")
    if not isinstance(case.get("text"), str) or not str(case.get("text")).strip():
        reasons.append("missing text")
    if not expected_type:
        reasons.append("missing expected_problem_type")
    if any(marker in text for marker in MOJIBAKE_MARKERS):
        reasons.append("prompt_zh appears to contain mojibake")

    gold_spec_path = case.get("gold_spec_path")
    if not gold_spec_path:
        reasons.append("missing gold_spec_path")
    else:
        resolved = _resolve_project_path(str(gold_spec_path))
        if not resolved.exists():
            reasons.append(f"gold_spec_path does not exist: {gold_spec_path}")

    if "expected_objective_value" not in case:
        reasons.append("missing expected_objective_value")

    reasons.extend(_quality_reasons_for_type(expected_type, text))

    return {
        "case_id": case_id,
        "expected_problem_type": expected_type,
        "difficulty": case.get("difficulty"),
        "status": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
    }


def _paths_for_difficulty(path: Path | None, difficulty: str | None) -> list[Path]:
    if path is not None:
        return [Path(path)]
    if difficulty == "medium":
        return [DEFAULT_MEDIUM_CASES_PATH]
    if difficulty == "hard":
        return [DEFAULT_HARD_CASES_PATH]
    if difficulty == "all":
        return [DEFAULT_CASES_PATH, DEFAULT_MEDIUM_CASES_PATH, DEFAULT_HARD_CASES_PATH]
    return [DEFAULT_CASES_PATH]


def audit_case_file(path: Path | None, difficulty: str | None = None) -> dict[str, Any]:
    paths = _paths_for_difficulty(path, difficulty)
    cases: list[dict[str, Any]] = []
    for case_path in paths:
        cases.extend(_load_jsonl(case_path))
    if difficulty is not None and difficulty != "all":
        cases = [case for case in cases if case.get("difficulty") == difficulty]
    results = [audit_case(case) for case in cases]
    passed = sum(1 for result in results if result["status"] == "PASS")
    total = len(results)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "cases": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit NL2OPT extractor case quality.")
    parser.add_argument("--cases", type=Path, default=None)
    parser.add_argument("--difficulty", default=None)
    args = parser.parse_args(argv)

    summary = audit_case_file(args.cases, difficulty=args.difficulty)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
