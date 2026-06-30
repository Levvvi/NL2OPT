from __future__ import annotations

import argparse
from pathlib import Path

from nl2opt.eval.extractor_eval import evaluate_mock_extractor_cases


def print_table(case_results: list[dict]) -> None:
    print(f"{'case_id':<28} {'type':<12} {'objective':<12} checker")
    for result in case_results:
        checker = "PASS" if result["end_to_end_passed"] else "FAIL"
        objective = "" if result["objective_value"] is None else str(result["objective_value"])
        print(f"{result['case_id']:<28} {result['problem_type']:<12} {objective:<12} {checker}")


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run mock Chinese NL extraction cases end to end.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=project_root / "src" / "nl2opt" / "eval" / "extractor_cases_easy.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "outputs" / "mock_extractor_eval",
    )
    parser.add_argument("--timeout-sec", type=int, default=10)
    parser.add_argument("--prompt-version", default="v2")
    args = parser.parse_args()

    metrics = evaluate_mock_extractor_cases(
        args.cases,
        args.output_dir,
        timeout_sec=args.timeout_sec,
        prompt_version=args.prompt_version,
    )
    print_table(metrics["case_results"])
    return 0 if metrics["end_to_end_pass_rate"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
