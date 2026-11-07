"""Deterministic provider for tests and offline demos. Makes no network calls."""
from app.core.errors import ProviderError
from app.services.providers.base import GenerationParams, ProviderResult


class MockProvider:
    name = "mock"
    default_model = "mock-model"

    def __init__(self, fail_with: ProviderError | None = None):
        self._fail_with = fail_with
        self.calls: list[GenerationParams] = []

    def generate(self, params: GenerationParams) -> ProviderResult:
        self.calls.append(params)
        if self._fail_with is not None:
            raise self._fail_with
        text = f"[mock reply] {params.prompt[:200]}"
        in_tokens = max(1, len(params.prompt.split()))
        out_tokens = max(1, len(text.split()))
        return ProviderResult(text, in_tokens, out_tokens, in_tokens + out_tokens)
