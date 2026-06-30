from pydantic import Field, field_validator, model_validator

from nl2opt.schemas.base import ObjectiveSense, ObjectiveSpec, ProblemType, StrictBaseModel


class VrpCustomer(StrictBaseModel):
    name: str
    demand: int = Field(ge=0)


class VrpVehicle(StrictBaseModel):
    name: str
    capacity: int = Field(gt=0)


class VrpProblemSpec(StrictBaseModel):
    problem_id: str
    problem_type: ProblemType = ProblemType.VRP
    objective: ObjectiveSpec
    depot: str = Field(min_length=1)
    vehicles: list[VrpVehicle] = Field(min_length=1)
    customers: list[VrpCustomer] = Field(min_length=1)
    distance_matrix: dict[str, dict[str, int]]
    assumptions: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)

    @field_validator("problem_type")
    @classmethod
    def require_vrp_type(cls, value: ProblemType) -> ProblemType:
        if value is not ProblemType.VRP:
            raise ValueError("problem_type must be vrp")
        return value

    @model_validator(mode="after")
    def validate_vrp_data(self) -> "VrpProblemSpec":
        vehicle_names = [vehicle.name for vehicle in self.vehicles]
        customer_names = [customer.name for customer in self.customers]
        vehicle_name_set = set(vehicle_names)
        customer_name_set = set(customer_names)

        if len(vehicle_names) != len(vehicle_name_set):
            raise ValueError("vehicle names must be unique")
        if len(customer_names) != len(customer_name_set):
            raise ValueError("customer names must be unique")
        if self.depot in customer_name_set:
            raise ValueError("depot cannot also be a customer")

        if (
            self.objective.sense is not ObjectiveSense.MINIMIZE
            or self.objective.name != "distance"
        ):
            raise ValueError("vrp only supports minimize distance")

        total_demand = sum(customer.demand for customer in self.customers)
        total_capacity = sum(vehicle.capacity for vehicle in self.vehicles)
        if total_demand > total_capacity:
            raise ValueError("total customer demand exceeds total vehicle capacity")

        node_names = {self.depot, *customer_names}
        matrix_rows = set(self.distance_matrix)
        if matrix_rows != node_names:
            missing = node_names - matrix_rows
            extra = matrix_rows - node_names
            raise ValueError(
                f"distance_matrix rows must match depot and customers; missing={sorted(missing)}, extra={sorted(extra)}"
            )

        for from_node, distances in self.distance_matrix.items():
            columns = set(distances)
            if columns != node_names:
                missing = node_names - columns
                extra = columns - node_names
                raise ValueError(
                    f"distance_matrix row {from_node} columns must match depot and customers; missing={sorted(missing)}, extra={sorted(extra)}"
                )

            for to_node, distance in distances.items():
                if distance < 0:
                    raise ValueError("distance cannot be negative")
                if from_node == to_node and distance != 0:
                    raise ValueError(f"distance from {from_node} to itself must be 0")

        return self
