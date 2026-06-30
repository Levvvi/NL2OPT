from __future__ import annotations

import argparse
from pathlib import Path

from nl2opt.pipeline import PipelineResult, run_problem_file


def run_all(output_root: Path) -> list[PipelineResult]:
    project_root = Path(__file__).resolve().parents[1]
    specs_dir = project_root / "examples" / "specs"
    cases = [
        specs_dir / "production_basic.json",
        specs_dir / "assignment_basic.json",
        specs_dir / "jobshop_basic.json",
        specs_dir / "vrp_basic.json",
    ]

    return [
        run_problem_file(spec_path, output_root / spec_path.stem, timeout_sec=10)
        for spec_path in cases
    ]


def print_table(results: list[PipelineResult]) -> None:
    print(f"{'problem_id':<20} {'type':<12} {'status':<10} {'objective':<12} checker")
    for result in results:
        checker = "PASS" if result.checker_passed else "FAIL"
        objective = "" if result.objective_value is None else str(result.objective_value)
        status = "" if result.solver_status is None else result.solver_status
        print(
            f"{result.problem_id:<20} {result.problem_type:<12} {status:<10} {objective:<12} {checker}"
        )


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run all basic NL2OPT examples through the pipeline.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=project_root / "outputs" / "pipeline",
    )
    args = parser.parse_args()

    results = run_all(args.output_root)
    print_table(results)
    return 0 if all(result.checker_passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
