from enum import Enum
from typing import Any

from pydantic import Field

from nl2opt.schemas.base import StrictBaseModel


class SolverStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    ERROR = "ERROR"


class SolverResult(StrictBaseModel):
    status: SolverStatus
    objective_value: float | None = None
    solution: dict[str, Any] = Field(default_factory=dict)
    runtime_sec: float = Field(ge=0)
    solver: str
    violations: list[str] = Field(default_factory=list)
