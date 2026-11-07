from app.core.config import Settings
from app.services.providers.base import LLMProvider
from app.services.providers.gemini import GeminiProvider
from app.services.providers.mock import MockProvider


def build_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockProvider()
    assert settings.gemini_api_key is not None  # guaranteed by Settings validation
    return GeminiProvider(
        api_key=settings.gemini_api_key.get_secret_value(),
        default_model=settings.gemini_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
