"""One isolated API request. Invoked only by nl2opt.api, never by a shell."""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from nl2opt.agents.extractor import extract_problem_spec
from nl2opt.agents.llm_client import DeepSeekClient
from nl2opt.agents.router import route_text
from nl2opt.api_contract import ApiError, check_instance_limits, fail, production_spec, validate_request
from nl2opt.checkers.production_checker import check_production_solution
from nl2opt.pipeline import run_problem_spec
from nl2opt.runtime.runner import load_solver_result
from nl2opt.schemas import SolverResult


class MeteredClient:
    """Keep only safe usage metadata, not prompts, raw API output, or credentials."""
    def __init__(self, client: Any):
        self.client, self.usage, self.model = client, None, None
        configured_model = getattr(client, "model", None)
        self.requested_model = configured_model if isinstance(configured_model, str) else None
        self.model_identifier_source = "requested_model" if self.requested_model else "unavailable"

    def complete_json(self, *args: Any, **kwargs: Any) -> Any:
        response = self.client.complete_json(*args, **kwargs)
        self.usage = response.usage
        raw = getattr(response, "raw", None)
        reported_model = raw.get("model") if isinstance(raw, dict) else None
        if isinstance(reported_model, str) and reported_model.strip():
            self.model = reported_model
            self.model_identifier_source = "provider_response"
        else:
            # DeepSeekClient.response.model is the configured request alias,
            # not necessarily the provider's reported model identifier.
            self.model = self.requested_model or getattr(response, "model", None)
            self.model_identifier_source = "requested_model" if self.requested_model else "client_identifier"
        return response


def create_client(timeout_sec: float) -> MeteredClient:
    # API deployment reads secrets from the server environment only: no .env or
    # Streamlit config lookup. Disable SDK retries so the request budget is real.
    from openai import OpenAI
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise ApiError("MODEL_NOT_CONFIGURED", "服务器尚未配置真实模型，未执行模型调用。", "extraction", 503)
    base_url = os.environ.get("DEEPSEEK_BASE_URL") or DeepSeekClient.DEFAULT_BASE_URL
    model = os.environ.get("DEEPSEEK_MODEL") or DeepSeekClient.DEFAULT_MODEL
    sdk = OpenAI(api_key=key, base_url=base_url, timeout=timeout_sec, max_retries=0)
    return MeteredClient(DeepSeekClient(api_key=key, base_url=base_url, model=model,
                                     timeout_sec=timeout_sec, max_tokens=2048, openai_client=sdk))


