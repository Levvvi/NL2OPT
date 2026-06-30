from pydantic import Field, field_validator, model_validator

from nl2opt.schemas.base import ObjectiveSense, ObjectiveSpec, ProblemType, StrictBaseModel


class JobshopMachine(StrictBaseModel):
    name: str


class JobshopOperation(StrictBaseModel):
    machine: str
    duration: int = Field(gt=0)


class JobshopJob(StrictBaseModel):
    name: str
    operations: list[JobshopOperation] = Field(min_length=1)


class JobshopProblemSpec(StrictBaseModel):
    problem_id: str
    problem_type: ProblemType = ProblemType.JOBSHOP
    objective: ObjectiveSpec
    machines: list[JobshopMachine] = Field(min_length=1)
    jobs: list[JobshopJob] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)

    @field_validator("problem_type")
    @classmethod
    def require_jobshop_type(cls, value: ProblemType) -> ProblemType:
        if value is not ProblemType.JOBSHOP:
            raise ValueError("problem_type must be jobshop")
        return value

    @model_validator(mode="after")
    def validate_jobshop_data(self) -> "JobshopProblemSpec":
        machine_names = [machine.name for machine in self.machines]
        job_names = [job.name for job in self.jobs]
        machine_name_set = set(machine_names)

        if len(machine_names) != len(machine_name_set):
            raise ValueError("machine names must be unique")
        if len(job_names) != len(set(job_names)):
            raise ValueError("job names must be unique")

        if (
            self.objective.sense is not ObjectiveSense.MINIMIZE
            or self.objective.name != "makespan"
        ):
            raise ValueError("jobshop only supports minimize makespan")

        for job in self.jobs:
            for operation in job.operations:
                if operation.machine not in machine_name_set:
                    raise ValueError(f"unknown machine in operation: {operation.machine}")

        return self
