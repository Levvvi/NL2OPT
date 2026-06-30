from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from nl2opt.agents.router import route_text


DEFAULT_CASES_PATH = Path(__file__).with_name("router_cases.jsonl")


def load_router_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        case = json.loads(line)
        if not isinstance(case, dict):
            raise ValueError(f"router case line {line_number} must be a JSON object")
        cases.append(case)
    return cases


def evaluate_router_cases(path: Path) -> dict[str, Any]:
    cases = load_router_cases(path)
    by_type: dict[str, dict[str, int]] = {}
    failures: list[dict[str, Any]] = []

    for case in cases:
        expected = case["expected_problem_type"]
        by_type.setdefault(expected, {"total": 0, "correct": 0})
        by_type[expected]["total"] += 1

        result = route_text(case["text"])
        predicted = result.problem_type.value
        if predicted == expected:
            by_type[expected]["correct"] += 1
        else:
            failures.append(
                {
                    "case_id": case.get("case_id"),
                    "expected": expected,
                    "predicted": predicted,
                    "text": case.get("text"),
                    "matched_keywords": result.matched_keywords,
                    "reason": result.reason,
                }
            )

    correct = sum(type_metrics["correct"] for type_metrics in by_type.values())
    total = len(cases)
    accuracy = correct / total if total else 0.0

    return {
        "total": total,
        "correct": correct,
        "router_accuracy": accuracy,
        "by_type": by_type,
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the rule-based NL2OPT router.")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_CASES_PATH)
    args = parser.parse_args(argv)

    metrics = evaluate_router_cases(args.path)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0 if not metrics["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
