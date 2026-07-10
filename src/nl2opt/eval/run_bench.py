"""Command-line entry point for the pinned public benchmark runner."""

from __future__ import annotations

import argparse
from pathlib import Path

from nl2opt.eval.benchmark import BenchmarkRunConfig, DEFAULT_DATASETS_DIR, DEFAULT_RESULTS_DIR, run_benchmark


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the pinned NL4Opt/IndustryOR benchmark.")
    parser.add_argument("--dataset", choices=("all", "nl4opt", "industryor"), default="all")
    parser.add_argument("--track", choices=("all", "en", "zh"), default="all")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--checker-retry", choices=("on", "off"), default="off")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout-sec", type=int, default=60)
    parser.add_argument("--run-id", default="benchmark")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        results = run_benchmark(
            BenchmarkRunConfig(
                datasets_dir=DEFAULT_DATASETS_DIR,
                results_dir=DEFAULT_RESULTS_DIR,
                dataset=args.dataset,
                track=args.track,
                repetitions=args.repetitions,
                checker_retry=args.checker_retry == "on",
                resume=args.resume,
                limit=args.limit,
                timeout_sec=args.timeout_sec,
                run_id=args.run_id,
            )
        )
    except (ValueError, OSError) as exc:
        print(f"benchmark failed: {exc}")
        return 1
    print(Path(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
