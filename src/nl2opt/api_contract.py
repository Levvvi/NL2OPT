"""Small public API contract; user input never includes code or raw ProblemSpecs."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from typing import Any
from uuid import uuid4

from nl2opt.schemas import ProductionProblemSpec

MAX_BODY_BYTES = 16 * 1024
MAX_TEXT_LENGTH = 2000
ALLOWED_TYPES = {"production", "assignment", "jobshop", "vrp"}


class ApiError(Exception):
    def __init__(self, code: str, message: str, stage: str = "input", http_status: int = 400):
        super().__init__(message)
        self.code, self.message, self.stage, self.http_status = code, message, stage, http_status


def envelope(mode: str, source: str, revision: str = "unversioned") -> dict[str, Any]:
    try:
        solver_version = version("ortools")
    except PackageNotFoundError:
        solver_version = "unavailable"
    return {
        "run_id": uuid4().hex,
        "mode": mode,
        "status": "failed",
        "stage": "input",
        "problem_spec": None,
        "solver_result": None,
        "checker_report": None,
        "diagnostics": {},
        "provenance": {
            "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "revision": revision,
            "ortools_version": solver_version,
            "checker_proves": "feasibility_and_objective_consistency_for_extracted_spec",
            "semantic_equivalence_proven": False,
            "independent_optimality_proven": False,
        },
    }


def fail(payload: dict[str, Any], error: ApiError) -> tuple[int, dict[str, Any]]:
    payload.update(status="failed", stage=error.stage,
                   error={"code": error.code, "message": error.message, "stage": error.stage})
    return error.http_status, payload


def _keys(value: Any, required: set[str], optional: set[str] | None = None) -> None:
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - (optional or set()):
        raise ApiError("INVALID_INPUT", "请求字段不完整或包含不支持的字段。")


def finite_number(value: Any, lower: float, upper: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ApiError("INVALID_INPUT", "数值字段必须使用 JSON 数字。")
    # Compare the range first: extremely large JSON integers must be rejected
    # without overflowing their conversion to a platform float.
    if not lower <= value <= upper or not math.isfinite(value):
        raise ApiError("INVALID_INPUT", f"数值必须为 {lower:g} 到 {upper:g} 之间的有限值。")
    return float(value)


def validate_request(data: Any, operation: str) -> dict[str, Any]:
    if operation == "check":
        _keys(data, {"parameters", "quantities"}, {"objective_value"})
        _keys(data["quantities"], {"A", "B"})
        for value in data["quantities"].values():
            finite_number(value, -500, 500)
        if "objective_value" in data:
            finite_number(data["objective_value"], -1_000_000, 1_000_000)
    elif operation == "solve" and isinstance(data, dict) and data.get("mode") == "text":
        _keys(data, {"mode", "text"})
        if not isinstance(data["text"], str) or not 1 <= len(data["text"].strip()) <= MAX_TEXT_LENGTH:
            raise ApiError("INVALID_INPUT", "请输入 1 至 2000 字的优化问题。")
        return data
    else:
        _keys(data, {"mode", "parameters"})
        if data["mode"] != "production":
            raise ApiError("INVALID_MODE", "仅支持 production 和 text 模式。")
    _keys(data["parameters"], {"labor_capacity", "material_capacity"})
    for value in data["parameters"].values():
        number = finite_number(value, 1, 200)
        if not number.is_integer():
            raise ApiError("INVALID_INPUT", "资源容量必须为 1 至 200 的整数。")
    return data


def production_spec(parameters: dict[str, Any]) -> ProductionProblemSpec:
    return ProductionProblemSpec.model_validate({
        "problem_id": "online_production", "problem_type": "production",
        "objective": {"sense": "maximize", "name": "profit"},
        "products": [{"name": "A", "profit": 40}, {"name": "B", "profit": 30}],
        "resources": [{"name": "labor", "capacity": parameters["labor_capacity"]},
                      {"name": "material", "capacity": parameters["material_capacity"]}],
        "consumption": {"A": {"labor": 2, "material": 1}, "B": {"labor": 1, "material": 2}},
    })


def check_instance_limits(spec: Any) -> None:
    """Whitelist small demos, after schema validation and before code generation."""
    data = spec.model_dump(mode="json")
    kind = data.get("problem_type")
    if kind not in ALLOWED_TYPES:
        raise ApiError("UNSUPPORTED_TYPE", "在线演示支持生产、指派、作业车间和车辆路径四类问题。", "router", 422)
    sizes = {
        "production": [("products", 10), ("resources", 10)],
        "assignment": [("employees", 10), ("tasks", 10)],
        "jobshop": [("machines", 5), ("jobs", 5)],
        "vrp": [("vehicles", 3), ("customers", 8)],
    }
    if any(len(data[field]) > limit for field, limit in sizes[kind]):
        raise ApiError("INSTANCE_TOO_LARGE", "实例超出演示规模限制，请缩小问题。", "schema", 422)
    if kind == "jobshop" and sum(len(job["operations"]) for job in data["jobs"]) > 20:
        raise ApiError("INSTANCE_TOO_LARGE", "在线作业车间最多支持 20 道工序。", "schema", 422)

    def visit(value: Any, depth: int = 0) -> None:
        if depth > 8:
            raise ApiError("INSTANCE_TOO_LARGE", "数据层级超出限制。", "schema", 422)
        if isinstance(value, dict):
            if len(value) > 100:
                raise ApiError("INSTANCE_TOO_LARGE", "数据规模超出限制。", "schema", 422)
            for key, item in value.items():
                if len(str(key)) > 80:
                    raise ApiError("INSTANCE_TOO_LARGE", "对象名称过长。", "schema", 422)
                visit(item, depth + 1)
        elif isinstance(value, list):
            if len(value) > 100:
                raise ApiError("INSTANCE_TOO_LARGE", "数据规模超出限制。", "schema", 422)
            for item in value:
                visit(item, depth + 1)
        elif isinstance(value, str) and len(value) > 2000:
            raise ApiError("INSTANCE_TOO_LARGE", "文本字段过长。", "schema", 422)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            if not math.isfinite(value) or abs(value) > 10_000:
                raise ApiError("INVALID_SPEC_NUMBER", "模型数值必须有限且绝对值不超过 10000。", "schema", 422)
    visit(data)
