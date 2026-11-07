import json

import httpx
import pytest
from app.core.errors import (
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderRateLimitError,
)
from app.services.providers import registry as registry_module
from app.services.providers.anthropic import AnthropicProvider
from app.services.providers.base import GenerationParams
from app.services.providers.openai import OpenAIProvider

KEY = "sk-test-SECRETKEY1234567890"


def _transport(status=200, body=None, capture=None):
    def handler(request: httpx.Request):
        if capture is not None:
            capture["headers"] = dict(request.headers)
            capture["json"] = json.loads(request.content)
        return httpx.Response(status, json=body or {})
    return httpx.MockTransport(handler)


OPENAI_OK = {"choices": [{"message": {"content": "hi"}}],
             "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}}
ANTHROPIC_OK = {"content": [{"type": "text", "text": "hey"}],
                "usage": {"input_tokens": 4, "output_tokens": 6}}


def test_openai_request_shape_and_usage():
    cap = {}
    p = OpenAIProvider(KEY, transport=_transport(200, OPENAI_OK, cap))
    res = p.generate(GenerationParams("q", "gpt-4.1-mini", "be brief", 0.3, 50))
    assert res.text == "hi" and res.total_tokens == 5
    assert cap["headers"]["authorization"] == f"Bearer {KEY}"
    assert cap["json"]["max_completion_tokens"] == 50 and cap["json"]["temperature"] == 0.3
    assert cap["json"]["messages"][0] == {"role": "system", "content": "be brief"}


def test_openai_reasoning_model_omits_temperature():
    cap = {}
    OpenAIProvider(KEY, transport=_transport(200, OPENAI_OK, cap)).generate(
        GenerationParams("q", "gpt-5", None, 0.9, 500)
    )
    assert "temperature" not in cap["json"]


def test_anthropic_request_shape_and_usage():
    cap = {}
    p = AnthropicProvider(KEY, transport=_transport(200, ANTHROPIC_OK, cap))
    res = p.generate(GenerationParams("q", "claude-haiku-5-5", "sys", 0.5, 100))
    assert res.text == "hey" and res.total_tokens == 10
    assert cap["headers"]["x-api-key"] == KEY and "anthropic-version" in cap["headers"]
    assert cap["json"]["system"] == "sys" and cap["json"]["max_tokens"] == 100


@pytest.mark.parametrize("cls", [OpenAIProvider, AnthropicProvider])
def test_http_errors_are_categorised_and_never_leak_key(cls):
    body = {"error": {"message": f"Incorrect API key provided: {KEY}"}}
    with pytest.raises(ProviderAuthError) as e:
        cls(KEY, transport=_transport(401, body)).generate(GenerationParams("q", "m", None, 0.5, 5))
    assert KEY not in e.value.message
    with pytest.raises(ProviderRateLimitError):
        cls(KEY, transport=_transport(429, {})).generate(GenerationParams("q", "m", None, 0.5, 5))
    with pytest.raises(ProviderBadRequestError) as e:
        cls(KEY, transport=_transport(400, {"error": f"bad model {KEY}"})).generate(
            GenerationParams("q", "m", None, 0.5, 5)
        )
    assert KEY not in e.value.message and "bad model" in e.value.message


def test_models_endpoint_lists_providers_and_hides_mock_when_not_default(settings, db):
    from app.core.config import Settings
    from app.main import create_app
    from fastapi.testclient import TestClient

    cfg = Settings(_env_file=None, llm_provider="gemini", gemini_api_key="server-key")
    with TestClient(create_app(settings=cfg, db=db)) as c:
        body = c.get("/api/models").json()
    ids = [p["id"] for p in body["providers"]]
    assert ids == ["gemini", "openai", "anthropic"]
    gem = body["providers"][0]
    assert gem["server_key_configured"] is True
    assert body["providers"][1]["server_key_configured"] is False
    assert any(m["id"] == "gemini-2.5-flash" for m in gem["models"])


def test_models_endpoint_includes_mock_when_enabled(client):
    ids = [p["id"] for p in client.get("/api/models").json()["providers"]]
    assert "mock" in ids


def test_missing_key_gives_clear_400(real_client):
    r = real_client.post("/api/generate", json={"prompt": "x", "provider": "openai"})
    assert r.status_code == 400
    assert r.json()["error"]["category"] == "missing_api_key"


def test_unknown_provider_and_disabled_mock(settings, db):
    from app.core.config import Settings
    from app.main import create_app
    from fastapi.testclient import TestClient

    cfg = Settings(_env_file=None, llm_provider="gemini")
    with TestClient(create_app(settings=cfg, db=db)) as c:
        assert c.post("/api/generate", json={"prompt": "x", "provider": "nope"}).status_code == 422
        assert c.post("/api/generate", json={"prompt": "x", "provider": "mock"}).status_code == 422


def test_user_key_is_used_but_never_stored_or_returned(real_client, db, monkeypatch):
    seen = {}

    def fake_openai(key, timeout):
        seen["key"] = key
        return OpenAIProvider(key, transport=_transport(200, OPENAI_OK))

    monkeypatch.setattr(registry_module, "OpenAIProvider", fake_openai)
    r = real_client.post(
        "/api/generate",
        json={"prompt": "hello", "provider": "openai", "model": "gpt-4.1-mini"},
        headers={"X-Provider-Api-Key": KEY},
    )
    assert r.status_code == 200 and seen["key"] == KEY
    assert KEY not in r.text
    dump = " ".join(str(d) for col in db.list_collection_names() for d in db[col].find({}))
    assert KEY not in dump


def test_server_key_used_when_user_key_absent(settings, db, monkeypatch):
    from app.core.config import Settings
    from app.main import create_app
    from fastapi.testclient import TestClient

    seen = {}

    def fake_openai(key, timeout):
        seen["key"] = key
        return OpenAIProvider(key, transport=_transport(200, OPENAI_OK))

    monkeypatch.setattr(registry_module, "OpenAIProvider", fake_openai)
    cfg = Settings(_env_file=None, llm_provider="openai", openai_api_key="server-side")
    with TestClient(create_app(settings=cfg, db=db)) as c:
        assert c.post("/api/generate", json={"prompt": "x"}).status_code == 200
        assert seen["key"] == "server-side"
        c.post("/api/generate", json={"prompt": "x"}, headers={"X-Provider-Api-Key": "mine-123"})
        assert seen["key"] == "mine-123"


def test_malformed_key_header_rejected(real_client):
    r = real_client.post("/api/generate", json={"prompt": "x", "provider": "openai"},
                         headers={"X-Provider-Api-Key": "has space inside"})
    assert r.status_code == 422


def test_parameter_validation_per_provider(real_client):
    h = {"X-Provider-Api-Key": "k"}
    r = real_client.post("/api/generate", headers=h, json={
        "prompt": "x", "provider": "anthropic", "model": "claude-haiku-5-5", "temperature": 1.5})
    assert r.status_code == 422 and "between 0 and 1" in r.json()["error"]["message"]


def test_top_p_is_gone(client):
    r = client.post("/api/generate", json={"prompt": "x", "top_p": 0.5})
    assert r.status_code == 200  # unknown field ignored, never forwarded
    assert "top_p" not in client.get("/openapi.json").text
