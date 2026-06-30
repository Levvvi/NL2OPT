from __future__ import annotations

from nl2opt.checkers.base import CheckerReport
from nl2opt.schemas import AssignmentProblemSpec, SolverResult, SolverStatus


def check_assignment_solution(
    spec: AssignmentProblemSpec,
    result: SolverResult,
    tolerance: float = 1e-6,
) -> CheckerReport:
    violations: list[str] = []
    employee_loads = {employee.name: 0 for employee in spec.employees}
    computed_objective: float | None = None

    if result.status not in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
        return CheckerReport(
            passed=False,
            violations=[f"solver status is not feasible: {result.status.value}"],
            computed_objective=None,
            details={"employee_loads": employee_loads},
        )

    assignments = result.solution.get("assignments")
    if not isinstance(assignments, dict):
        return CheckerReport(
            passed=False,
            violations=["solution.assignments is required for feasible results"],
            computed_objective=None,
            details={"employee_loads": employee_loads},
        )

    task_names = {task.name for task in spec.tasks}
    employee_names = {employee.name for employee in spec.employees}
    capacities = {employee.name: employee.capacity for employee in spec.employees}
    valid_assignments: dict[str, str] = {}

    missing_tasks = task_names - set(assignments)
    for task_name in sorted(missing_tasks):
        violations.append(f"missing task assignment: {task_name}")

    for task_name in sorted(set(assignments) - task_names):
        violations.append(f"unknown task in assignments: {task_name}")

    for task_name, employee_name in assignments.items():
        if task_name not in task_names:
            continue
        if employee_name not in employee_names:
            violations.append(f"unknown employee in assignment for {task_name}: {employee_name}")
            continue
        if task_name not in spec.costs.get(employee_name, {}):
            violations.append(f"ineligible employee-task pair: {employee_name}-{task_name}")
            continue

        valid_assignments[task_name] = employee_name
        employee_loads[employee_name] += 1

    for employee_name, load in employee_loads.items():
        capacity = capacities[employee_name]
        if load > capacity:
            violations.append(
                f"employee {employee_name} capacity exceeded: load={load}, capacity={capacity}"
            )

    computed_objective = sum(
        spec.costs[employee_name][task_name]
        for task_name, employee_name in valid_assignments.items()
    )

    if result.objective_value is None:
        violations.append("objective_value is required for feasible results")
    elif abs(computed_objective - result.objective_value) > tolerance:
        violations.append(
            f"objective mismatch: computed={computed_objective}, reported={result.objective_value}"
        )

    reported_loads = result.solution.get("employee_loads")
    if reported_loads is not None:
        if not isinstance(reported_loads, dict):
            violations.append("solution.employee_loads must be an object when provided")
        else:
            for employee_name, expected_load in employee_loads.items():
                reported_load = reported_loads.get(employee_name)
                if reported_load != expected_load:
                    violations.append(
                        f"employee_loads mismatch for {employee_name}: computed={expected_load}, reported={reported_load}"
                    )
            for employee_name in set(reported_loads) - employee_names:
                violations.append(f"unknown employee in employee_loads: {employee_name}")

    return CheckerReport(
        passed=len(violations) == 0,
        violations=violations,
        computed_objective=computed_objective,
        details={"employee_loads": employee_loads},
    )
