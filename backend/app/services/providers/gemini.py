"""Gemini adapter using the google-genai SDK. Runs server-side only."""
import logging

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.core.errors import (
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.services.providers.base import GenerationParams, ProviderResult

log = logging.getLogger(__name__)


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, default_model: str, timeout_seconds: int = 30):
        self.default_model = default_model
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_seconds * 1000),  # milliseconds
        )

    def generate(self, params: GenerationParams) -> ProviderResult:
        config = types.GenerateContentConfig(
            system_instruction=params.system_instruction,
            temperature=params.temperature,
            max_output_tokens=params.max_output_tokens,
        )
        try:
            resp = self._client.models.generate_content(
                model=params.model, contents=params.prompt, config=config
            )
        except genai_errors.APIError as exc:
            raise self._map_api_error(exc) from None
        except (httpx.TimeoutException, TimeoutError):
            raise ProviderTimeoutError("The model provider timed out") from None
        except Exception as exc:  # noqa: BLE001
            log.error(
                "unexpected provider failure",
                extra={"ctx": {"error_type": type(exc).__name__}},
            )
            raise ProviderError("The model provider failed unexpectedly") from None

        usage = resp.usage_metadata
        try:
            text = resp.text or ""
        except Exception:  # noqa: BLE001 - blocked/empty responses have no text
            text = ""
        return ProviderResult(
            text=text,
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=getattr(usage, "candidates_token_count", None),
            total_tokens=getattr(usage, "total_token_count", None),
        )

    @staticmethod
    def _map_api_error(exc: genai_errors.APIError) -> ProviderError:
        # Only the numeric status is used; raw provider text is dropped so nothing sensitive leaks.
        code = getattr(exc, "code", None)
        if code == 429:
            return ProviderRateLimitError("Rate limit or quota exceeded at the model provider")
        if code in (401, 403):
            return ProviderAuthError("The model provider rejected the server credentials")
        if code in (408, 504):
            return ProviderTimeoutError("The model provider timed out")
        if code == 400:
            return ProviderBadRequestError("The model provider rejected the request")
        return ProviderError("The model provider returned an error")
