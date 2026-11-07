from datetime import date

from pydantic import BaseModel, Field, field_validator


class PricingCreate(BaseModel):
    """A price entered by the user. Nothing is built in: prices change, so you verify them."""

    provider: str = Field(min_length=1, max_length=30)
    model: str = Field(min_length=1, max_length=100)
    effective_from: str = Field(description="YYYY-MM-DD; applies to requests from this day on")
    input_price: float = Field(ge=0, le=1_000_000)
    output_price: float = Field(ge=0, le=1_000_000)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    unit: str = Field(default="per_1M_tokens")
    source_note: str | None = Field(default=None, max_length=300)

    @field_validator("effective_from")
    @classmethod
    def _date(cls, v: str) -> str:
        try:
            return date.fromisoformat(v).isoformat()
        except ValueError:
            raise ValueError("effective_from must be a date like 2026-01-31") from None

    @field_validator("unit")
    @classmethod
    def _unit(cls, v: str) -> str:
        if v not in ("per_1M_tokens", "per_1K_tokens"):
            raise ValueError("unit must be per_1M_tokens or per_1K_tokens")
        return v

    @field_validator("currency")
    @classmethod
    def _cur(cls, v: str) -> str:
        v = v.upper()
        if not v.isalpha():
            raise ValueError("currency must be a 3-letter code like USD")
        return v


class FeedbackCreate(BaseModel):
    request_id: str = Field(min_length=1, max_length=64)
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class Thresholds(BaseModel):
    """Alert rules. Window = the date range you are viewing."""

    min_requests: int = Field(default=20, ge=1, le=100000)
    error_rate_max: float = Field(default=0.2, ge=0, le=1)
    latency_p95_ms_max: float | None = Field(default=None, ge=1)
    quality_drop_max: float = Field(default=0.1, ge=0, le=1)  # on a 0-1 scale
    format_failure_rate_max: float = Field(default=0.2, ge=0, le=1)
    feedback_avg_min: float | None = Field(default=3.0, ge=1, le=5)
    input_length_change_max: float = Field(default=0.5, ge=0, le=10)  # relative change
    min_samples: int = Field(default=5, ge=1, le=100000)
