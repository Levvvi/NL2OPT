from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from nl2opt.agents.extractor import extract_problem_spec
from nl2opt.agents.llm_client import DeepSeekClient, LLMClient, MockLLMClient
from nl2opt.agents.router import route_text
from nl2opt.config import get_deepseek_api_key_source
from nl2opt.pipeline import run_problem_spec
from nl2opt.schemas import ProblemType


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CASES_PATH = Path(__file__).with_name("extractor_cases_easy.jsonl")
DEFAULT_MEDIUM_CASES_PATH = Path(__file__).with_name("extractor_cases_medium.jsonl")
DEFAULT_HARD_CASES_PATH = Path(__file__).with_name("extractor_cases_hard.jsonl")


def _case_paths_for_difficulty(path: Path | None, difficulty: str | None) -> list[Path]:
    if path is not None:
        return [Path(path)]
    if difficulty == "medium":
        return [DEFAULT_MEDIUM_CASES_PATH]
    if difficulty == "hard":
        return [DEFAULT_HARD_CASES_PATH]
    if difficulty == "all":
        return [DEFAULT_CASES_PATH, DEFAULT_MEDIUM_CASES_PATH, DEFAULT_HARD_CASES_PATH]
    return [DEFAULT_CASES_PATH]


def load_extractor_cases(path: Path | None, difficulty: str | None = None) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for case_path in _case_paths_for_difficulty(path, difficulty):
        for line_number, line in enumerate(case_path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            data = json.loads(stripped)
            if not isinstance(data, dict):
                raise ValueError(f"{case_path}: line {line_number} is not a JSON object")
            cases.append(data)
    if difficulty is not None and difficulty != "all":
        cases = [case for case in cases if case.get("difficulty") == difficulty]
    return cases


def _resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _objective_matches(actual: float | None, expected: Any, tolerance: float = 1e-6) -> bool:
    if actual is None:
        return False
    try:
        return abs(float(actual) - float(expected)) <= tolerance
    except (TypeError, ValueError):
        return False


def evaluate_mock_extractor_cases(
    path: Path | None,
    output_dir: Path,
    timeout_sec: int = 10,
    prompt_version: str = "v2",
    difficulty: str = "easy",
) -> dict[str, Any]:
    cases = load_extractor_cases(path, difficulty=difficulty)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    router_correct = 0
    spec_success = 0
    execution_success = 0
    checker_success = 0
    end_to_end_success = 0
    runtimes: list[float] = []
    failures: list[dict[str, Any]] = []
    failure_breakdown: Counter[str] = Counter()
    by_type: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "end_to_end_success": 0})
    case_results: list[dict[str, Any]] = []

    def add_failure(case_id: str, category: str, message: str) -> None:
        failure_breakdown[category] += 1
        failures.append({"case_id": case_id, "category": category, "message": message})

    for case in cases:
        case_id = str(case["case_id"])
        expected_type = str(case["expected_problem_type"])
        by_type[expected_type]["total"] += 1

        route_result = route_text(str(case["text"]))
        router_ok = route_result.problem_type.value == expected_type
        if router_ok:
            router_correct += 1
        else:
            add_failure(
                case_id,
                "router",
                f"expected {expected_type}, got {route_result.problem_type.value}",
            )

        pipeline_result = None
        extraction_result = None
        try:
            gold_spec = _load_json(_resolve_project_path(str(case["gold_spec_path"])))
            extraction_result = extract_problem_spec(
                str(case["text"]),
                problem_type=route_result.problem_type,
                client=MockLLMClient(gold_spec),
                prompt_version=prompt_version,
            )
        except Exception as exc:
            add_failure(case_id, "extractor", str(exc))

        if extraction_result is not None and extraction_result.success:
            spec_success += 1
            pipeline_result = run_problem_spec(
                extraction_result.spec,
                output_dir / case_id,
                timeout_sec=timeout_sec,
            )
            if pipeline_result.runtime_sec is not None:
                runtimes.append(pipeline_result.runtime_sec)
            if (
                pipeline_result.returncode == 0
                and not pipeline_result.timed_out
                and pipeline_result.solver_status is not None
            ):
                execution_success += 1
            else:
                add_failure(case_id, "execution", pipeline_result.error or "execution failed")
            if pipeline_result.checker_passed:
                checker_success += 1
            else:
                add_failure(case_id, "checker", pipeline_result.error or "checker failed")
        elif extraction_result is not None:
            add_failure(
                case_id,
                "extractor",
                extraction_result.error or "extractor failed",
            )

        objective_ok = False
        if pipeline_result is not None:
            objective_ok = _objective_matches(
                pipeline_result.objective_value,
                case["expected_objective_value"],
            )
            if not objective_ok:
                add_failure(
                    case_id,
                    "objective",
                    f"expected {case['expected_objective_value']}, got {pipeline_result.objective_value}",
                )

        case_ok = bool(router_ok and extraction_result and extraction_result.success and pipeline_result and pipeline_result.checker_passed and objective_ok)
        if case_ok:
            end_to_end_success += 1
            by_type[expected_type]["end_to_end_success"] += 1

        case_results.append(
            {
                "case_id": case_id,
                "problem_type": expected_type,
                "router_problem_type": route_result.problem_type.value,
                "spec_success": bool(extraction_result and extraction_result.success),
                "solver_status": pipeline_result.solver_status if pipeline_result else None,
                "objective_value": pipeline_result.objective_value if pipeline_result else None,
                "checker_passed": bool(pipeline_result and pipeline_result.checker_passed),
                "end_to_end_passed": case_ok,
                "prompt_version": prompt_version,
                "difficulty": case.get("difficulty"),
            }
        )

    total = len(cases)
    metrics: dict[str, Any] = {
        "total": total,
        "provider": "mock",
        "mock": True,
        "model": "mock-extractor",
        "prompt_version": prompt_version,
        "difficulty": difficulty,
        "router_correct": router_correct,
        "router_accuracy": router_correct / total if total else 0.0,
        "spec_success": spec_success,
        "spec_pass_rate": spec_success / total if total else 0.0,
        "execution_success": execution_success,
        "execution_pass_rate": execution_success / total if total else 0.0,
        "checker_success": checker_success,
        "checker_pass_rate": checker_success / total if total else 0.0,
        "end_to_end_success": end_to_end_success,
        "end_to_end_pass_rate": end_to_end_success / total if total else 0.0,
        "avg_runtime_sec": sum(runtimes) / len(runtimes) if runtimes else 0.0,
        "by_type": dict(by_type),
        "failure_breakdown": dict(failure_breakdown),
        "failures": failures,
        "case_results": case_results,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metrics


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _failure_stage(error: str | None, validation_errors: list[str], pipeline_error: str | None = None) -> str:
    text = " ".join(part for part in [error, pipeline_error, " ".join(validation_errors)] if part)
    lower = text.lower()
    if "empty content" in lower or "empty response" in lower:
        return "empty_response"
    if "invalid json" in lower or "json object" in lower:
        return "json_parse_error"
    if validation_errors or "schema validation" in lower:
        return "schema_validation_error"
    if "llm client failed" in lower or "deepseek api" in lower:
        return "api_error"
    if pipeline_error:
        return "pipeline_error"
    return "api_error" if error else "unknown"


REQUIRED_MISSING_MARKERS: dict[str, tuple[str, ...]] = {
    ProblemType.PRODUCTION.value: (
        "products",
        "profit",
        "resources",
        "capacity",
        "consumption",
        "labor",
        "material",
    ),
    ProblemType.ASSIGNMENT.value: (
        "employees",
        "workers",
        "tasks",
        "capacity",
        "costs",
        "cost",
        "cost_matrix",
    ),
    ProblemType.JOBSHOP.value: (
        "machines",
        "jobs",
        "operations",
        "machine",
        "duration",
        "processing_time",
    ),
    ProblemType.VRP.value: (
        "depot",
        "vehicles",
        "vehicle",
        "capacity",
        "customers",
        "demand",
        "distance_matrix",
        "distance",
    ),
}


def _missing_required_fields(problem_type: str, missing_fields: list[str]) -> list[str]:
    markers = REQUIRED_MISSING_MARKERS.get(problem_type, ())
    required: list[str] = []
    for field in missing_fields:
        normalized = str(field).lower()
        if any(marker.lower() in normalized for marker in markers):
            required.append(str(field))
    return required


def evaluate_deepseek_extractor_cases(
    path: Path | None,
    output_dir: Path,
    timeout_sec: int = 10,
    model: str | None = None,
    client_factory: Callable[[dict[str, Any]], LLMClient] | None = None,
    prompt_version: str = "v2",
    difficulty: str = "easy",
) -> dict[str, Any]:
    cases = load_extractor_cases(path, difficulty=difficulty)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if client_factory is None:
        shared_client = DeepSeekClient(model=model)

        def client_factory(case: dict[str, Any]) -> LLMClient:
            return shared_client

    router_correct = 0
    spec_success = 0
    execution_success = 0
    checker_success = 0
    objective_match = 0
    end_to_end_success = 0
    runtimes: list[float] = []
    failures: list[dict[str, Any]] = []
    failure_breakdown: Counter[str] = Counter()
    by_type: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "end_to_end_success": 0})
    case_results: list[dict[str, Any]] = []

    def add_failure(case_id: str, stage: str, message: str) -> None:
        failure_breakdown[stage] += 1
        failures.append({"case_id": case_id, "failure_stage": stage, "message": message})

    for case in cases:
        case_id = str(case["case_id"])
        case_dir = output_dir / case_id
        if case_dir.exists():
            shutil.rmtree(case_dir)
        case_dir.mkdir(parents=True, exist_ok=True)
        expected_type = str(case["expected_problem_type"])
        by_type[expected_type]["total"] += 1

        route_result = route_text(str(case["text"]))
        router_ok = route_result.problem_type.value == expected_type
        if router_ok:
            router_correct += 1
        else:
            add_failure(case_id, "router_mismatch", f"expected {expected_type}, got {route_result.problem_type.value}")

        extraction_result = None
        pipeline_result = None
        main_failure_stage: str | None = None
        main_failure_message: str | None = None

        try:
            extraction_result = extract_problem_spec(
                str(case["text"]),
                problem_type=route_result.problem_type,
                client=client_factory(case),
                prompt_version=prompt_version,
            )
        except Exception as exc:
            main_failure_stage = "api_error"
            main_failure_message = str(exc)
            add_failure(case_id, main_failure_stage, main_failure_message)

        if extraction_result is not None:
            (case_dir / "raw_response.txt").write_text(extraction_result.raw_response or "", encoding="utf-8")
            if extraction_result.spec_dict is not None:
                _write_json(case_dir / "parsed_spec.json", extraction_result.spec_dict)

            extractor_payload = {
                "case_id": case_id,
                "text": case["text"],
                "expected_problem_type": expected_type,
                "routed_problem_type": route_result.problem_type.value,
                "router_correct": router_ok,
                "extractor_success": extraction_result.success,
                "provider": extraction_result.provider,
                "model": extraction_result.model,
                "problem_id": extraction_result.spec_dict.get("problem_id") if extraction_result.spec_dict else None,
                "validation_errors": extraction_result.validation_errors,
                "error": extraction_result.error,
                "prompt_version": extraction_result.prompt_version,
                "difficulty": case.get("difficulty"),
            }
            _write_json(case_dir / "extractor_result.json", extractor_payload)

            if extraction_result.success:
                spec_success += 1
                required_missing = _missing_required_fields(
                    expected_type,
                    list(getattr(extraction_result.spec, "missing_fields", []) or []),
                )
                if required_missing:
                    stage = "missing_required_fields"
                    message = "missing required fields: " + ", ".join(required_missing)
                    add_failure(case_id, stage, message)
                    main_failure_stage = main_failure_stage or stage
                    main_failure_message = main_failure_message or message
                else:
                    pipeline_result = run_problem_spec(
                        extraction_result.spec,
                        case_dir,
                        timeout_sec=timeout_sec,
                    )
                    if pipeline_result.runtime_sec is not None:
                        runtimes.append(pipeline_result.runtime_sec)
                    if (
                        pipeline_result.returncode == 0
                        and not pipeline_result.timed_out
                        and pipeline_result.solver_status is not None
                    ):
                        execution_success += 1
                    else:
                        stage = "pipeline_error"
                        message = pipeline_result.error or "pipeline execution failed"
                        add_failure(case_id, stage, message)
                        main_failure_stage = main_failure_stage or stage
                        main_failure_message = main_failure_message or message
                    if pipeline_result.checker_passed:
                        checker_success += 1
                    else:
                        stage = "checker_failed"
                        message = pipeline_result.error or "checker failed"
                        add_failure(case_id, stage, message)
                        main_failure_stage = main_failure_stage or stage
                        main_failure_message = main_failure_message or message
            else:
                stage = _failure_stage(extraction_result.error, extraction_result.validation_errors)
                message = extraction_result.error or "extractor failed"
                add_failure(case_id, stage, message)
                main_failure_stage = main_failure_stage or stage
                main_failure_message = main_failure_message or message

        objective_ok = False
        if pipeline_result is not None:
            objective_ok = _objective_matches(
                pipeline_result.objective_value,
                case["expected_objective_value"],
            )
            if objective_ok:
                objective_match += 1
            else:
                stage = "objective_mismatch"
                message = f"expected {case['expected_objective_value']}, got {pipeline_result.objective_value}"
                add_failure(case_id, stage, message)
                main_failure_stage = main_failure_stage or stage
                main_failure_message = main_failure_message or message

        case_ok = bool(
            router_ok
            and extraction_result
            and extraction_result.success
            and pipeline_result
            and pipeline_result.checker_passed
            and objective_ok
        )
        if case_ok:
            end_to_end_success += 1
            by_type[expected_type]["end_to_end_success"] += 1
        elif main_failure_stage:
            _write_json(
                case_dir / "failure.json",
                {
                    "case_id": case_id,
                    "failure_stage": main_failure_stage,
                    "message": main_failure_message,
                    "raw_response_path": str(case_dir / "raw_response.txt"),
                },
            )

        case_results.append(
            {
                "case_id": case_id,
                "problem_type": expected_type,
                "router_problem_type": route_result.problem_type.value,
                "spec_success": bool(extraction_result and extraction_result.success),
                "solver_status": pipeline_result.solver_status if pipeline_result else None,
                "objective_value": pipeline_result.objective_value if pipeline_result else None,
                "checker_passed": bool(pipeline_result and pipeline_result.checker_passed),
                "objective_matched": objective_ok,
                "end_to_end_passed": case_ok,
                "status": "OK" if case_ok else (main_failure_stage or "unknown"),
                "prompt_version": prompt_version,
                "difficulty": case.get("difficulty"),
            }
        )

    total = len(cases)
    summary_path = output_dir / "summary.json"
    model_name = None
    for result in case_results:
        if result.get("model"):
            model_name = result["model"]
            break
    metrics: dict[str, Any] = {
        "total": total,
        "provider": "deepseek",
        "mock": False,
        "model": model_name or model or DeepSeekClient.DEFAULT_MODEL,
        "prompt_version": prompt_version,
        "difficulty": difficulty,
        "router_correct": router_correct,
        "router_accuracy": router_correct / total if total else 0.0,
        "spec_success": spec_success,
        "spec_pass_rate": spec_success / total if total else 0.0,
        "execution_success": execution_success,
        "execution_pass_rate": execution_success / total if total else 0.0,
        "checker_success": checker_success,
        "checker_pass_rate": checker_success / total if total else 0.0,
        "objective_match": objective_match,
        "objective_match_rate": objective_match / total if total else 0.0,
        "end_to_end_success": end_to_end_success,
        "end_to_end_pass_rate": end_to_end_success / total if total else 0.0,
        "avg_runtime_sec": sum(runtimes) / len(runtimes) if runtimes else 0.0,
        "by_type": dict(by_type),
        "failure_breakdown": dict(failure_breakdown),
        "failures": failures,
        "case_results": case_results,
        "summary_path": str(summary_path),
    }
    _write_json(summary_path, metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate extractor easy cases.")
    parser.add_argument("--mock", action="store_true", help="Run the mock extractor evaluation.")
    parser.add_argument("--provider", choices=["mock", "deepseek"], default=None)
    parser.add_argument("--cases", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--timeout-sec", type=int, default=10)
    parser.add_argument("--model", default=None)
    parser.add_argument("--prompt-version", default="v2")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard", "all"], default="easy")
    parser.add_argument("--check-env", action="store_true")
    args = parser.parse_args(argv)

    if args.check_env:
        print(f"DEEPSEEK_API_KEY_SOURCE={get_deepseek_api_key_source()}")
        return 0

    provider = "mock" if args.mock else (args.provider or "deepseek")
    output_dir = args.output_dir
    if output_dir is None:
        base_dir = "deepseek_extractor_eval" if provider == "deepseek" else "mock_extractor_eval"
        output_dir = Path("outputs") / base_dir / args.difficulty

    try:
        if provider == "deepseek":
            metrics = evaluate_deepseek_extractor_cases(
                args.cases,
                output_dir,
                timeout_sec=args.timeout_sec,
                model=args.model,
                prompt_version=args.prompt_version,
                difficulty=args.difficulty,
            )
            print(json.dumps(metrics, ensure_ascii=False, indent=2))
            return 0

        metrics = evaluate_mock_extractor_cases(
            args.cases,
            output_dir,
            timeout_sec=args.timeout_sec,
            prompt_version=args.prompt_version,
            difficulty=args.difficulty,
        )
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        return 0 if metrics["end_to_end_pass_rate"] == 1.0 else 1
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
