"""Anthropic Messages API adapter (plain HTTPS via httpx)."""
import httpx

from app.core.errors import ProviderError, ProviderTimeoutError
from app.services.providers.base import GenerationParams, ProviderResult
from app.services.providers.http_errors import map_http_error


class AnthropicProvider:
    name = "anthropic"
    default_model = "claude-haiku-5-5"

    def __init__(self, api_key: str, timeout_seconds: int = 30, transport=None,
                 base_url: str = "https://api.anthropic.com/v1"):
        self._key = api_key
        self._timeout = timeout_seconds
        self._transport = transport
        self._url = f"{base_url}/messages"

    def generate(self, params: GenerationParams) -> ProviderResult:
        body = {
            "model": params.model,
            "max_tokens": params.max_output_tokens,
            "temperature": params.temperature,
            "messages": [{"role": "user", "content": params.prompt}],
        }
        if params.system_instruction:
            body["system"] = params.system_instruction
        headers = {"x-api-key": self._key, "anthropic-version": "2023-06-01"}
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                resp = client.post(self._url, json=body, headers=headers)
        except httpx.TimeoutException:
            raise ProviderTimeoutError("The model provider timed out") from None
        except httpx.HTTPError:
            raise ProviderError("Could not reach the model provider") from None
        if resp.status_code >= 400:
            raise map_http_error(resp.status_code, resp.text, self._key)
        try:
            data = resp.json()
            text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ProviderError("The model provider returned an unreadable response") from None
        usage = data.get("usage") or {}
        i, o = usage.get("input_tokens"), usage.get("output_tokens")
        return ProviderResult(text, i, o, (i + o) if i is not None and o is not None else None)
