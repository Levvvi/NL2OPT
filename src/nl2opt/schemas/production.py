from pydantic import Field, field_validator, model_validator

from nl2opt.schemas.base import ObjectiveSpec, ProblemType, StrictBaseModel


class ProductSpec(StrictBaseModel):
    name: str
    profit: float = Field(ge=0)


class ResourceSpec(StrictBaseModel):
    name: str
    capacity: float = Field(ge=0)


class ProductionProblemSpec(StrictBaseModel):
    problem_id: str
    problem_type: ProblemType = ProblemType.PRODUCTION
    objective: ObjectiveSpec
    products: list[ProductSpec] = Field(min_length=1)
    resources: list[ResourceSpec] = Field(min_length=1)
    consumption: dict[str, dict[str, float]]
    assumptions: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)

    @field_validator("problem_type")
    @classmethod
    def require_production_type(cls, value: ProblemType) -> ProblemType:
        if value is not ProblemType.PRODUCTION:
            raise ValueError("problem_type must be production")
        return value

    @model_validator(mode="after")
    def validate_consumption_matrix(self) -> "ProductionProblemSpec":
        product_names = {product.name for product in self.products}
        resource_names = {resource.name for resource in self.resources}

        for product_name, resource_consumption in self.consumption.items():
            if product_name not in product_names:
                raise ValueError(f"unknown product in consumption: {product_name}")

            for resource_name, amount in resource_consumption.items():
                if resource_name not in resource_names:
                    raise ValueError(f"unknown resource in consumption: {resource_name}")
                if amount < 0:
                    raise ValueError("consumption amount cannot be negative")

        return self
