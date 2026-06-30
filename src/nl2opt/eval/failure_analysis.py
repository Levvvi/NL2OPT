from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


NO_LIVE_DATA = "no_live_data"
ROUTER_MISMATCH = "router_mismatch"
API_ERROR = "api_error"
EMPTY_RESPONSE = "empty_response"
JSON_PARSE_ERROR = "json_parse_error"
SCHEMA_VALIDATION_ERROR = "schema_validation_error"
PIPELINE_ERROR = "pipeline_error"
CHECKER_FAILED = "checker_failed"
OBJECTIVE_MISMATCH = "objective_mismatch"
MISSING_OUTPUT = "missing_output"
MISSING_REQUIRED_FIELDS = "missing_required_fields"
UNKNOWN_FAILURE = "unknown_failure"
SUCCESS = "success"

FAILURE_TYPES = {
    NO_LIVE_DATA,
    ROUTER_MISMATCH,
    API_ERROR,
    EMPTY_RESPONSE,
    JSON_PARSE_ERROR,
    SCHEMA_VALIDATION_ERROR,
    PIPELINE_ERROR,
    CHECKER_FAILED,
    OBJECTIVE_MISMATCH,
    MISSING_OUTPUT,
    MISSING_REQUIRED_FIELDS,
    UNKNOWN_FAILURE,
}

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EVAL_DIR = Path("outputs") / "deepseek_extractor_eval"
DEFAULT_CASES_PATH = PROJECT_ROOT / "src" / "nl2opt" / "eval" / "extractor_cases_easy.jsonl"
DEFAULT_MEDIUM_CASES_PATH = PROJECT_ROOT / "src" / "nl2opt" / "eval" / "extractor_cases_medium.jsonl"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "deepseek_easy_failure_analysis.md"
DEFAULT_HARD_CASES_PATH = PROJECT_ROOT / "src" / "nl2opt" / "eval" / "extractor_cases_hard.jsonl"
DEFAULT_ALL_CASES_PATHS = [DEFAULT_CASES_PATH, DEFAULT_MEDIUM_CASES_PATH, DEFAULT_HARD_CASES_PATH]


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _read_cases(path: Path | list[Path] | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}

    paths = path if isinstance(path, list) else [Path(path)]
    cases: dict[str, dict[str, Any]] = {}
    for case_path in paths:
        if not case_path.exists():
            continue
        for line in case_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("case_id"):
                cases[str(data["case_id"])] = data
    return cases


