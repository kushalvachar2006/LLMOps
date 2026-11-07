import re

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
)

ENVIRONMENTS = ("development", "staging", "production")
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


def _env(v: str) -> str:
    if v not in ENVIRONMENTS:
        raise ValueError(f"environment must be one of {', '.join(ENVIRONMENTS)}")
    return v


class DeploymentCreate(BaseModel):
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


class ValidationSpec(BaseModel):
    """Checks that must pass before a version can be called 'ready'."""

    sample_inputs: list[dict] = Field(default_factory=list, max_length=3)
    expect_json: bool = False
    max_output_chars: int | None = Field(default=None, ge=1, le=100_000)


class PublishRequest(BaseModel):
    prompt_id: str = Field(min_length=1, max_length=64)
    prompt_version: int | None = Field(default=None, ge=1)  # None = latest
    validation: ValidationSpec = Field(default_factory=ValidationSpec)
    change_description: str | None = Field(default=None, max_length=500)


class PromoteRequest(BaseModel):
    version: int = Field(ge=1)
    environment: str

    @field_validator("environment")
    @classmethod
    def _e(cls, v: str) -> str:
        return _env(v)


class ApiKeyCreate(BaseModel):
    project_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    environments: list[str] = Field(default_factory=lambda: ["production"], min_length=1, max_length=3)
    rate_limit_per_minute: int | None = Field(default=None, ge=1)

    @field_validator("environments")
    @classmethod
    def _envs(cls, v: list[str]) -> list[str]:
        return sorted({_env(e) for e in v})


class InvokeRequest(BaseModel):
    """Public request body. Unknown fields are rejected so typos are noticed."""

    model_config = ConfigDict(extra="forbid")
    inputs: dict[str, StrictStr | StrictInt | StrictFloat | StrictBool] = Field(
        default_factory=dict, max_length=50
    )
    environment: str = "production"

    @field_validator("inputs")
    @classmethod
    def _keys(cls, v: dict) -> dict:
        bad = [k for k in v if not _NAME.match(k)]
        if bad:
            raise ValueError("input names must be letters, digits and underscores")
        return v
