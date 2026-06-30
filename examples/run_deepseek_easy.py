from __future__ import annotations

import argparse
from pathlib import Path

from nl2opt.eval.extractor_eval import evaluate_deepseek_extractor_cases


def print_table(case_results: list[dict]) -> None:
    print(f"{'case_id':<28} {'type':<12} {'spec':<8} {'checker':<8} {'objective':<12} status")
    for result in case_results:
        spec = "PASS" if result["spec_success"] else "FAIL"
        checker = "PASS" if result["checker_passed"] else "SKIP"
        objective = "-" if result["objective_value"] is None else str(result["objective_value"])
        print(
            f"{result['case_id']:<28} {result['problem_type']:<12} {spec:<8} "
            f"{checker:<8} {objective:<12} {result['status']}"
        )


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run DeepSeek extraction on the 8 easy NL2OPT cases.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=project_root / "src" / "nl2opt" / "eval" / "extractor_cases_easy.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "outputs" / "deepseek_extractor_eval",
    )
    parser.add_argument("--timeout-sec", type=int, default=10)
    parser.add_argument("--model", default=None)
    parser.add_argument("--prompt-version", default="v2")
    args = parser.parse_args()

    try:
        metrics = evaluate_deepseek_extractor_cases(
            args.cases,
            args.output_dir,
            timeout_sec=args.timeout_sec,
            model=args.model,
            prompt_version=args.prompt_version,
        )
    except Exception as exc:
        print(f"DeepSeek evaluation could not start: {exc}")
        return 1

    print_table(metrics["case_results"])
    print(f"summary_path: {metrics['summary_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
