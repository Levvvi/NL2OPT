from enum import Enum

from pydantic import BaseModel, ConfigDict


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProblemType(str, Enum):
    PRODUCTION = "production"
    ASSIGNMENT = "assignment"
    JOBSHOP = "jobshop"
    VRP = "vrp"
    UNSUPPORTED = "unsupported"


class ObjectiveSense(str, Enum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class ObjectiveSpec(StrictBaseModel):
    sense: ObjectiveSense
    name: str
