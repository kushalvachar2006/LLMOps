import json
import time
from types import SimpleNamespace

import pytest
from app.core.errors import (
    MissingApiKeyError,
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.core.security import generate_api_key, hash_secret, parse_token, verify_secret

from tests.conftest import ScriptedProvider


@pytest.fixture
def env(make_client):
    provider = ScriptedProvider(default="Hello!")
    with make_client(provider=provider) as c:
        proj = c.post("/api/projects", json={"name": "P"}).json()["id"]
        prompt = c.post("/api/prompts", json={
            "project_id": proj, "name": "greet", "template": "Say hi to {{name}}",
            "system_instruction": "Be kind", "provider": "mock", "model": "mock-model",
            "temperature": 0.3, "max_output_tokens": 50}).json()["prompt"]["id"]
        dep = c.post("/api/deployments", json={"project_id": proj, "name": "Greeter"}).json()["id"]
        yield SimpleNamespace(c=c, provider=provider, project=proj, prompt=prompt, dep=dep)


def publish(e, **body):
    return e.c.post(f"/api/deployments/{e.dep}/versions", json={"prompt_id": e.prompt, **body})


def promote(e, version=1, environment="production"):
    return e.c.post(f"/api/deployments/{e.dep}/promote",
                    json={"version": version, "environment": environment})


def go_live(e, environment="production"):
    assert publish(e).json()["status"] == "ready"
    assert promote(e, 1, environment).status_code == 200


def make_key(e, **kw):
    body = {"project_id": e.project, "name": "k", "environments": ["production"], **kw}
    r = e.c.post("/api/api-keys", json=body)
    assert r.status_code == 201, r.text
    return r.json()["secret"]


def invoke(e, key, inputs=None, dep=None, environment=None, headers=None, **extra):
    body = {"inputs": {"name": "Ada"} if inputs is None else inputs, **extra}
    if environment:
        body["environment"] = environment
    h = {"Authorization": f"Bearer {key}"} if key else {}
    return e.c.post(f"/v1/deployments/{dep or e.dep}/invoke", json=body, headers={**h, **(headers or {})})


# ---------------- deployments + validation gate ----------------
def test_create_deployment_and_conflicts(env):
    d = env.c.get(f"/api/deployments/{env.dep}").json()
    assert d["status"] == "inactive" and d["environments"] == {
        "development": None, "staging": None, "production": None}
    dup = {"project_id": env.project, "name": "greeter"}
    assert env.c.post("/api/deployments", json=dup).status_code == 409
    assert env.c.post("/api/deployments", json={"project_id": "ghost", "name": "x"}).status_code == 404


def test_publish_runs_checks_and_marks_ready(env):
    r = publish(env)
    assert r.status_code == 201
    v = r.json()
    assert v["status"] == "ready" and v["version"] == 1 and v["prompt_version"] == 1
    assert v["health"]["status"] == "healthy" and v["variables"] == ["name"]
    names = [c["name"] for c in v["validation_report"]["checks"]]
    assert names == ["model_configuration", "sample_inputs", "model_call", "non_empty_output"]
    assert all(c["passed"] for c in v["validation_report"]["checks"])
    assert v["config"]["model"] == "mock-model" and v["config"]["temperature"] == 0.3
    assert env.provider.calls[0].prompt == "Say hi to sample name"  # default synthetic sample


def test_failed_validation_blocks_the_version_from_going_live(env):
    env.provider.fail = ProviderTimeoutError("vendor said: secret detail")
    v = publish(env).json()
    assert v["status"] == "failed" and v["health"]["status"] == "unhealthy"
    call = next(c for c in v["validation_report"]["checks"] if c["name"] == "model_call")
    assert call["passed"] is False and "secret detail" not in json.dumps(v)
    r = promote(env)
    assert r.status_code == 409 and "validation passed" in r.json()["error"]["message"]
    assert env.c.get(f"/api/deployments/{env.dep}").json()["status"] == "inactive"


def test_sample_inputs_must_match_the_template_and_skip_the_model(env):
    v = publish(env, validation={"sample_inputs": [{"wrong": "x"}]}).json()
    assert v["status"] == "failed" and env.provider.calls == []


def test_json_and_length_checks(env):
    env.provider.default = "not json"
    assert publish(env, validation={"expect_json": True}).json()["status"] == "failed"
    env.provider.default = '{"ok": true}'
    assert publish(env, validation={"expect_json": True}).json()["status"] == "ready"
    env.provider.default = "x" * 50
    assert publish(env, validation={"max_output_chars": 10}).json()["status"] == "failed"
    env.provider.default = "   "
    assert publish(env).json()["status"] == "failed"  # empty output


def test_publish_rejects_foreign_prompt_and_missing_credentials(env, real_client):
    other = env.c.post("/api/projects", json={"name": "Other"}).json()["id"]
    foreign = env.c.post("/api/prompts", json={
        "project_id": other, "name": "p", "template": "x", "provider": "mock",
        "model": "mock-model"}).json()["prompt"]["id"]
    r = env.c.post(f"/api/deployments/{env.dep}/versions", json={"prompt_id": foreign})
    assert r.status_code == 422
    # no model credentials at all: clear error and nothing is stored
    c = real_client
    pr = c.post("/api/projects", json={"name": "R"}).json()["id"]
    pid = c.post("/api/prompts", json={"project_id": pr, "name": "p", "template": "x",
                 "provider": "openai", "model": "gpt-4.1-mini"}).json()["prompt"]["id"]
    d = c.post("/api/deployments", json={"project_id": pr, "name": "D"}).json()["id"]
    r = c.post(f"/api/deployments/{d}/versions", json={"prompt_id": pid})
    assert r.status_code == 400 and r.json()["error"]["category"] == "missing_api_key"
    assert c.get(f"/api/deployments/{d}/versions").json() == []


def test_health_check_updates_health_and_gates_production(env):
    go_live(env)
    assert env.c.post(f"/api/deployments/{env.dep}/versions/1/health-check").json()["health"][
        "status"] == "healthy"
    env.provider.fail = ProviderRateLimitError("x")
    hc = env.c.post(f"/api/deployments/{env.dep}/versions/1/health-check").json()
    assert hc["health"]["status"] == "unhealthy" and hc["status"] == "ready"
    assert promote(env, 1, "production").status_code == 409  # unhealthy -> not to production
    assert promote(env, 1, "staging").status_code == 200  # but other environments are allowed
    assert env.c.post(f"/api/deployments/{env.dep}/versions/9/health-check").status_code == 404


def test_promote_rollback_unpublish_and_audit_trail(env):
    publish(env)
    publish(env, change_description="second")
    assert promote(env, 1).status_code == 200
    assert promote(env, 2).status_code == 200
    d = promote(env, 1).json()  # going back is a rollback
    assert d["environments"]["production"] == 1 and d["status"] == "active"
    assert promote(env, 5).status_code == 404
    assert env.c.post(f"/api/deployments/{env.dep}/promote",
                      json={"version": 1, "environment": "qa"}).status_code == 422
    kinds = [(e["type"], e["to_version"]) for e in env.c.get(f"/api/deployments/{env.dep}/events").json()]
    assert kinds == [("rollback", 1), ("promote", 2), ("promote", 1)]
    d = env.c.delete(f"/api/deployments/{env.dep}/environments/production").json()
    assert d["status"] == "inactive"
    assert env.c.delete(f"/api/deployments/{env.dep}/environments/production").status_code == 404


def test_versions_are_immutable_records(env):
    publish(env)
    publish(env)
    versions = env.c.get(f"/api/deployments/{env.dep}/versions").json()
    assert [v["version"] for v in versions] == [2, 1]
    before = env.c.get(f"/api/deployments/{env.dep}/versions").json()
    for method in ("put", "patch", "delete"):  # no endpoint exists to edit or remove a version
        r = getattr(env.c, method)(f"/api/deployments/{env.dep}/versions/1")
        assert r.status_code in (404, 405)
    assert env.c.get(f"/api/deployments/{env.dep}/versions").json() == before


# ---------------- API keys ----------------
def test_key_is_shown_once_and_only_a_hash_is_stored(env, db):
    r = env.c.post("/api/api-keys", json={"project_id": env.project, "name": "ci"})
    body = r.json()
    secret = body["secret"]
    assert r.headers["cache-control"] == "no-store"
    assert secret.startswith("llmops_") and "hash" not in body
    dump = " ".join(str(d) for d in db["api_keys"].find({}))
    secret_part = secret.split("_", 2)[2]
    assert secret not in dump and secret_part not in dump  # no plaintext anywhere
    stored = db["api_keys"].find_one({})
    assert len(stored["hash"]) == 64 and stored["hash"] != secret_part
    listing = env.c.get("/api/api-keys", params={"project_id": env.project}).json()
    assert len(listing) == 1 and "secret" not in listing[0] and "hash" not in listing[0]
    assert listing[0]["prefix"] == body["prefix"] and secret not in json.dumps(listing)
    assert secret_part not in json.dumps(env.c.post(
        f"/api/api-keys/{body['id']}/revoke").json())


def test_key_creation_validation(env):
    assert env.c.post("/api/api-keys", json={"project_id": "ghost", "name": "k"}).status_code == 404
    assert env.c.post("/api/api-keys", json={"project_id": env.project, "name": "k",
                                             "environments": ["qa"]}).status_code == 422
    assert env.c.post("/api/api-keys", json={"project_id": env.project, "name": "k",
                                             "rate_limit_per_minute": 999999}).status_code == 422
    assert env.c.post("/api/api-keys", json={"project_id": env.project, "name": ""}).status_code == 422


def test_revoked_key_stops_working_immediately(env):
    go_live(env)
    secret = make_key(env)
    assert invoke(env, secret).status_code == 200
    key_row = env.c.get("/api/api-keys", params={"project_id": env.project}).json()[0]
    r = env.c.post(f"/api/api-keys/{key_row['id']}/revoke")
    assert r.status_code == 200 and r.json()["revoked_at"]
    assert env.c.post(f"/api/api-keys/{key_row['id']}/revoke").status_code == 200  # idempotent
    assert invoke(env, secret).status_code == 401
    assert env.c.post("/api/api-keys/ghost/revoke").status_code == 404


def test_security_helpers():
    key_id, secret, token = generate_api_key()
    assert parse_token(token) == (key_id, secret) and len(secret) == 43
    assert parse_token("llmops_zz_abc") is None and parse_token(None) is None
    h = hash_secret(secret, "pepper")
    assert verify_secret(secret, "pepper", h)
    assert not verify_secret(secret, "other-pepper", h) and not verify_secret("x", "pepper", h)
    assert generate_api_key()[2] != token


# ---------------- invoking ----------------
def test_invoke_returns_output_usage_and_hides_internals(env, db):
    go_live(env)
    secret = make_key(env)
    r = invoke(env, secret, {"name": "Ada"})
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["output"] == "Hello!" and body["version"] == 1 and body["environment"] == "production"
    assert body["usage"]["total_tokens"] == 8 and body["latency_ms"] >= 0
    text = r.text
    for hidden in ("Say hi", "Be kind", "mock-model", "temperature", "template", "system"):
        assert hidden not in text
    assert env.provider.calls[-1].prompt == "Say hi to Ada"
    assert env.provider.calls[-1].system_instruction == "Be kind"
    trace = db["requests"].find_one({"request_id": body["request_id"]})
    assert trace["deployment_id"] == env.dep and trace["deployment_version"] == 1
    assert trace["environment"] == "production" and trace["api_key_id"]
    assert trace["prompt_id"] == env.prompt and "Ada" not in str(trace)  # no text stored by default
    row = env.c.get("/api/api-keys", params={"project_id": env.project}).json()[0]
    assert row["request_count"] == 1 and row["last_used_at"]


def test_authentication_failures_are_uniform(env, db):
    go_live(env)
    secret = make_key(env)
    key_id, secret_part = parse_token(secret)
    wrong_secret = f"llmops_{key_id}_{'A' * 43}"
    unknown = f"llmops_{'0' * 12}_{secret_part}"
    messages = set()
    for hdrs in ({}, {"Authorization": "Bearer nonsense"}, {"Authorization": f"Bearer {wrong_secret}"},
                 {"Authorization": f"Bearer {unknown}"}, {"Authorization": "Basic abc"}):
        r = env.c.post(f"/v1/deployments/{env.dep}/invoke", json={"inputs": {"name": "x"}}, headers=hdrs)
        assert r.status_code == 401, hdrs
        messages.add(r.json()["error"]["message"])
    assert messages == {"Invalid or missing API key."}
    ok = env.c.post(f"/v1/deployments/{env.dep}/invoke", json={"inputs": {"name": "x"}},
                    headers={"X-API-Key": secret})
    assert ok.status_code == 200
    assert env.provider.calls[-1].prompt == "Say hi to x"


def test_keys_are_scoped_to_their_project_and_environment(env):
    go_live(env)
    other = env.c.post("/api/projects", json={"name": "Other"}).json()["id"]
    foreign = env.c.post("/api/api-keys", json={"project_id": other, "name": "f"}).json()["secret"]
    r = invoke(env, foreign)
    assert r.status_code == 404 and r.json()["error"]["message"] == "Deployment not found."
    assert invoke(env, make_key(env), dep="no-such-id").status_code == 404  # same answer
    prod_only = make_key(env)
    assert invoke(env, prod_only, environment="staging").status_code == 403
    both = make_key(env, environments=["production", "staging"])
    r = invoke(env, both, environment="staging")
    assert r.status_code == 404 and "No version is live" in r.json()["error"]["message"]
    assert invoke(env, both, environment="qa").status_code == 422


def test_input_validation(env):
    go_live(env)
    k = make_key(env)
    secret_looking = "SUPER-PRIVATE-VALUE"
    cases = [
        ({}, "Missing input"),
        ({"name": "a", "extra": "b"}, "Unknown input"),
        ({"name": {"nested": secret_looking}}, "Invalid request"),
        ({"name": [secret_looking]}, "Invalid request"),
        ({"name": None}, "Invalid request"),
        ({"bad-name!": "x"}, "Invalid request"),
        ({"name": "x" * 10_001}, "limited to 10,000"),
    ]
    for inputs, expected in cases:
        r = invoke(env, k, inputs)
        assert r.status_code == 422, inputs
        assert expected in r.json()["error"]["message"]
        assert secret_looking not in r.text  # values are never echoed back
    assert invoke(env, k, {"name": "ok"}, unexpected_field=1).status_code == 422
    for raw in (b"not json", b"[1,2]", b'"str"'):
        r = env.c.post(f"/v1/deployments/{env.dep}/invoke", content=raw,
                       headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"})
        assert r.status_code == 422
    assert invoke(env, k, {"name": 5}).status_code == 200  # numbers are accepted and stringified


def test_user_input_cannot_inject_template_fields(env):
    go_live(env)
    k = make_key(env)
    invoke(env, k, {"name": "{{name}} {{secret}}"})
    assert env.provider.calls[-1].prompt == "Say hi to {{name}} {{secret}}"  # inserted literally


def test_request_size_limit(env):
    go_live(env)
    k = make_key(env)
    big = {"inputs": {"name": "x" * 40_000}}
    r = env.c.post(f"/v1/deployments/{env.dep}/invoke", json=big,
                   headers={"Authorization": f"Bearer {k}"})
    assert r.status_code == 413 and r.json()["error"]["category"] == "payload_too_large"

    def chunks():  # no Content-Length: the limit must still hold while streaming
        for _ in range(10):
            yield b"x" * 5000
    r = env.c.post(f"/v1/deployments/{env.dep}/invoke", content=chunks(),
                   headers={"Authorization": f"Bearer {k}"})
    assert r.status_code == 413


def test_rate_limit_per_key_with_retry_after_and_window_reset(env):
    go_live(env)
    now = [(time.time() // 60) * 60 + 10]  # 10 s into a real minute (TTL emulation needs real dates)
    env.c.app.state.clock = lambda: now[0]
    limited = make_key(env, rate_limit_per_minute=3)
    other = make_key(env, rate_limit_per_minute=3)
    assert [invoke(env, limited).status_code for _ in range(3)] == [200, 200, 200]
    r = invoke(env, limited)
    assert r.status_code == 429 and r.json()["error"]["category"] == "rate_limited"
    assert 1 <= int(r.headers["retry-after"]) <= 60
    assert invoke(env, other).status_code == 200  # another key is unaffected
    now[0] += 61  # next window
    assert invoke(env, limited).status_code == 200


def test_provider_failures_become_safe_generic_errors(env, db):
    go_live(env)
    k = make_key(env)
    expectations = [
        (ProviderTimeoutError("vendor secret sk-live-123"), 504, "upstream_timeout"),
        (ProviderRateLimitError("quota for org-XYZ"), 503, "service_unavailable"),
        (ProviderAuthError("bad key sk-live-123"), 503, "service_unavailable"),
        (ProviderBadRequestError("model gpt-secret not found"), 502, "upstream_error"),
        (MissingApiKeyError("no key configured for openai"), 503, "service_unavailable"),
    ]
    for exc, status, category in expectations:
        env.provider.fail = exc
        r = invoke(env, k)
        assert (r.status_code, r.json()["error"]["category"]) == (status, category), exc
        for leaked in ("sk-live-123", "org-XYZ", "gpt-secret", "openai", "vendor"):
            assert leaked not in r.text
    env.provider.fail = ProviderTimeoutError("x")
    err = invoke(env, k).json()["error"]
    assert len(err["request_id"]) == 32
    assert db["requests"].find_one({"request_id": err["request_id"]})["status"] == "error"
    env.provider.fail = None
    assert invoke(env, k).status_code == 200


def test_callers_cannot_supply_their_own_model_key(env):
    go_live(env)
    k = make_key(env)
    r = invoke(env, k, headers={"X-Provider-Api-Key": "sk-attacker-key"})
    assert r.status_code == 200 and "sk-attacker-key" not in r.text


def test_deployment_usage_tracking(env):
    go_live(env)
    k = make_key(env)
    for _ in range(3):
        invoke(env, k)
    env.provider.fail = ProviderTimeoutError("x")
    invoke(env, k)
    env.provider.fail = None
    u = env.c.get(f"/api/deployments/{env.dep}/usage").json()
    assert u["total"] == 4 and u["failed"] == 1 and u["error_rate"] == 0.25  # probes excluded
    assert u["by_environment"][0]["environment"] == "production"
    assert u["by_version"][0]["version"] == 1 and u["by_api_key"][0]["requests"] == 4
    assert env.c.get("/api/requests", params={"limit": 100}).json()["total"] >= 5
    assert env.c.get("/api/deployments/ghost/usage").status_code == 404


def test_empty_usage_is_reported_as_empty(env):
    assert env.c.get(f"/api/deployments/{env.dep}/usage").json()["empty"] is True


# ---------------- management API protection + production hardening ----------------
def test_admin_token_protects_management_api_but_not_health_or_keys(make_client, settings):
    from app.core.config import Settings

    cfg = Settings(_env_file=None, llm_provider="mock", admin_token="s3cret-admin")
    with make_client(cfg=cfg, provider=ScriptedProvider(default="ok")) as c:
        assert c.get("/health").json()["admin_auth"] is True
        assert c.get("/api/projects").status_code == 401
        assert c.get("/api/projects", headers={"X-Admin-Token": "wrong"}).status_code == 401
        assert c.get("/api/projects", headers={"X-Admin-Token": "s3cret-admin"}).status_code == 200
        assert c.post("/api/generate", json={"prompt": "x"}).status_code == 401
        r = c.post("/v1/deployments/x/invoke", json={"inputs": {}})
        assert r.status_code == 401 and r.json()["error"]["message"] == "Invalid or missing API key."


def test_no_admin_token_means_open_local_development(client):
    assert client.get("/health").json()["admin_auth"] is False
    assert client.get("/api/projects").status_code == 200


def test_interactive_docs_are_disabled_in_production(make_client):
    from app.core.config import Settings

    cfg = Settings(_env_file=None, llm_provider="mock", app_env="production")
    with make_client(cfg=cfg) as c:
        assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404


def test_project_with_deployments_cannot_be_deleted(env):
    assert env.c.delete(f"/api/projects/{env.project}").status_code == 409