def _raw_response_info(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {"path": str(path), "summary": ""}
    compact = " ".join(text.strip().split())
    return {"path": str(path), "summary": compact[:240]}


def load_case_artifacts(eval_dir: Path) -> list[dict[str, Any]]:
    eval_dir = Path(eval_dir)
    if not eval_dir.exists():
        return []

    artifacts: list[dict[str, Any]] = []
    for case_dir in sorted(path for path in eval_dir.iterdir() if path.is_dir()):
        case_id = case_dir.name
        artifacts.append(
            {
                "case_id": case_id,
                "case_dir": str(case_dir),
                "extractor_result": _read_json(case_dir / "extractor_result.json"),
                "pipeline_report": _read_json(case_dir / "pipeline_report.json"),
                "failure": _read_json(case_dir / "failure.json"),
                "parsed_spec": _read_json(case_dir / "parsed_spec.json"),
                "raw_response": _raw_response_info(case_dir / "raw_response.txt"),
            }
        )
    return artifacts


def _objective_matches(actual: Any, expected: Any, tolerance: float = 1e-6) -> bool | None:
    if actual is None or expected is None:
        return None
    try:
        return abs(float(actual) - float(expected)) <= tolerance
    except (TypeError, ValueError):
        return False


def _suggested_action(stage: str) -> str:
    actions = {
        NO_LIVE_DATA: "Run DeepSeek eval first, then re-run failure analysis.",
        ROUTER_MISMATCH: "Inspect router keywords or override problem_type before extraction.",
        API_ERROR: "Check API key, model, base_url, rate limits, and raw error message.",
        EMPTY_RESPONSE: "Retry the request and consider lowering max_tokens pressure or simplifying prompt.",
        JSON_PARSE_ERROR: "Tighten JSON-only instructions and inspect raw_response.txt.",
        SCHEMA_VALIDATION_ERROR: "Tune schema-specific prompt hints for missing or inconsistent fields.",
        PIPELINE_ERROR: "Inspect generated pipeline_report.json and solver stderr.",
        CHECKER_FAILED: "Compare parsed_spec and checker violations; update extraction hints, not checker logic.",
        OBJECTIVE_MISMATCH: "Inspect numeric extraction and objective sense/name consistency.",
        MISSING_OUTPUT: "Check whether expected artifact files were generated for this case.",
        MISSING_REQUIRED_FIELDS: "Fix the input case text or extractor prompt so required fields are provided before solver execution.",
        UNKNOWN_FAILURE: "Inspect case artifacts manually and add a more specific failure rule.",
        SUCCESS: "No action needed.",
    }
    return actions.get(stage, actions[UNKNOWN_FAILURE])


def _classify_from_error(error: str | None, validation_errors: list[Any]) -> str:
    text = " ".join(str(part) for part in [error, *validation_errors] if part).lower()
    if "empty content" in text or "empty response" in text:
        return EMPTY_RESPONSE
    if "invalid json" in text or "json object" in text:
        return JSON_PARSE_ERROR
    if validation_errors or "schema validation" in text:
        return SCHEMA_VALIDATION_ERROR
    if "api" in text or "llm client" in text or "deepseek" in text:
        return API_ERROR
    return UNKNOWN_FAILURE


def _case_from_summary_result(result: dict[str, Any]) -> dict[str, Any]:
    stage = SUCCESS if result.get("end_to_end_passed") else str(result.get("status") or UNKNOWN_FAILURE)
    return {
        "case_id": result.get("case_id"),
        "expected_problem_type": result.get("problem_type"),
        "routed_problem_type": result.get("router_problem_type"),
        "router_correct": result.get("router_problem_type") in (None, result.get("problem_type")),
        "extractor_success": result.get("spec_success"),
        "checker_passed": result.get("checker_passed"),
        "expected_objective_value": None,
        "objective_value": result.get("objective_value"),
        "objective_match": result.get("objective_matched"),
        "failure_stage": stage,
        "message": "" if stage == SUCCESS else str(result.get("status") or ""),
        "suggested_action": _suggested_action(stage),
    }


def _case_from_artifact(artifact: dict[str, Any], expected: dict[str, Any] | None) -> dict[str, Any]:
    extractor_result = artifact.get("extractor_result") or {}
    pipeline_report = artifact.get("pipeline_report") or {}
    failure = artifact.get("failure") or {}
    expected = expected or {}

    case_id = str(artifact.get("case_id") or expected.get("case_id") or extractor_result.get("case_id"))
    expected_type = extractor_result.get("expected_problem_type") or expected.get("expected_problem_type")
    routed_type = extractor_result.get("routed_problem_type")
    router_correct = extractor_result.get("router_correct")
    extractor_success = extractor_result.get("extractor_success")
    checker_passed = pipeline_report.get("checker_passed")
    expected_objective = expected.get("expected_objective_value")
    objective_value = pipeline_report.get("objective_value")
    objective_match = _objective_matches(objective_value, expected_objective)

    if failure.get("failure_stage"):
        stage = str(failure["failure_stage"])
        message = str(failure.get("message") or "")
    elif router_correct is False:
        stage = ROUTER_MISMATCH
        message = f"expected {expected_type}, got {routed_type}"
    elif extractor_success is False:
        stage = _classify_from_error(
            extractor_result.get("error"),
            extractor_result.get("validation_errors") or [],
        )
        message = str(extractor_result.get("error") or "; ".join(extractor_result.get("validation_errors") or []))
    elif pipeline_report.get("error"):
        stage = PIPELINE_ERROR
        message = str(pipeline_report.get("error"))
    elif checker_passed is False:
        stage = CHECKER_FAILED
        message = "; ".join(str(item) for item in pipeline_report.get("violations") or []) or "checker failed"
    elif objective_match is False:
        stage = OBJECTIVE_MISMATCH
        message = f"expected {expected_objective}, got {objective_value}"
    elif extractor_success and checker_passed and objective_match is not False:
        stage = SUCCESS
        message = ""
    else:
        stage = MISSING_OUTPUT
        message = "missing one or more expected case artifacts"

    return {
        "case_id": case_id,
        "expected_problem_type": expected_type,
        "routed_problem_type": routed_type,
        "router_correct": router_correct,
        "extractor_success": extractor_success,
        "checker_passed": checker_passed,
        "expected_objective_value": expected_objective,
        "objective_value": objective_value,
        "objective_match": objective_match,
        "failure_stage": stage,
        "message": message,
        "suggested_action": _suggested_action(stage),
        "raw_response_path": (artifact.get("raw_response") or {}).get("path"),
        "raw_response_summary": (artifact.get("raw_response") or {}).get("summary"),
    }


def _no_live_data_summary(cases_path: Path | None = None) -> dict[str, Any]:
    cases = _read_cases(cases_path)
    return {
        "status": NO_LIVE_DATA,
        "total": len(cases),
        "completed_cases": 0,
        "end_to_end_success": 0,
        "end_to_end_pass_rate": 0.0,
        "failure_breakdown": {NO_LIVE_DATA: 1},
        "cases": [
            {
                "case_id": None,
                "failure_stage": NO_LIVE_DATA,
                "message": "No live DeepSeek eval outputs were found.",
                "suggested_action": _suggested_action(NO_LIVE_DATA),
            }
        ],
        "suggested_next_actions": [_suggested_action(NO_LIVE_DATA)],
    }


def analyze_deepseek_eval_outputs(
    eval_dir: Path,
    cases_path: Path | list[Path] | None = None,
) -> dict[str, Any]:
    eval_dir = Path(eval_dir)
    if not eval_dir.exists():
        return _no_live_data_summary(cases_path)

    cases_by_id = _read_cases(cases_path)
    artifacts = {artifact["case_id"]: artifact for artifact in load_case_artifacts(eval_dir)}
    summary_json = _read_json(eval_dir / "summary.json") or {}
    if not artifacts and not summary_json.get("case_results"):
        return _no_live_data_summary(cases_path)

    case_ids: set[str] = set(cases_by_id) | set(artifacts)
    if summary_json.get("case_results"):
        case_ids.update(str(item.get("case_id")) for item in summary_json["case_results"] if item.get("case_id"))

    if not case_ids:
        return _no_live_data_summary(cases_path)

    summary_case_by_id = {
        str(item.get("case_id")): item
        for item in summary_json.get("case_results", [])
        if isinstance(item, dict) and item.get("case_id")
    }

    analyzed_cases: list[dict[str, Any]] = []
    for case_id in sorted(case_ids):
        if case_id in artifacts:
            analyzed_cases.append(_case_from_artifact(artifacts[case_id], cases_by_id.get(case_id)))
        elif case_id in summary_case_by_id:
            analyzed_cases.append(_case_from_summary_result(summary_case_by_id[case_id]))
        else:
            expected = cases_by_id.get(case_id, {})
            analyzed_cases.append(
                {
                    "case_id": case_id,
                    "expected_problem_type": expected.get("expected_problem_type"),
                    "routed_problem_type": None,
                    "router_correct": None,
                    "extractor_success": None,
                    "checker_passed": None,
                    "expected_objective_value": expected.get("expected_objective_value"),
                    "objective_value": None,
                    "objective_match": None,
                    "failure_stage": MISSING_OUTPUT,
                    "message": "missing case output directory",
                    "suggested_action": _suggested_action(MISSING_OUTPUT),
                }
            )

    total = int(summary_json.get("total") or len(analyzed_cases))
    completed_cases = sum(1 for case in analyzed_cases if case["failure_stage"] != MISSING_OUTPUT)
    end_to_end_success = sum(1 for case in analyzed_cases if case["failure_stage"] == SUCCESS)
    failure_breakdown = Counter(
        case["failure_stage"]
        for case in analyzed_cases
        if case["failure_stage"] != SUCCESS
    )
    suggested_next_actions = []
    for case in analyzed_cases:
        action = case["suggested_action"]
        if case["failure_stage"] != SUCCESS and action not in suggested_next_actions:
            suggested_next_actions.append(action)

    return {
        "status": "ok",
        "total": total,
        "completed_cases": completed_cases,
        "end_to_end_success": end_to_end_success,
        "end_to_end_pass_rate": end_to_end_success / total if total else 0.0,
        "failure_breakdown": dict(failure_breakdown),
        "cases": analyzed_cases,
        "suggested_next_actions": suggested_next_actions,
    }


def write_failure_report(
    summary: dict[str, Any],
    report_path: Path,
) -> Path:
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# DeepSeek Extractor Failure Analysis",
        "",
        "## Status",
    ]
    if summary.get("status") == NO_LIVE_DATA:
        lines.append("No live DeepSeek eval outputs were found. Do not treat mock pass rates as live DeepSeek metrics.")
    else:
        lines.append("Analysis generated from the current DeepSeek eval artifacts.")

    lines.extend(
        [
            "",
            "## Metrics",
            f"- total: {summary.get('total', 0)}",
            f"- completed_cases: {summary.get('completed_cases', 0)}",
            f"- end_to_end_success: {summary.get('end_to_end_success', 0)}",
            f"- end_to_end_pass_rate: {summary.get('end_to_end_pass_rate', 0.0)}",
            "",
            "## Failure Breakdown",
        ]
    )
    breakdown = summary.get("failure_breakdown") or {}
    if breakdown:
        for stage, count in breakdown.items():
            lines.append(f"- {stage}: {count}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Per-case Analysis",
            "| case_id | type | stage | objective | message | suggested_action |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for case in summary.get("cases", []):
        objective = case.get("objective_value")
        expected = case.get("expected_objective_value")
        objective_text = "" if objective is None else str(objective)
        if expected is not None:
            objective_text = f"{objective_text} / expected {expected}".strip()
        lines.append(
            "| {case_id} | {type} | {stage} | {objective} | {message} | {action} |".format(
                case_id=case.get("case_id") or "",
                type=case.get("expected_problem_type") or "",
                stage=case.get("failure_stage") or "",
                objective=objective_text or "-",
                message=str(case.get("message") or "").replace("|", "\\|"),
                action=str(case.get("suggested_action") or "").replace("|", "\\|"),
            )
        )

    lines.extend(["", "## Suggested Next Actions"])
    actions = summary.get("suggested_next_actions") or []
    if actions:
        for action in actions:
            lines.append(f"- {action}")
    else:
        lines.append("- No immediate action.")

    lines.extend(
        [
            "",
            "## Re-run Commands",
            "```bash",
            "python -m nl2opt.eval.extractor_eval --provider deepseek --prompt-version v3",
            "python -m nl2opt.eval.failure_analysis --eval-dir outputs/deepseek_extractor_eval --report docs/deepseek_easy_failure_analysis.md",
            "```",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze DeepSeek easy-case eval outputs.")
    parser.add_argument("--eval-dir", type=Path, default=DEFAULT_EVAL_DIR)
    parser.add_argument("--cases", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args(argv)

    cases_path = args.cases
    if cases_path is None:
        if args.eval_dir.name == "medium":
            cases_path = DEFAULT_MEDIUM_CASES_PATH
        elif args.eval_dir.name == "hard":
            cases_path = DEFAULT_HARD_CASES_PATH
        elif args.eval_dir.name == "all":
            cases_path = DEFAULT_ALL_CASES_PATHS
        else:
            cases_path = DEFAULT_CASES_PATH

    summary = analyze_deepseek_eval_outputs(args.eval_dir, cases_path)
    report_path = write_failure_report(summary, args.report)
    payload = {
        "total": summary["total"],
        "completed_cases": summary["completed_cases"],
        "end_to_end_pass_rate": summary["end_to_end_pass_rate"],
        "failure_breakdown": summary["failure_breakdown"],
        "report_path": str(report_path),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
