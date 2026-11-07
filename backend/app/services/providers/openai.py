"""OpenAI Chat Completions adapter (plain HTTPS via httpx)."""
import httpx

from app.core.errors import ProviderError, ProviderTimeoutError
from app.services.model_catalog import limits_for
from app.services.providers.base import GenerationParams, ProviderResult
from app.services.providers.http_errors import map_http_error


class OpenAIProvider:
    name = "openai"
    default_model = "gpt-4.1-mini"

    def __init__(self, api_key: str, timeout_seconds: int = 30, transport=None,
                 base_url: str = "https://api.openai.com/v1"):
        self._key = api_key
        self._timeout = timeout_seconds
        self._transport = transport
        self._url = f"{base_url}/chat/completions"

    def generate(self, params: GenerationParams) -> ProviderResult:
        messages = []
        if params.system_instruction:
            messages.append({"role": "system", "content": params.system_instruction})
        messages.append({"role": "user", "content": params.prompt})
        body = {
            "model": params.model,
            "messages": messages,
            "max_completion_tokens": params.max_output_tokens,
        }
        if limits_for("openai", params.model).supports_temperature:
            body["temperature"] = params.temperature
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                resp = client.post(
                    self._url, json=body, headers={"Authorization": f"Bearer {self._key}"}
                )
        except httpx.TimeoutException:
            raise ProviderTimeoutError("The model provider timed out") from None
        except httpx.HTTPError:
            raise ProviderError("Could not reach the model provider") from None
        if resp.status_code >= 400:
            raise map_http_error(resp.status_code, resp.text, self._key)
        try:
            data = resp.json()
            text = data["choices"][0]["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("The model provider returned an unreadable response") from None
        usage = data.get("usage") or {}
        return ProviderResult(
            text,
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            usage.get("total_tokens"),
        )
