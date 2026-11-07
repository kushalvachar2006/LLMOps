from pydantic import BaseModel, Field, field_validator


class DatasetUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    required_fields: list[str] = Field(default_factory=list, max_length=50)
    split_ratios: dict[str, float] | None = None
    split_seed: int = 42
    change_description: str | None = Field(default=None, max_length=500)


class DatasetCreate(DatasetUpload):
    project_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("name must not be blank")
        return v
