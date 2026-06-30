from pydantic import Field, field_validator, model_validator

from nl2opt.schemas.base import ObjectiveSpec, ProblemType, StrictBaseModel


class AssignmentEmployee(StrictBaseModel):
    name: str
    capacity: int = Field(ge=0)


class AssignmentTask(StrictBaseModel):
    name: str


class AssignmentProblemSpec(StrictBaseModel):
    problem_id: str
    problem_type: ProblemType = ProblemType.ASSIGNMENT
    objective: ObjectiveSpec
    employees: list[AssignmentEmployee] = Field(min_length=1)
    tasks: list[AssignmentTask] = Field(min_length=1)
    costs: dict[str, dict[str, float]]
    assumptions: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)

    @field_validator("problem_type")
    @classmethod
    def require_assignment_type(cls, value: ProblemType) -> ProblemType:
        if value is not ProblemType.ASSIGNMENT:
            raise ValueError("problem_type must be assignment")
        return value

    @model_validator(mode="after")
    def validate_assignment_data(self) -> "AssignmentProblemSpec":
        employee_names = [employee.name for employee in self.employees]
        task_names = [task.name for task in self.tasks]
        employee_name_set = set(employee_names)
        task_name_set = set(task_names)

        if len(employee_names) != len(employee_name_set):
            raise ValueError("employee names must be unique")
        if len(task_names) != len(task_name_set):
            raise ValueError("task names must be unique")

        available_tasks: set[str] = set()
        for employee_name, task_costs in self.costs.items():
            if employee_name not in employee_name_set:
                raise ValueError(f"unknown employee in costs: {employee_name}")

            for task_name, cost in task_costs.items():
                if task_name not in task_name_set:
                    raise ValueError(f"unknown task in costs: {task_name}")
                if cost < 0:
                    raise ValueError("cost cannot be negative")
                available_tasks.add(task_name)

        missing_tasks = task_name_set - available_tasks
        if missing_tasks:
            names = ", ".join(sorted(missing_tasks))
            raise ValueError(f"tasks without available employee: {names}")

        return self
