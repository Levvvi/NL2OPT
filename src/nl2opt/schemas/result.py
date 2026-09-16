import math
from enum import Enum
from typing import Any

from pydantic import Field, field_validator

from nl2opt.schemas.base import StrictBaseModel


class SolverStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNBOUNDED = "UNBOUNDED"
    ERROR = "ERROR"


class SolverResult(StrictBaseModel):
    status: SolverStatus
    objective_value: float | None = Field(default=None, allow_inf_nan=False)
    solution: dict[str, Any] = Field(default_factory=dict)
    runtime_sec: float = Field(ge=0, allow_inf_nan=False)
    solver: str
    violations: list[str] = Field(default_factory=list)

    @field_validator("solution")
    @classmethod
    def require_finite_solution_numbers(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Reject non-finite JSON numbers before any family-specific checker."""

        def visit(item: Any, path: str) -> None:
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError(f"{path} must be finite")
            if isinstance(item, dict):
                for key, child in item.items():
                    visit(child, f"{path}.{key}")
            elif isinstance(item, list):
                for index, child in enumerate(item):
                    visit(child, f"{path}[{index}]")

        visit(value, "solution")
        return value
