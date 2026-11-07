"""Curated list of selectable models plus per-model parameter limits.

The list is a convenience, not a guarantee: vendors add and retire models often, so the UI
also accepts any custom model ID and the vendor's own error is shown if it is unknown.
"""
from dataclasses import dataclass

from app.core.errors import ValidationAppError

PROVIDER_LABELS = {
    "gemini": "Google Gemini",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "mock": "Mock (offline demo)",
}


@dataclass(frozen=True)
class ModelInfo:
    id: str
    label: str
    provider: str
    supports_temperature: bool = True
    temp_max: float = 2.0
    max_output_tokens: int = 8192
    note: str = ""


_NO_TEMP = "Fixed temperature: the vendor ignores or rejects this setting."
_REASON = "Reasoning model: hidden thinking tokens count toward the output limit, so keep it high."

_FIXED_REASON = _NO_TEMP + " " + _REASON

_MODELS: list[ModelInfo] = [
    ModelInfo("gemini-2.5-pro", "Gemini 2.5 Pro", "gemini", note=_REASON),
    ModelInfo("gemini-2.5-flash", "Gemini 2.5 Flash", "gemini", note=_REASON),
    ModelInfo("gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite", "gemini"),
    ModelInfo("gemini-2.0-flash", "Gemini 2.0 Flash", "gemini"),
    ModelInfo("gpt-4.1", "GPT-4.1", "openai"),
    ModelInfo("gpt-4.1-mini", "GPT-4.1 mini", "openai"),
    ModelInfo("gpt-4.1-nano", "GPT-4.1 nano", "openai"),
    ModelInfo("gpt-4o", "GPT-4o", "openai"),
    ModelInfo("gpt-4o-mini", "GPT-4o mini", "openai"),
    ModelInfo("gpt-5", "GPT-5", "openai", supports_temperature=False, note=_FIXED_REASON),
    ModelInfo(
        "gpt-5-mini", "GPT-5 mini", "openai", supports_temperature=False, note=_FIXED_REASON
    ),
    ModelInfo("o4-mini", "o4-mini", "openai", supports_temperature=False, note=_FIXED_REASON),
    ModelInfo("claude-opus-5-5", "Claude Opus 5.5", "anthropic", temp_max=1.0),
    ModelInfo("claude-sonnet-5-5", "Claude Sonnet 5.5", "anthropic", temp_max=1.0),
    ModelInfo("claude-haiku-5-5", "Claude Haiku 5.5", "anthropic", temp_max=1.0),
    ModelInfo("claude-fable-5-1", "Claude Fable 5.1", "anthropic", temp_max=1.0),
    ModelInfo("mock-model", "Mock model", "mock"),
]


def providers() -> list[str]:
    return list(PROVIDER_LABELS)


def models_for(provider: str) -> list[ModelInfo]:
    return [m for m in _MODELS if m.provider == provider]


def find_model(provider: str, model_id: str) -> ModelInfo | None:
    return next((m for m in _MODELS if m.provider == provider and m.id == model_id), None)


def default_model(provider: str) -> str:
    # Prefer a fast, inexpensive model as the default.
    prefs = {
        "gemini": "gemini-2.5-flash",
        "openai": "gpt-4.1-mini",
        "anthropic": "claude-haiku-5-5",
        "mock": "mock-model",
    }
    return prefs[provider]


def limits_for(provider: str, model_id: str) -> ModelInfo:
    """Catalog entry, or conservative provider defaults for a custom model ID."""
    known = find_model(provider, model_id)
    if known:
        return known
    return ModelInfo(
        model_id, model_id, provider, temp_max=1.0 if provider == "anthropic" else 2.0
    )


def validate_generation(
    provider: str, model_id: str, temperature: float, max_output_tokens: int
) -> None:
    info = limits_for(provider, model_id)
    if info.supports_temperature and not 0.0 <= temperature <= info.temp_max:
        raise ValidationAppError(
            f"Temperature must be between 0 and {info.temp_max:g} for {model_id} ({provider})."
        )
    if not 1 <= max_output_tokens <= info.max_output_tokens:
        raise ValidationAppError(
            f"Max output tokens must be between 1 and {info.max_output_tokens} for {model_id}."
        )
