from datetime import datetime

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    system_instruction: str | None = Field(default=None, max_length=5000)
    provider: str | None = Field(default=None, max_length=30)
    model: str | None = Field(default=None, max_length=100)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=1024, ge=1, le=8192)
    project_id: str | None = Field(default=None, max_length=64)


class Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class GenerateResponse(BaseModel):
    request_id: str
    text: str
    provider: str
    model: str
    latency_ms: float
    usage: Usage
    # False means the model answered but saving telemetry failed (see logs).
    telemetry_recorded: bool


class RequestRecord(BaseModel):
    request_id: str
    created_at: datetime
    project_id: str | None = None
    provider: str
    model: str
    status: str
    error_category: str | None = None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    prompt_chars: int
    response_chars: int | None = None
    temperature: float
    max_output_tokens: int
    retry_count: int | None = None
    deployment_id: str | None = None
    prompt_id: str | None = None
    prompt_version: int | None = None
    experiment_id: str | None = None
    deployment_version: int | None = None
    environment: str | None = None
    api_key_id: str | None = None
    evaluations: list[dict] = []


class RequestPage(BaseModel):
    items: list[RequestRecord]
    total: int
    skip: int
    limit: int
