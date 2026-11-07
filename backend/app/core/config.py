"""Environment-based configuration, validated once at startup."""
from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    # Prompts/responses may contain private data, so they are NOT stored unless enabled.
    store_prompt_text: bool = False
    # Text that IS stored (prompts when enabled, feedback comments) is scrubbed of emails,
    # phone numbers, card-like numbers and key-like tokens.
    redaction_enabled: bool = True
    # Traces and feedback older than this are deleted by MongoDB itself. 0 = keep forever.
    trace_retention_days: int = Field(default=0, ge=0, le=3650)

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "llmops"
    mongodb_timeout_ms: int = Field(default=3000, ge=500)

    # Default provider when a request does not name one.
    llm_provider: str = "gemini"  # gemini | openai | anthropic | mock
    # Optional server-side keys. Users can instead supply their own key per request.
    gemini_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"
    llm_timeout_seconds: int = Field(default=30, ge=1, le=300)

    cors_origins: str = "http://localhost:8501"

    max_dataset_bytes: int = Field(default=2_000_000, ge=1_000)
    max_dataset_rows: int = Field(default=5000, ge=1)
    experiment_max_rows: int = Field(default=50, ge=1, le=500)

    # --- Phase 4: protecting the management API and the public inference API ---
    # If set, every /api/* call must carry this value in the X-Admin-Token header.
    admin_token: SecretStr | None = None
    # Secret mixed into API-key hashes (HMAC). Changing it invalidates all existing keys.
    api_key_pepper: SecretStr | None = None
    max_request_bytes: int = Field(default=32_768, ge=1_024, le=1_048_576)
    max_input_chars: int = Field(default=10_000, ge=1, le=20_000)
    default_rate_limit_per_minute: int = Field(default=60, ge=1, le=10_000)
    max_rate_limit_per_minute: int = Field(default=1000, ge=1, le=100_000)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _validate(self) -> "Settings":
        if self.llm_provider not in {"gemini", "openai", "anthropic", "mock"}:
            raise ValueError("LLM_PROVIDER must be gemini, openai, anthropic or mock")
        return self

    @property
    def pepper(self) -> str:
        return self.api_key_pepper.get_secret_value() if self.api_key_pepper else ""

    @property
    def admin_token_value(self) -> str | None:
        value = self.admin_token.get_secret_value().strip() if self.admin_token else ""
        return value or None

    def server_key(self, provider: str) -> str | None:
        secret = {
            "gemini": self.gemini_api_key,
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
        }.get(provider)
        value = secret.get_secret_value().strip() if secret else ""
        return value or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
