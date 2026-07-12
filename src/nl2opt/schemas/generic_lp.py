from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, field_validator, model_validator

from nl2opt.schemas.base import ObjectiveSense, ProblemType, StrictBaseModel


def _require_finite(value: float, field_name: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite")
    return value


class GenericVariableSpec(StrictBaseModel):
    name: str = Field(min_length=1)
    lb: float
    ub: float | None = None
    is_integer: bool

    @field_validator("lb")
    @classmethod
    def require_finite_lower_bound(cls, value: float) -> float:
        return _require_finite(value, "lb")

    @field_validator("ub")
    @classmethod
    def require_finite_upper_bound(cls, value: float | None) -> float | None:
        return None if value is None else _require_finite(value, "ub")

    @model_validator(mode="after")
    def require_ordered_bounds(self) -> "GenericVariableSpec":
        if self.ub is not None and self.ub < self.lb:
            raise ValueError("ub must be greater than or equal to lb")
        return self


class LinearTerm(StrictBaseModel):
    var: str = Field(min_length=1)
    coef: float

    @field_validator("coef")
    @classmethod
    def require_finite_coefficient(cls, value: float) -> float:
        return _require_finite(value, "coef")


class LinearConstraint(StrictBaseModel):
    terms: list[LinearTerm] = Field(min_length=1)
    op: Literal["<=", ">=", "=="]
    rhs: float

    @field_validator("rhs")
    @classmethod
    def require_finite_rhs(cls, value: float) -> float:
        return _require_finite(value, "rhs")


class GenericObjectiveSpec(StrictBaseModel):
    sense: ObjectiveSense
    name: str = Field(min_length=1)
    terms: list[LinearTerm] = Field(min_length=1)


class GenericLpSpec(StrictBaseModel):
    problem_id: str
    problem_type: ProblemType = ProblemType.GENERIC_LP_MILP
    variables: list[GenericVariableSpec] = Field(min_length=1)
    objective: GenericObjectiveSpec
    constraints: list[LinearConstraint] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)

    @field_validator("problem_type")
    @classmethod
    def require_generic_lp_type(cls, value: ProblemType) -> ProblemType:
        if value is not ProblemType.GENERIC_LP_MILP:
            raise ValueError("problem_type must be generic_lp_milp")
        return value

    @model_validator(mode="after")
    def validate_variable_references(self) -> "GenericLpSpec":
        variable_names = [variable.name for variable in self.variables]
        if len(variable_names) != len(set(variable_names)):
            raise ValueError("variable names must be unique")

        known_variables = set(variable_names)
        for term in self.objective.terms:
            if term.var not in known_variables:
                raise ValueError(f"unknown variable in objective: {term.var}")
        for constraint_index, constraint in enumerate(self.constraints):
            for term in constraint.terms:
                if term.var not in known_variables:
                    raise ValueError(
                        f"unknown variable in constraints[{constraint_index}]: {term.var}"
                    )
        return self


class UnsupportedProblemSpec(StrictBaseModel):
    problem_id: str
    problem_type: ProblemType = ProblemType.UNSUPPORTED
    reason: str = Field(min_length=1)

    @field_validator("problem_type")
    @classmethod
    def require_unsupported_type(cls, value: ProblemType) -> ProblemType:
        if value is not ProblemType.UNSUPPORTED:
            raise ValueError("problem_type must be unsupported")
        return value
