from pydantic import BaseModel, Field


class EvaluatorConfig(BaseModel):
    type: str = Field(min_length=1, max_length=40)
    params: dict = Field(default_factory=dict)


class ExperimentCreate(BaseModel):
    project_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    prompt_id: str = Field(min_length=1, max_length=64)
    prompt_version: int | None = Field(default=None, ge=1)  # None = latest
    dataset_id: str = Field(min_length=1, max_length=64)
    dataset_version: int | None = Field(default=None, ge=1)  # None = latest
    split: str = Field(default="all", max_length=20)
    max_rows: int = Field(default=20, ge=1, le=500)
    evaluators: list[EvaluatorConfig] = Field(default_factory=list, max_length=10)
    reference_field: str | None = Field(default=None, max_length=100)
