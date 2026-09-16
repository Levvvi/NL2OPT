from __future__ import annotations

import math
from numbers import Real

from nl2opt.checkers.base import CheckerReport
from nl2opt.schemas import ProductionProblemSpec, SolverResult, SolverStatus


def _is_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)


def check_production_solution(
    spec: ProductionProblemSpec,
    result: SolverResult,
    tolerance: float = 1e-6,
) -> CheckerReport:
    violations: list[str] = []
    resource_usage = {resource.name: 0.0 for resource in spec.resources}
    computed_objective: float | None = None

    if result.status not in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
        return CheckerReport(
            passed=False,
            violations=[f"solver status is not feasible: {result.status.value}"],
            computed_objective=None,
            resource_usage=resource_usage,
        )

    quantities = result.solution.get("quantities")
    if not isinstance(quantities, dict):
        return CheckerReport(
            passed=False,
            violations=["solution.quantities is required for feasible results"],
            computed_objective=None,
            resource_usage=resource_usage,
        )

    products_by_name = {product.name: product for product in spec.products}
    valid_quantities: dict[str, float] = {}

    for product_name, quantity in quantities.items():
        if product_name not in products_by_name:
            violations.append(f"unknown product in solution: {product_name}")
            continue
        if not _is_number(quantity):
            violations.append(f"quantity for {product_name} must be a finite number")
            continue
        if quantity < 0:
            violations.append(f"quantity for {product_name} cannot be negative")
            continue
        if abs(quantity - round(quantity)) > tolerance:
            violations.append(f"quantity for {product_name} must be an integer")
            continue
        valid_quantities[product_name] = float(quantity)

    for product in spec.products:
        quantity = valid_quantities.get(product.name, 0.0)
        for resource in spec.resources:
            amount = spec.consumption[product.name].get(resource.name, 0.0)
            resource_usage[resource.name] += amount * quantity

    for resource in spec.resources:
        usage = resource_usage[resource.name]
        if usage - resource.capacity > tolerance:
            violations.append(
                f"resource {resource.name} capacity exceeded: usage={usage}, capacity={resource.capacity}"
            )

    computed_objective = sum(
        product.profit * valid_quantities.get(product.name, 0.0)
        for product in spec.products
    )

    if result.objective_value is None:
        violations.append("objective_value is required for feasible results")
    elif not _is_number(result.objective_value):
        violations.append("objective_value must be a finite number")
    elif abs(computed_objective - result.objective_value) > tolerance:
        violations.append(
            f"objective mismatch: computed={computed_objective}, reported={result.objective_value}"
        )

    return CheckerReport(
        passed=len(violations) == 0,
        violations=violations,
        computed_objective=computed_objective,
        resource_usage=resource_usage,
    )
