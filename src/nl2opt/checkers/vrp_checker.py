from __future__ import annotations

from numbers import Real
from typing import Any

from nl2opt.checkers.base import CheckerReport
from nl2opt.schemas import SolverResult, SolverStatus, VrpProblemSpec


def _is_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _empty_details() -> dict[str, Any]:
    return {
        "route_loads": {},
        "route_distances": {},
        "total_distance": None,
        "total_load": None,
        "visited_customers": [],
    }


def check_vrp_solution(
    spec: VrpProblemSpec,
    result: SolverResult,
    tolerance: float = 1e-6,
) -> CheckerReport:
    violations: list[str] = []
    details = _empty_details()

    if result.status not in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
        return CheckerReport(
            passed=False,
            violations=[f"solver status is not feasible: {result.status.value}"],
            computed_objective=None,
            details=details,
        )

    routes = result.solution.get("routes")
    if not isinstance(routes, list):
        return CheckerReport(
            passed=False,
            violations=["solution.routes is required for feasible results"],
            computed_objective=None,
            details=details,
        )

    vehicle_by_name = {vehicle.name: vehicle for vehicle in spec.vehicles}
    demand_by_customer = {customer.name: customer.demand for customer in spec.customers}
    customer_names = set(demand_by_customer)
    known_stops = {spec.depot, *customer_names}
    used_vehicles: set[str] = set()
    visited_customers: list[str] = []
    total_distance = 0.0
    total_load = 0.0

    for route_index, route in enumerate(routes):
        if not isinstance(route, dict):
            violations.append(f"route {route_index} must be an object")
            continue

        vehicle_name = route.get("vehicle")
        stops = route.get("stops")
        if vehicle_name not in vehicle_by_name:
            violations.append(f"unknown vehicle in route: {vehicle_name}")
            continue
        if vehicle_name in used_vehicles:
            violations.append(f"duplicate vehicle route: {vehicle_name}")
            continue
        used_vehicles.add(vehicle_name)

        if not isinstance(stops, list) or not stops:
            violations.append(f"route for {vehicle_name} must include stops")
            continue

        if stops[0] != spec.depot:
            violations.append(f"route for {vehicle_name} must start at depot")
        if stops[-1] != spec.depot:
            violations.append(f"route for {vehicle_name} must end at depot")
        if spec.depot in stops[1:-1]:
            violations.append(f"depot cannot appear in the middle of route for {vehicle_name}")

        unknown_stops = [stop for stop in stops if stop not in known_stops]
        for stop in unknown_stops:
            violations.append(f"unknown stop in route for {vehicle_name}: {stop}")

        route_customers = [
            stop
            for stop in stops[1:-1]
            if stop in customer_names
        ]
        route_load = sum(demand_by_customer[customer] for customer in route_customers)
        route_distance = 0.0
        for from_stop, to_stop in zip(stops, stops[1:]):
            if from_stop in known_stops and to_stop in known_stops:
                route_distance += spec.distance_matrix[from_stop][to_stop]

        capacity = vehicle_by_name[vehicle_name].capacity
        if route_load > capacity:
            violations.append(
                f"vehicle {vehicle_name} capacity exceeded: load={route_load}, capacity={capacity}"
            )

        reported_load = route.get("load")
        if reported_load is not None and (
            not _is_number(reported_load) or abs(float(reported_load) - route_load) > tolerance
        ):
            violations.append(
                f"route load mismatch for {vehicle_name}: computed={route_load}, reported={reported_load}"
            )

        reported_distance = route.get("distance")
        if reported_distance is not None and (
            not _is_number(reported_distance)
            or abs(float(reported_distance) - route_distance) > tolerance
        ):
            violations.append(
                f"route distance mismatch for {vehicle_name}: computed={route_distance}, reported={reported_distance}"
            )

        details["route_loads"][vehicle_name] = route_load
        details["route_distances"][vehicle_name] = route_distance
        visited_customers.extend(route_customers)
        total_load += route_load
        total_distance += route_distance

    duplicate_customers = sorted(
        customer
        for customer in customer_names
        if visited_customers.count(customer) > 1
    )
    for customer in duplicate_customers:
        violations.append(f"duplicate customer visit: {customer}")

    missing_customers = sorted(customer_names - set(visited_customers))
    for customer in missing_customers:
        violations.append(f"missing customer visit: {customer}")

    dropped_customers = result.solution.get("dropped_customers")
    if dropped_customers not in (None, []):
        violations.append(f"dropped_customers must be empty: {dropped_customers}")

    reported_total_distance = result.solution.get("total_distance")
    if reported_total_distance is not None and (
        not _is_number(reported_total_distance)
        or abs(float(reported_total_distance) - total_distance) > tolerance
    ):
        violations.append(
            f"total_distance mismatch: computed={total_distance}, reported={reported_total_distance}"
        )

    if result.objective_value is None:
        violations.append("objective_value is required for feasible results")
    elif abs(total_distance - result.objective_value) > tolerance:
        violations.append(
            f"objective mismatch: computed={total_distance}, reported={result.objective_value}"
        )

    details["total_distance"] = total_distance
    details["total_load"] = total_load
    details["visited_customers"] = sorted(visited_customers)

    return CheckerReport(
        passed=len(violations) == 0,
        violations=violations,
        computed_objective=total_distance,
        details=details,
    )
