from __future__ import annotations

from copy import deepcopy
from typing import Any

from nl2opt.schemas import ProblemType


def _as_number(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and stripped.replace(".", "", 1).isdigit():
            number = float(stripped)
            return int(number) if number.is_integer() else number
    return value


def _normalize_sense(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    normalized = value.strip().lower()
    if "max" in normalized or "最大" in normalized:
        return "maximize"
    if "min" in normalized or "最小" in normalized:
        return "minimize"
    return value


def _normalize_objective_name(problem_type: ProblemType, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    normalized = value.strip().lower()
    if problem_type is ProblemType.PRODUCTION:
        if any(token in normalized for token in ("profit", "利润", "收益")):
            return "profit"
    if problem_type is ProblemType.ASSIGNMENT:
        if any(token in normalized for token in ("cost", "成本", "费用")):
            return "cost"
    if problem_type is ProblemType.JOBSHOP:
        if any(token in normalized for token in ("makespan", "completion", "完工")):
            return "makespan"
    if problem_type is ProblemType.VRP:
        if any(token in normalized for token in ("distance", "route", "travel", "距离", "路程")):
            return "distance"
    return value


def _normalize_objective(problem_type: ProblemType, data: dict[str, Any]) -> None:
    objective = data.get("objective")
    if not isinstance(objective, dict):
        return
    if "sense" in objective:
        objective["sense"] = _normalize_sense(objective["sense"])
    if "name" in objective:
        objective["name"] = _normalize_objective_name(problem_type, objective["name"])


def _normalize_numeric_mapping(mapping: Any) -> Any:
    if isinstance(mapping, dict):
        return {
            key: _normalize_numeric_mapping(value)
            for key, value in mapping.items()
        }
    if isinstance(mapping, list):
        return [_normalize_numeric_mapping(item) for item in mapping]
    return _as_number(mapping)


def _normalize_production(data: dict[str, Any]) -> None:
    for product in data.get("products", []):
        if isinstance(product, dict) and "profit" in product:
            product["profit"] = _as_number(product["profit"])
    for resource in data.get("resources", []):
        if isinstance(resource, dict) and "capacity" in resource:
            resource["capacity"] = _as_number(resource["capacity"])
    if "resource_consumption" in data and "consumption" not in data:
        data["consumption"] = data.pop("resource_consumption")
    if "consumption_matrix" in data and "consumption" not in data:
        data["consumption"] = data.pop("consumption_matrix")
    if "consumption" in data:
        data["consumption"] = _normalize_numeric_mapping(data["consumption"])


def _normalize_assignment(data: dict[str, Any]) -> None:
    if "workers" in data and "employees" not in data:
        data["employees"] = data.pop("workers")
    if "cost_matrix" in data and "costs" not in data:
        data["costs"] = data.pop("cost_matrix")
    for employee in data.get("employees", []):
        if isinstance(employee, dict) and "capacity" in employee:
            employee["capacity"] = _as_number(employee["capacity"])
    if "costs" in data:
        data["costs"] = _normalize_numeric_mapping(data["costs"])


def _normalize_jobshop(data: dict[str, Any]) -> None:
    for job in data.get("jobs", []):
        if not isinstance(job, dict):
            continue
        for operation in job.get("operations", []):
            if not isinstance(operation, dict):
                continue
            if "machine_id" in operation and "machine" not in operation:
                operation["machine"] = operation.pop("machine_id")
            if "machine_name" in operation and "machine" not in operation:
                operation["machine"] = operation.pop("machine_name")
            if "processing_time" in operation and "duration" not in operation:
                operation["duration"] = operation.pop("processing_time")
            if "duration_time" in operation and "duration" not in operation:
                operation["duration"] = operation.pop("duration_time")
            if "time" in operation and "duration" not in operation:
                operation["duration"] = operation.pop("time")
            if "duration" in operation:
                operation["duration"] = _as_number(operation["duration"])


def _normalize_vrp(data: dict[str, Any]) -> None:
    if "distances" in data and "distance_matrix" not in data:
        data["distance_matrix"] = data.pop("distances")
    if "customers" in data:
        for customer in data["customers"]:
            if isinstance(customer, dict) and "demand" in customer:
                customer["demand"] = _as_number(customer["demand"])
    if "vehicles" in data:
        for vehicle in data["vehicles"]:
            if isinstance(vehicle, dict) and "capacity" in vehicle:
                vehicle["capacity"] = _as_number(vehicle["capacity"])
    if "distance_matrix" in data:
        data["distance_matrix"] = _normalize_numeric_mapping(data["distance_matrix"])


def _normalize_generic_lp(data: dict[str, Any]) -> None:
    for variable in data.get("variables", []):
        if not isinstance(variable, dict):
            continue
        for field_name in ("lb", "ub"):
            if field_name in variable and variable[field_name] is not None:
                variable[field_name] = _as_number(variable[field_name])

    objective = data.get("objective")
    if isinstance(objective, dict):
        for term in objective.get("terms", []):
            if isinstance(term, dict) and "coef" in term:
                term["coef"] = _as_number(term["coef"])

    for constraint in data.get("constraints", []):
        if not isinstance(constraint, dict):
            continue
        if "rhs" in constraint:
            constraint["rhs"] = _as_number(constraint["rhs"])
        for term in constraint.get("terms", []):
            if isinstance(term, dict) and "coef" in term:
                term["coef"] = _as_number(term["coef"])


def normalize_spec_dict(problem_type: ProblemType, data: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(data)
    if "problem_type" in normalized and isinstance(normalized["problem_type"], str):
        normalized["problem_type"] = normalized["problem_type"].strip().lower()

    _normalize_objective(problem_type, normalized)
    if problem_type is ProblemType.PRODUCTION:
        _normalize_production(normalized)
    elif problem_type is ProblemType.ASSIGNMENT:
        _normalize_assignment(normalized)
    elif problem_type is ProblemType.JOBSHOP:
        _normalize_jobshop(normalized)
    elif problem_type is ProblemType.VRP:
        _normalize_vrp(normalized)
    elif problem_type is ProblemType.GENERIC_LP_MILP:
        _normalize_generic_lp(normalized)
    return normalized
