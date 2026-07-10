from __future__ import annotations

import math
from numbers import Real

from ortools.linear_solver import pywraplp

from nl2opt.checkers.base import CheckerReport
from nl2opt.schemas import GenericLpSpec, SolverResult, SolverStatus


def _is_finite_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)


def _create_feasibility_solver(spec: GenericLpSpec):
    solver_name = "SCIP" if any(variable.is_integer for variable in spec.variables) else "GLOP"
    return pywraplp.Solver.CreateSolver(solver_name), solver_name


def _add_model_constraints(solver: pywraplp.Solver, spec: GenericLpSpec) -> None:
    variables = {
        variable.name: (
            solver.IntVar(variable.lb, solver.infinity() if variable.ub is None else variable.ub, variable.name)
            if variable.is_integer
            else solver.NumVar(variable.lb, solver.infinity() if variable.ub is None else variable.ub, variable.name)
        )
        for variable in spec.variables
    }
    for constraint in spec.constraints:
        expression = solver.Sum(term.coef * variables[term.var] for term in constraint.terms)
        if constraint.op == "<=":
            solver.Add(expression <= constraint.rhs)
        elif constraint.op == ">=":
            solver.Add(expression >= constraint.rhs)
        else:
            solver.Add(expression == constraint.rhs)


def _verify_infeasibility(spec: GenericLpSpec, timeout_sec: float | None = None) -> tuple[bool, str]:
    solver, solver_name = _create_feasibility_solver(spec)
    if solver is None:
        return False, f"{solver_name} is unavailable"
    _add_model_constraints(solver, spec)
    if timeout_sec is not None:
        solver.SetTimeLimit(max(1, math.ceil(timeout_sec * 1000)))
    status = solver.Solve()
    return status == pywraplp.Solver.INFEASIBLE, solver_name


def check_generic_solution(
    spec: GenericLpSpec,
    result: SolverResult,
    tolerance: float = 1e-6,
    timeout_sec: float | None = None,
) -> CheckerReport:
    if result.status is SolverStatus.INFEASIBLE:
        if timeout_sec is not None and timeout_sec <= 0:
            return CheckerReport(
                passed=False,
                violations=["no remaining time for independent infeasibility verification"],
                details={"infeasibility_verified": False},
            )
        verified, solver_name = _verify_infeasibility(spec, timeout_sec=timeout_sec)
        if verified:
            return CheckerReport(
                passed=True,
                details={
                    "infeasibility_verified": True,
                    "verification_solver": solver_name,
                    "verification_timeout_sec": timeout_sec,
                },
            )
        return CheckerReport(
            passed=False,
            violations=["reported infeasibility could not be independently verified"],
            details={
                "infeasibility_verified": False,
                "verification_solver": solver_name,
                "verification_timeout_sec": timeout_sec,
            },
        )

    if result.status not in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
        return CheckerReport(
            passed=False,
            violations=[f"solver status is not feasible: {result.status.value}"],
        )

    variables = result.solution.get("variables")
    if not isinstance(variables, dict):
        return CheckerReport(
            passed=False,
            violations=["solution.variables is required for feasible results"],
        )

    violations: list[str] = []
    declared_variables = {variable.name: variable for variable in spec.variables}
    values: dict[str, float] = {}
    for name, value in variables.items():
        if name not in declared_variables:
            violations.append(f"unknown variable in solution: {name}")
            continue
        if not _is_finite_number(value):
            violations.append(f"value for {name} must be a finite number")
            continue
        values[name] = float(value)

    for name, variable in declared_variables.items():
        value = values.get(name)
        if value is None:
            violations.append(f"solution.variables is missing {name}")
            continue
        if value < variable.lb - tolerance:
            violations.append(f"variable {name} is below lb: value={value}, lb={variable.lb}")
        if variable.ub is not None and value > variable.ub + tolerance:
            violations.append(f"variable {name} is above ub: value={value}, ub={variable.ub}")
        if variable.is_integer and abs(value - round(value)) > tolerance:
            violations.append(f"integer variable {name} has non-integer value: {value}")

    if len(values) == len(declared_variables):
        for constraint_index, constraint in enumerate(spec.constraints):
            lhs = sum(term.coef * values[term.var] for term in constraint.terms)
            if constraint.op == "<=" and lhs > constraint.rhs + tolerance:
                violations.append(
                    f"constraint {constraint_index} violated: lhs={lhs} > rhs={constraint.rhs}"
                )
            elif constraint.op == ">=" and lhs < constraint.rhs - tolerance:
                violations.append(
                    f"constraint {constraint_index} violated: lhs={lhs} < rhs={constraint.rhs}"
                )
            elif constraint.op == "==" and abs(lhs - constraint.rhs) > tolerance:
                violations.append(
                    f"constraint {constraint_index} violated: lhs={lhs} != rhs={constraint.rhs}"
                )

    computed_objective = None
    if len(values) == len(declared_variables):
        computed_objective = sum(term.coef * values[term.var] for term in spec.objective.terms)
        if result.objective_value is None:
            violations.append("objective_value is required for feasible results")
        elif not _is_finite_number(result.objective_value):
            violations.append("objective_value must be a finite number")
        elif abs(computed_objective - result.objective_value) > tolerance:
            violations.append(
                f"objective mismatch: computed={computed_objective}, reported={result.objective_value}"
            )

    return CheckerReport(
        passed=not violations,
        violations=violations,
        computed_objective=computed_objective,
        resource_usage={},
    )
