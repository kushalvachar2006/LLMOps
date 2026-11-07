"""Builds the right provider for each request, using the caller's key or a server key."""
from app.core.config import Settings
from app.core.errors import MissingApiKeyError, ValidationAppError
from app.services.model_catalog import default_model, providers
from app.services.providers.anthropic import AnthropicProvider
from app.services.providers.base import LLMProvider
from app.services.providers.gemini import GeminiProvider
from app.services.providers.mock import MockProvider
from app.services.providers.openai import OpenAIProvider


class ProviderRegistry:
    def __init__(self, settings: Settings, override: LLMProvider | None = None):
        self._settings = settings
        self._override = override  # tests inject a fake provider here

    @property
    def default_provider(self) -> str:
        return self._override.name if self._override else self._settings.llm_provider

    def has_server_key(self, provider: str) -> bool:
        return self._settings.server_key(provider) is not None

    def mock_enabled(self) -> bool:
        return self.default_provider == "mock" or (
            self._override is not None and self._override.name == "mock"
        )

    def get(self, provider: str | None, api_key: str | None) -> LLMProvider:
        if self._override is not None:
            return self._override
        name = provider or self._settings.llm_provider
        if name not in providers():
            raise ValidationAppError(f"Unknown provider '{name}'.")
        if name == "mock":
            if self._settings.llm_provider != "mock":
                raise ValidationAppError("The mock provider is disabled on this server.")
            return MockProvider()
        key = api_key or self._settings.server_key(name)
        if not key:
            raise MissingApiKeyError(
                f"No API key for {name}. Enter your own key in the app, or ask the "
                "server admin to configure one."
            )
        timeout = self._settings.llm_timeout_seconds
        if name == "gemini":
            return GeminiProvider(key, default_model("gemini"), timeout)
        if name == "openai":
            return OpenAIProvider(key, timeout)
        return AnthropicProvider(key, timeout)
