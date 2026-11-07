from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class VersionFields(BaseModel):
    system_instruction: str | None = Field(default=None, max_length=5000)
    template: str = Field(min_length=1, max_length=20000)
    provider: str = Field(min_length=1, max_length=30)
    model: str = Field(min_length=1, max_length=100)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=1024, ge=1, le=8192)
    change_description: str | None = Field(default=None, max_length=500)


class PromptCreate(VersionFields):
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


class PromptVersionCreate(VersionFields):
    pass


class PromptOut(BaseModel):
    id: str
    project_id: str
    name: str
    description: str
    latest_version: int
    created_at: datetime
    updated_at: datetime


class PromptPage(BaseModel):
    items: list[PromptOut]
    total: int
    skip: int
    limit: int
