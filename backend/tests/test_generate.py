from app.core.errors import ProviderAuthError, ProviderRateLimitError, ProviderTimeoutError
from app.repositories.request_repository import RequestRepository
from app.services.providers.mock import MockProvider


def test_generate_success_returns_text_and_usage(client):
    r = client.post("/api/generate", json={"prompt": "hello brave new world"})
    assert r.status_code == 200
    body = r.json()
    assert body["text"].startswith("[mock reply]")
    assert body["provider"] == "mock"
    assert body["usage"]["input_tokens"] == 4
    assert body["latency_ms"] >= 0
    assert body["telemetry_recorded"] is True
    assert len(body["request_id"]) == 32


def test_telemetry_is_persisted(client, db):
    rid = client.post("/api/generate", json={"prompt": "hi there"}).json()["request_id"]
    doc = db["requests"].find_one({"request_id": rid})
    assert doc["status"] == "success"
    assert doc["prompt_chars"] == len("hi there")
    assert doc["total_tokens"] is not None


def test_prompt_text_not_stored_by_default(client, db):
    rid = client.post("/api/generate", json={"prompt": "my secret prompt"}).json()["request_id"]
    doc = db["requests"].find_one({"request_id": rid})
    assert "prompt_text" not in doc and "response_text" not in doc


def test_prompt_text_stored_only_when_enabled(make_client, db):
    from app.core.config import Settings

    cfg = Settings(_env_file=None, llm_provider="mock", store_prompt_text=True)
    with make_client(cfg=cfg) as c:
        rid = c.post("/api/generate", json={"prompt": "keep me"}).json()["request_id"]
    assert db["requests"].find_one({"request_id": rid})["prompt_text"] == "keep me"


def test_telemetry_listing_and_project_filter(client):
    pid = client.post("/api/projects", json={"name": "P"}).json()["id"]
    client.post("/api/generate", json={"prompt": "a", "project_id": pid})
    client.post("/api/generate", json={"prompt": "b"})
    assert client.get("/api/requests").json()["total"] == 2
    assert client.get("/api/requests", params={"project_id": pid}).json()["total"] == 1


def test_unknown_project_rejected_before_calling_model(client, db):
    r = client.post("/api/generate", json={"prompt": "x", "project_id": "ghost"})
    assert r.status_code == 404
    assert db["requests"].count_documents({}) == 0


def test_invalid_parameters_rejected(client):
    assert client.post("/api/generate", json={"prompt": ""}).status_code == 422
    assert client.post("/api/generate", json={"prompt": "x", "temperature": 5}).status_code == 422
    bad = {"prompt": "x", "max_output_tokens": 0}
    assert client.post("/api/generate", json=bad).status_code == 422


def test_rate_limit_maps_to_429_and_is_recorded(make_client, db):
    provider = MockProvider(fail_with=ProviderRateLimitError("quota hit"))
    with make_client(provider=provider) as c:
        r = c.post("/api/generate", json={"prompt": "x"})
    assert r.status_code == 429
    assert r.json()["error"]["category"] == "rate_limited"
    doc = db["requests"].find_one({})
    assert doc["status"] == "error" and doc["error_category"] == "rate_limited"
    assert doc["total_tokens"] is None


def test_timeout_and_auth_status_codes(make_client):
    with make_client(provider=MockProvider(fail_with=ProviderTimeoutError("t"))) as c:
        assert c.post("/api/generate", json={"prompt": "x"}).status_code == 504
    with make_client(provider=MockProvider(fail_with=ProviderAuthError("a"))) as c:
        assert c.post("/api/generate", json={"prompt": "x"}).status_code == 502


def test_telemetry_failure_does_not_fail_inference(client, monkeypatch):
    def boom(self, record):
        raise RuntimeError("db write failed")

    monkeypatch.setattr(RequestRepository, "insert", boom)
    r = client.post("/api/generate", json={"prompt": "still works"})
    assert r.status_code == 200
    assert r.json()["telemetry_recorded"] is False
    assert r.json()["text"]


def test_unexpected_error_does_not_leak_details(settings, db):
    from app.main import create_app
    from fastapi.testclient import TestClient

    class Exploding(MockProvider):
        def generate(self, params):
            raise ValueError("api_key=SECRET-KEY-VALUE")

    app = create_app(settings=settings, db=db, provider=Exploding())
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.post("/api/generate", json={"prompt": "x"})
    assert r.status_code == 500
    assert r.json()["error"]["category"] == "internal_error"
    assert "SECRET-KEY-VALUE" not in r.text
