"""Shared mapping from vendor HTTP errors to our error categories."""
import re

from app.core.errors import (
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)


def safe_detail(raw: str, api_key: str, limit: int = 200) -> str:
    """Trim vendor text and make sure the user's key can never appear in it."""
    text = raw.replace(api_key, "[redacted]") if api_key else raw
    text = re.sub(r"(sk|key|AIza)[-_A-Za-z0-9]{8,}", "[redacted]", text)
    return " ".join(text.split())[:limit]


def map_http_error(status: int, raw_body: str, api_key: str) -> ProviderError:
    if status == 429:
        return ProviderRateLimitError("Rate limit or quota exceeded at the model provider")
    if status in (401, 403):
        return ProviderAuthError("The model provider rejected the API key")
    if status in (408, 504):
        return ProviderTimeoutError("The model provider timed out")
    if status in (400, 404, 422):
        detail = safe_detail(raw_body, api_key)
        return ProviderBadRequestError(f"The model provider rejected the request: {detail}")
    return ProviderError("The model provider returned an error")