def execute(request: dict[str, Any], output_dir: Path) -> tuple[int, dict[str, Any]]:
    payload = request["envelope"]
    started = time.monotonic()
    operation, data = request["operation"], request["data"]
    try:
        validate_request(data, operation)
        if operation == "check" or data["mode"] == "production":
            spec = production_spec(data["parameters"])
        else:
            route = route_text(data["text"])
            payload["diagnostics"]["router"] = route.model_dump(mode="json")
            if route.problem_type.value not in {"production", "assignment", "jobshop", "vrp"}:
                raise ApiError("UNSUPPORTED_TYPE", "在线演示支持生产、指派、作业车间和车辆路径四类问题。", "router", 422)
            client = create_client(request["model_timeout_sec"])
            extracted = extract_problem_spec(data["text"], problem_type=route.problem_type,
                                             client=client, prompt_version="v3")
            if client.usage:
                payload["diagnostics"]["token_usage"] = {
                    key: value for key, value in client.usage.items()
                    if key in {"prompt_tokens", "completion_tokens", "total_tokens"} and isinstance(value, int)
                }
            payload["provenance"].update(provider="deepseek", model=client.model or client.requested_model,
                                          requested_model=client.requested_model,
                                          model_identifier_source=client.model_identifier_source,
                                          prompt_version=extracted.prompt_version)
            if not extracted.success:
                # Never return extractor.error: SDK errors may contain hosts,
                # local paths, credentials, or raw model content.
                if extracted.error == "schema validation failed":
                    raise ApiError("SCHEMA_VALIDATION_FAILED", "模型输出未通过结构校验，未启动求解。", "schema", 422)
                if extracted.error and extracted.error.startswith("invalid JSON"):
                    raise ApiError("INVALID_MODEL_JSON", "模型输出不是有效 JSON，未启动求解。", "extraction", 422)
                raise ApiError("EXTRACTION_FAILED", "真实模型抽取失败，请稍后重试或检查服务器模型配置。", "extraction", 502)
            spec = extracted.spec
            if any(field.strip() == "problem_id" for field in spec.missing_fields):
                # Run identifiers are server metadata, not omitted mathematical
                # constraints. Resolve only this exact marker; all other missing
                # fields still reach the shared pipeline's blocking gate.
                spec = spec.model_copy(update={
                    "problem_id": payload["run_id"],
                    "missing_fields": [field for field in spec.missing_fields if field.strip() != "problem_id"],
                    "assumptions": [*spec.assumptions,
                                    "problem_id is generated by the API for this run; mathematical inputs are unchanged."],
                })
                payload["diagnostics"]["generated_metadata"] = {"problem_id": payload["run_id"]}
        check_instance_limits(spec)
        payload["problem_spec"] = spec.model_dump(mode="json")
        if operation == "check":
            objective = data.get("objective_value", 40 * data["quantities"]["A"] + 30 * data["quantities"]["B"])
            result = SolverResult(status="FEASIBLE", objective_value=objective,
                                  solution={"quantities": data["quantities"]}, runtime_sec=0,
                                  solver="user_candidate:not_a_solver_run")
            report = asdict(check_production_solution(spec, result))
            payload.update(solver_result=result.model_dump(mode="json"), checker_report=report)
            payload["diagnostics"]["solver_executed"] = False
            if not report["passed"]:
                raise ApiError("CHECKER_REJECTED", "候选方案未通过独立复核。", "checker", 422)
        else:
            result = run_problem_spec(spec, output_dir, timeout_sec=request["solver_timeout_sec"])
            payload["diagnostics"].update(solver_executed=result.code_path is not None,
                                          solver_runtime_sec=result.runtime_sec,
                                          timed_out=result.timed_out)
            payload["checker_report"] = getattr(result, "checker_report", None)
            # Load only parsed solver fields; paths, stdout/stderr and report file
            # locations are intentionally private to the server.
            if result.solution_path and Path(result.solution_path).exists():
                try:
                    solver_result = load_solver_result(Path(result.solution_path))
                    safe_result = solver_result.model_dump(mode="json")
                    safe_result["violations"] = []  # raw solver exceptions are not public diagnostics
                    payload["solver_result"] = safe_result
                except Exception:
                    pass
            if result.timed_out:
                raise ApiError("SOLVER_TIMEOUT", "求解超过演示时限，进程已终止。", "solver", 504)
            if getattr(result, "failure_stage", None) == "missing_required_fields":
                raise ApiError("MISSING_REQUIRED_FIELDS", "模型仍有缺失的必填信息，未启动求解。", "schema", 422)
            if not result.checker_passed:
                if payload["checker_report"] is not None:
                    raise ApiError("CHECKER_REJECTED", "求解结果未通过独立复核。", "checker", 422)
                raise ApiError("SOLVER_FAILED", "求解未能生成可复核的结果。", "solver", 422)
        payload.update(status="succeeded", stage="complete")
        return 200, payload
    except ApiError as exc:
        return fail(payload, exc)
    except Exception:
        return fail(payload, ApiError("INTERNAL_ERROR", "运行失败；服务器未返回有效结果。", "internal", 500))
    finally:
        payload["diagnostics"]["elapsed_ms"] = round((time.monotonic() - started) * 1000)


def main() -> None:
    request = json.loads(sys.stdin.read())
    status, payload = execute(request, Path(sys.argv[1]))
    print(json.dumps({"http_status": status, "payload": payload}, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
