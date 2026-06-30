from __future__ import annotations

from numbers import Real
from typing import Any

from nl2opt.checkers.base import CheckerReport
from nl2opt.schemas import JobshopProblemSpec, SolverResult, SolverStatus


def _is_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _empty_details(spec: JobshopProblemSpec) -> dict[str, Any]:
    return {
        "makespan": None,
        "machine_schedules": {machine.name: [] for machine in spec.machines},
        "job_completion_times": {job.name: None for job in spec.jobs},
    }


def check_jobshop_solution(
    spec: JobshopProblemSpec,
    result: SolverResult,
    tolerance: float = 1e-6,
) -> CheckerReport:
    violations: list[str] = []
    details = _empty_details(spec)

    if result.status not in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
        return CheckerReport(
            passed=False,
            violations=[f"solver status is not feasible: {result.status.value}"],
            computed_objective=None,
            details=details,
        )

    operations = result.solution.get("operations")
    if not isinstance(operations, list):
        return CheckerReport(
            passed=False,
            violations=["solution.operations is required for feasible results"],
            computed_objective=None,
            details=details,
        )

    expected_operations = {
        (job.name, op_index): operation
        for job in spec.jobs
        for op_index, operation in enumerate(job.operations)
    }
    machine_names = {machine.name for machine in spec.machines}
    job_names = {job.name for job in spec.jobs}
    seen: dict[tuple[str, int], dict[str, Any]] = {}

    for raw_operation in operations:
        if not isinstance(raw_operation, dict):
            violations.append("operation entry must be an object")
            continue

        job_name = raw_operation.get("job")
        op_index = raw_operation.get("op_index")
        machine_name = raw_operation.get("machine")
        start = raw_operation.get("start")
        end = raw_operation.get("end")
        duration = raw_operation.get("duration")

        if job_name not in job_names:
            violations.append(f"unknown job in solution: {job_name}")
            continue
        if not isinstance(op_index, int) or isinstance(op_index, bool):
            violations.append(f"invalid op_index for job {job_name}: {op_index}")
            continue

        key = (job_name, op_index)
        expected_operation = expected_operations.get(key)
        if expected_operation is None:
            violations.append(f"unknown op_index in solution: {job_name}-O{op_index}")
            continue
        if key in seen:
            violations.append(f"duplicate operation in solution: {job_name}-O{op_index}")
            continue

        if machine_name not in machine_names:
            violations.append(f"unknown machine in solution: {machine_name}")
            continue
        if machine_name != expected_operation.machine:
            violations.append(
                f"machine mismatch for {job_name}-O{op_index}: expected={expected_operation.machine}, got={machine_name}"
            )
            continue

        if not _is_number(start) or not _is_number(end):
            violations.append(f"start and end must be numeric for {job_name}-O{op_index}")
            continue
        if start < 0 or end < 0:
            violations.append(f"start and end must be non-negative for {job_name}-O{op_index}")
            continue
        if end < start:
            violations.append(f"end must be >= start for {job_name}-O{op_index}")
            continue

        actual_duration = end - start
        if abs(actual_duration - expected_operation.duration) > tolerance:
            violations.append(
                f"duration mismatch for {job_name}-O{op_index}: expected={expected_operation.duration}, got={actual_duration}"
            )
        if duration is not None and abs(float(duration) - expected_operation.duration) > tolerance:
            violations.append(
                f"reported duration mismatch for {job_name}-O{op_index}: expected={expected_operation.duration}, got={duration}"
            )

        normalized_operation = {
            "job": job_name,
            "op_index": op_index,
            "machine": machine_name,
            "start": float(start),
            "end": float(end),
            "duration": expected_operation.duration,
        }
        seen[key] = normalized_operation
        details["machine_schedules"][machine_name].append(normalized_operation)

    for key in expected_operations:
        if key not in seen:
            violations.append(f"missing operation in solution: {key[0]}-O{key[1]}")

    for job in spec.jobs:
        for op_index in range(len(job.operations) - 1):
            current_op = seen.get((job.name, op_index))
            next_op = seen.get((job.name, op_index + 1))
            if current_op is None or next_op is None:
                continue
            if current_op["end"] - next_op["start"] > tolerance:
                violations.append(
                    f"precedence violation for {job.name}: O{op_index} ends at {current_op['end']}, O{op_index + 1} starts at {next_op['start']}"
                )

    for machine_name, schedule in details["machine_schedules"].items():
        schedule.sort(key=lambda item: (item["start"], item["end"], item["job"], item["op_index"]))
        for first, second in zip(schedule, schedule[1:]):
            if first["end"] - second["start"] > tolerance:
                violations.append(
                    f"machine overlap on {machine_name}: {first['job']}-O{first['op_index']} overlaps {second['job']}-O{second['op_index']}"
                )

    if seen:
        details["makespan"] = max(operation["end"] for operation in seen.values())
    else:
        details["makespan"] = None

    for job in spec.jobs:
        job_operations = [
            operation
            for key, operation in seen.items()
            if key[0] == job.name
        ]
        if job_operations:
            details["job_completion_times"][job.name] = max(
                operation["end"] for operation in job_operations
            )

    computed_objective = details["makespan"]
    if result.objective_value is None:
        violations.append("objective_value is required for feasible results")
    elif computed_objective is None:
        violations.append("cannot compute objective without operations")
    elif abs(computed_objective - result.objective_value) > tolerance:
        violations.append(
            f"objective mismatch: computed={computed_objective}, reported={result.objective_value}"
        )

    reported_makespan = result.solution.get("makespan")
    if reported_makespan is not None and computed_objective is not None:
        if abs(float(reported_makespan) - computed_objective) > tolerance:
            violations.append(
                f"makespan mismatch: computed={computed_objective}, reported={reported_makespan}"
            )

    reported_machine_schedules = result.solution.get("machine_schedules")
    if reported_machine_schedules is not None and not isinstance(reported_machine_schedules, dict):
        violations.append("solution.machine_schedules must be an object when provided")

    return CheckerReport(
        passed=len(violations) == 0,
        violations=violations,
        computed_objective=computed_objective,
        details=details,
    )
