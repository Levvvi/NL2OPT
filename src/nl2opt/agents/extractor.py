from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from nl2opt.agents.llm_client import DeepSeekClient, LLMClient, MockLLMClient
from nl2opt.agents.normalizer import normalize_spec_dict
from nl2opt.agents.prompts import build_extractor_prompt
from nl2opt.agents.router import route_text
from nl2opt.schemas import (
    AssignmentProblemSpec,
    GenericLpSpec,
    JobshopProblemSpec,
    ProblemType,
    ProductionProblemSpec,
    UnsupportedProblemSpec,
    VrpProblemSpec,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXTRACTOR_CASES_PATH = PROJECT_ROOT / "src" / "nl2opt" / "eval" / "extractor_cases_easy.jsonl"


@dataclass
class ExtractorResult:
    text: str
    problem_type: str
    success: bool
    spec: Any | None
    spec_dict: dict[str, Any] | None
    raw_response: str | None
    system_prompt: str | None
    user_prompt: str | None
    validation_errors: list[str]
    error: str | None
    provider: str | None
    model: str | None
    prompt_version: str


def _empty_result(
    *,
    text: str,
    problem_type: str,
    error: str,
    system_prompt: str | None = None,
    user_prompt: str | None = None,
    raw_response: str | None = None,
    validation_errors: list[str] | None = None,
    provider: str | None = None,
    model: str | None = None,
    prompt_version: str = "v2",
) -> ExtractorResult:
    return ExtractorResult(
        text=text,
        problem_type=problem_type,
        success=False,
        spec=None,
        spec_dict=None,
        raw_response=raw_response,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        validation_errors=validation_errors or [],
        error=error,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
    )


def _coerce_problem_type(problem_type: ProblemType | str) -> ProblemType:
    if isinstance(problem_type, ProblemType):
        return problem_type
    return ProblemType(str(problem_type))


def _problem_type_value(spec: Any, fallback: ProblemType) -> str:
    problem_type = getattr(spec, "problem_type", fallback)
    return problem_type.value if isinstance(problem_type, ProblemType) else str(problem_type)


def get_schema_model_for_problem_type(problem_type: ProblemType) -> type[BaseModel]:
    schema_by_type: dict[ProblemType, type[BaseModel]] = {
        ProblemType.PRODUCTION: ProductionProblemSpec,
        ProblemType.ASSIGNMENT: AssignmentProblemSpec,
        ProblemType.JOBSHOP: JobshopProblemSpec,
        ProblemType.VRP: VrpProblemSpec,
        ProblemType.GENERIC_LP_MILP: GenericLpSpec,
    }
    schema_model = schema_by_type.get(problem_type)
    if schema_model is None:
        raise ValueError(f"unsupported problem_type for extraction: {problem_type.value}")
    return schema_model


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON response: {exc.msg}") from exc

    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object")
    return data


def validate_spec_dict(
    problem_type: ProblemType,
    data: dict[str, Any],
) -> Any:
    normalized = normalize_spec_dict(problem_type, data)
    if (
        problem_type is ProblemType.GENERIC_LP_MILP
        and normalized.get("problem_type") == ProblemType.UNSUPPORTED.value
    ):
        return UnsupportedProblemSpec.model_validate(normalized)
    schema_model = get_schema_model_for_problem_type(problem_type)
    return schema_model.model_validate(normalized)


def get_schema_json_for_problem_type(problem_type: ProblemType) -> dict[str, Any]:
    if problem_type is ProblemType.GENERIC_LP_MILP:
        return TypeAdapter(GenericLpSpec | UnsupportedProblemSpec).json_schema()
    return get_schema_model_for_problem_type(problem_type).model_json_schema()


def _format_validation_errors(exc: ValidationError) -> list[str]:
    messages: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", ()))
        msg = str(error.get("msg", "validation error"))
        messages.append(f"{loc}: {msg}" if loc else msg)
    return messages or [str(exc)]


def extract_problem_spec(
    text: str,
    problem_type: ProblemType | str | None = None,
    client: LLMClient | None = None,
    prompt_version: str = "v2",
) -> ExtractorResult:
    if problem_type is None:
        resolved_type = route_text(text).problem_type
    else:
        try:
            resolved_type = _coerce_problem_type(problem_type)
        except ValueError as exc:
            return _empty_result(
                text=text,
                problem_type=str(problem_type),
                error=str(exc),
                prompt_version=prompt_version,
            )

    if resolved_type is ProblemType.UNSUPPORTED:
        return _empty_result(
            text=text,
            problem_type=ProblemType.UNSUPPORTED.value,
            error="unsupported problem_type; extractor only supports production, assignment, jobshop, vrp, and generic_lp_milp",
            prompt_version=prompt_version,
        )

    try:
        schema_model = get_schema_model_for_problem_type(resolved_type)
    except ValueError as exc:
        return _empty_result(
            text=text,
            problem_type=resolved_type.value,
            error=str(exc),
            prompt_version=prompt_version,
        )

    system_prompt, user_prompt = build_extractor_prompt(
        text,
        resolved_type,
        get_schema_json_for_problem_type(resolved_type),
        prompt_version=prompt_version,
    )

    if client is None:
        return _empty_result(
            text=text,
            problem_type=resolved_type.value,
            error="LLM client is required; no real API client is configured in this stage",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_version=prompt_version,
        )

    try:
        response = client.complete_json(system_prompt, user_prompt, temperature=0.0)
    except Exception as exc:
        return _empty_result(
            text=text,
            problem_type=resolved_type.value,
            error=f"LLM client failed: {exc}",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_version=prompt_version,
        )

    try:
        data = parse_json_object(response.content)
    except ValueError as exc:
        return _empty_result(
            text=text,
            problem_type=resolved_type.value,
            error=str(exc),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            raw_response=response.content,
            provider=response.provider,
            model=response.model,
            prompt_version=prompt_version,
        )

    try:
        spec = validate_spec_dict(resolved_type, data)
    except ValidationError as exc:
        return _empty_result(
            text=text,
            problem_type=resolved_type.value,
            error="schema validation failed",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            raw_response=response.content,
            validation_errors=_format_validation_errors(exc),
            provider=response.provider,
            model=response.model,
            prompt_version=prompt_version,
        )

    return ExtractorResult(
        text=text,
        problem_type=_problem_type_value(spec, resolved_type),
        success=True,
        spec=spec,
        spec_dict=spec.model_dump(mode="json"),
        raw_response=response.content,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        validation_errors=[],
        error=None,
        provider=response.provider,
        model=response.model,
        prompt_version=prompt_version,
    )


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


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


def _load_case(case_id: str) -> dict[str, Any]:
    for case in _load_jsonl(DEFAULT_EXTRACTOR_CASES_PATH):
        if case.get("case_id") == case_id:
            return case
    raise ValueError(f"unknown case_id: {case_id}")


def _result_payload(result: ExtractorResult) -> dict[str, Any]:
    problem_id = result.spec_dict.get("problem_id") if result.spec_dict else None
    return {
        "success": result.success,
        "problem_type": result.problem_type,
        "problem_id": problem_id,
        "provider": result.provider,
        "model": result.model,
        "validation_errors": result.validation_errors,
        "error": result.error,
        "prompt_version": result.prompt_version,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract a ProblemSpec from Chinese text.")
    parser.add_argument("text", nargs="?", help="中文优化问题文本")
    parser.add_argument("--problem-type", choices=[item.value for item in ProblemType], default=None)
    parser.add_argument("--mock-spec", type=Path, default=None)
    parser.add_argument("--case-id", default=None)
    parser.add_argument("--provider", choices=["mock", "deepseek"], default="mock")
    parser.add_argument("--model", default=None)
    parser.add_argument("--prompt-version", default="v2")
    args = parser.parse_args(argv)

    if args.case_id:
        try:
            case = _load_case(args.case_id)
            text = str(case["text"])
            problem_type = args.problem_type or str(case["expected_problem_type"])
            mock_spec = (
                _load_json(_resolve_project_path(case["gold_spec_path"]))
                if args.provider == "mock"
                else None
            )
        except Exception as exc:
            print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False, indent=2))
            return 1
    else:
        if not args.text:
            parser.print_usage()
            return 2
        text = args.text
        problem_type = args.problem_type
        mock_spec = None
        if args.provider == "mock":
            if args.mock_spec is None:
                parser.print_usage()
                return 2
            mock_spec = _load_json(args.mock_spec)

    try:
        if args.provider == "deepseek":
            client: LLMClient = DeepSeekClient(model=args.model)
        else:
            client = MockLLMClient(mock_spec or {})
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    result = extract_problem_spec(
        text,
        problem_type=problem_type,
        client=client,
        prompt_version=args.prompt_version,
    )
    print(json.dumps(_result_payload(result), ensure_ascii=False, indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
