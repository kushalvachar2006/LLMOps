from datetime import UTC, datetime, timedelta

import pytest
from app.core.redaction import redact

from tests.conftest import ScriptedProvider

NOW = datetime.now(UTC).replace(microsecond=0)


def seed(db, n=1, *, days_ago=1.0, status="success", latency=100.0, provider="openai",
         model="gpt-4.1-mini", project_id="p1", tokens=(10, 20), prompt=None, evaluations=None,
         prompt_chars=50, idx=0):
    """Insert deterministic request traces directly (what the pipeline would have written)."""
    docs = []
    for i in range(n):
        docs.append({
            "request_id": f"r{idx}-{days_ago}-{provider}-{model}-{status}-{i}-{id(docs)}",
            "created_at": NOW - timedelta(days=days_ago, minutes=i),
            "project_id": project_id, "provider": provider, "model": model, "status": status,
            "error_category": None if status == "success" else "rate_limited",
            "latency_ms": latency if not callable(latency) else latency(i),
            "input_tokens": tokens[0] if tokens else None,
            "output_tokens": tokens[1] if tokens else None,
            "total_tokens": sum(tokens) if tokens else None,
            "prompt_chars": prompt_chars, "response_chars": 10, "temperature": 0.7,
            "max_output_tokens": 100, "retry_count": 0, "deployment_id": None,
            "prompt_id": prompt[0] if prompt else None,
            "prompt_version": prompt[1] if prompt else None,
            "evaluations": evaluations or [],
        })
    db["requests"].insert_many(docs)
    return docs


def get(client, path, **params):
    return client.get(f"/api/monitoring/{path}", params=params)


def test_empty_state_is_honest_not_fabricated(client):
    s = get(client, "summary").json()
    assert s["empty"] is True and s["total"] == 0
    assert s["error_rate"] is None and s["latency"] is None and s["tokens"] is None
    assert s["cost"]["totals_by_currency"] == {} and s["cost"]["by_model"] == []
    assert get(client, "timeseries").json()["points"] == []
    assert get(client, "breakdown").json() == {"models": [], "prompt_versions": []}
    assert get(client, "quality").json()["series"] == []
    assert get(client, "alerts").json()["alerts"] == []


def test_summary_numbers_come_from_records(client, db):
    seed(db, 8, latency=lambda i: 100.0 * (i + 1), tokens=(10, 20))
    seed(db, 2, status="error", latency=None, tokens=None, idx=1)
    s = get(client, "summary").json()
    assert (s["total"], s["success"], s["failed"]) == (10, 8, 2)
    assert s["error_rate"] == 0.2
    assert s["latency"]["avg_ms"] == 450.0  # failed rows have no latency and are not averaged
    assert s["latency"]["p50_ms"] == 400.0 and s["latency"]["p95_ms"] == 800.0
    assert s["tokens"]["input"] == 80 and s["tokens"]["output"] == 160
    assert s["tokens"]["requests_with_usage"] == 8 and s["tokens"]["requests_without_usage"] == 2


def test_percentiles_are_exact_nearest_rank(client, db):
    seed(db, 10, latency=lambda i: 100.0 * (i + 1))
    lat = get(client, "summary").json()["latency"]
    assert (lat["p50_ms"], lat["p95_ms"], lat["p99_ms"]) == (500.0, 1000.0, 1000.0)


def test_filters_date_project_provider_model(client, db):
    seed(db, 3, days_ago=1, project_id="p1")
    seed(db, 2, days_ago=20, project_id="p1", idx=1)  # outside the default 7-day window
    seed(db, 4, days_ago=1, project_id="p2", provider="gemini", model="gemini-2.5-flash", idx=2)
    assert get(client, "summary").json()["total"] == 7
    assert get(client, "summary", project_id="p1").json()["total"] == 3
    assert get(client, "summary", provider="gemini").json()["total"] == 4
    assert get(client, "summary", model="gpt-4.1-mini").json()["total"] == 3
    start = (NOW - timedelta(days=30)).isoformat()
    assert get(client, "summary", start=start, project_id="p1").json()["total"] == 5
    assert get(client, "summary", start=NOW.isoformat(), end=(NOW - timedelta(days=1)).isoformat()
               ).status_code == 422
    assert get(client, "summary", start=(NOW - timedelta(days=900)).isoformat()).status_code == 422


def test_timeseries_has_only_real_buckets(client, db):
    seed(db, 3, days_ago=1)
    seed(db, 1, days_ago=1, status="error", idx=1)
    seed(db, 2, days_ago=3, idx=2)
    pts = get(client, "timeseries", granularity="day").json()["points"]
    assert [p["requests"] for p in pts] == [2, 4]  # day -3 then day -1, nothing invented for day -2
    assert pts[1]["failed"] == 1 and pts[1]["error_rate"] == 0.25
    hourly = get(client, "timeseries", granularity="hour").json()
    assert hourly["granularity"] == "hour" and sum(p["requests"] for p in hourly["points"]) == 6
    assert get(client, "timeseries", granularity="week").status_code == 422


def test_breakdown_by_model_and_prompt_version(client, db):
    pr = client.post("/api/projects", json={"name": "P"}).json()
    prompt = client.post("/api/prompts", json={
        "project_id": pr["id"], "name": "Summ", "template": "{{x}}", "provider": "mock",
        "model": "mock-model"}).json()["prompt"]["id"]
    seed(db, 4, prompt=(prompt, 1), latency=100.0)
    seed(db, 2, prompt=(prompt, 2), latency=300.0, status="error", idx=1)
    seed(db, 3, model="gpt-4.1", idx=2)
    out = get(client, "breakdown").json()
    models = {m["model"]: m for m in out["models"]}
    assert models["gpt-4.1-mini"]["requests"] == 6 and models["gpt-4.1"]["requests"] == 3
    v = {x["prompt_version"]: x for x in out["prompt_versions"]}
    assert v[1]["prompt"] == "Summ" and v[1]["requests"] == 4 and v[2]["error_rate"] == 1.0


# ---------------- cost ----------------
def _price(client, **kw):
    body = {"provider": "openai", "model": "gpt-4.1-mini", "effective_from": "2020-01-01",
            "input_price": 2.0, "output_price": 8.0, "currency": "USD", "unit": "per_1M_tokens",
            **kw}
    return client.post("/api/pricing", json=body)


def test_cost_is_unavailable_without_pricing_and_never_invented(client, db):
    seed(db, 5, tokens=(1000, 2000))
    cost = get(client, "summary").json()["cost"]
    assert cost["totals_by_currency"] == {} and cost["complete"] is False
    row = cost["by_model"][0]
    assert row["status"] == "no_pricing" and row["cost"] is None
    assert row["input_tokens"] == 5000  # tokens are still reported


def test_cost_calculation_per_million_and_per_thousand(client, db):
    seed(db, 5, tokens=(1000, 2000))
    assert _price(client).status_code == 201
    cost = get(client, "summary").json()["cost"]
    # 5 * (1000*2 + 2000*8) / 1e6 = 0.09
    assert cost["totals_by_currency"] == {"USD": pytest.approx(0.09)}
    assert cost["by_model"][0]["status"] == "estimated" and cost["complete"] is True


def test_cost_unit_per_1k(client, db):
    seed(db, 1, tokens=(1000, 1000))
    _price(client, unit="per_1K_tokens", input_price=0.001, output_price=0.002)
    assert get(client, "summary").json()["cost"]["totals_by_currency"]["USD"] == pytest.approx(0.003)


def test_price_effective_date_applies_only_from_that_day(client, db):
    seed(db, 2, days_ago=5, tokens=(1_000_000, 0))
    seed(db, 2, days_ago=1, tokens=(1_000_000, 0), idx=1)
    _price(client, effective_from=(NOW - timedelta(days=3)).date().isoformat(),
           input_price=1.0, output_price=0.0)
    row = get(client, "summary").json()["cost"]["by_model"][0]
    assert row["status"] == "partial" and row["cost"] == pytest.approx(2.0)
    assert row["priced_requests"] == 2 and row["unpriced_requests"] == 2


def test_requests_without_token_usage_are_excluded_from_cost(client, db):
    seed(db, 2, tokens=(1_000_000, 0))
    seed(db, 3, tokens=None, idx=1)
    _price(client, input_price=1.0, output_price=0.0)
    row = get(client, "summary").json()["cost"]["by_model"][0]
    assert row["cost"] == pytest.approx(2.0) and row["no_usage_requests"] == 3
    assert row["status"] == "partial"


def test_pricing_validation_duplicates_and_delete(client):
    assert _price(client, effective_from="not-a-date").status_code == 422
    assert _price(client, unit="per_banana").status_code == 422
    assert _price(client, input_price=-1).status_code == 422
    pid = _price(client).json()["id"]
    assert _price(client).status_code == 409
    assert len(client.get("/api/pricing").json()) == 1
    assert client.delete(f"/api/pricing/{pid}").status_code == 204
    assert client.delete(f"/api/pricing/{pid}").status_code == 404


def test_mixed_currencies_are_not_summed(client, db):
    seed(db, 1, days_ago=5, tokens=(1_000_000, 0))
    seed(db, 1, days_ago=1, tokens=(1_000_000, 0), idx=1)
    _price(client, effective_from="2020-01-01", currency="USD", input_price=1.0, output_price=0)
    _price(client, effective_from=(NOW - timedelta(days=3)).date().isoformat(), currency="EUR",
           input_price=1.0, output_price=0)
    row = get(client, "summary").json()["cost"]["by_model"][0]
    assert row["status"] == "mixed_currency" and row["cost"] is None


# ---------------- quality + alerts ----------------
def ev(name, type_, score, passed, kind="objective"):
    return {"name": name, "type": type_, "kind": kind, "score": score, "passed": passed}


def test_quality_series_and_version_regression_alert(client, db):
    seed(db, 6, prompt=("pa", 1), evaluations=[ev("exact_match", "exact_match", 1.0, True)])
    seed(db, 6, prompt=("pa", 2), idx=1, evaluations=[ev("exact_match", "exact_match", 0.0, False)])
    q = get(client, "quality").json()
    assert q["series"][0]["metric"] == "exact_match" and q["series"][0]["n_scored"] == 12
    assert q["series"][0]["mean_score"] == 0.5
    by_v = {r["prompt_version"]: r for r in q["by_prompt_version"]}
    assert by_v[1]["mean_score"] == 1.0 and by_v[2]["mean_score"] == 0.0
    alerts = get(client, "alerts").json()["alerts"]
    reg = [a for a in alerts if a["type"] == "quality_regression"]
    assert len(reg) == 1 and "v1 scored 1.00" in reg[0]["message"]
    assert "different test data" in reg[0]["message"]


def test_regression_needs_enough_samples(client, db):
    seed(db, 2, prompt=("pa", 1), evaluations=[ev("exact_match", "exact_match", 1.0, True)])
    seed(db, 2, prompt=("pa", 2), idx=1, evaluations=[ev("exact_match", "exact_match", 0.0, False)])
    assert not [a for a in get(client, "alerts").json()["alerts"] if a["type"] == "quality_regression"]


def test_judge_scores_are_normalised_before_comparison(client, db):
    j = lambda s: [ev("llm_judge", "llm_judge", float(s), s >= 4, "model_judgment")]  # noqa: E731
    seed(db, 6, prompt=("pa", 1), evaluations=j(5))
    seed(db, 6, prompt=("pa", 2), idx=1, evaluations=j(1))
    reg = [a for a in get(client, "alerts").json()["alerts"] if a["type"] == "quality_regression"]
    assert reg and reg[0]["evidence"]["kind"] == "model_judgment"
    assert "v1 scored 1.00 and v2 scored 0.00" in reg[0]["message"]


def test_format_failure_alert(client, db):
    seed(db, 4, prompt=("pj", 1), evaluations=[ev("json_valid", "json_valid", 0.0, False)])
    seed(db, 4, prompt=("pj", 1), idx=1, evaluations=[ev("json_valid", "json_valid", 1.0, True)])
    alerts = get(client, "alerts").json()["alerts"]
    fmt = [a for a in alerts if a["type"] == "format_failure"]
    assert fmt and "50%" in fmt[0]["message"]


def test_error_rate_alert_respects_min_requests_and_thresholds(client, db):
    seed(db, 8, status="error", latency=None, tokens=None)
    seed(db, 2, idx=1)
    assert get(client, "alerts").json()["alerts"] == []  # only 10 requests; min is 20
    client.put("/api/monitoring/thresholds", json={"min_requests": 5, "error_rate_max": 0.5})
    types = [a["type"] for a in get(client, "alerts").json()["alerts"]]
    assert "error_rate" in types
    client.put("/api/monitoring/thresholds", json={"min_requests": 5, "error_rate_max": 0.9})
    assert "error_rate" not in [a["type"] for a in get(client, "alerts").json()["alerts"]]
    assert client.put("/api/monitoring/thresholds", json={"error_rate_max": 5}).status_code == 422
    assert client.get("/api/monitoring/thresholds").json()["error_rate_max"] == 0.9


def test_latency_alert_only_when_threshold_configured(client, db):
    seed(db, 25, latency=5000.0)
    assert "latency_p95" not in [a["type"] for a in get(client, "alerts").json()["alerts"]]
    client.put("/api/monitoring/thresholds", json={"latency_p95_ms_max": 1000})
    assert "latency_p95" in [a["type"] for a in get(client, "alerts").json()["alerts"]]


def test_input_length_change_uses_careful_wording(client, db):
    seed(db, 25, days_ago=10, prompt_chars=100)               # previous period
    seed(db, 25, days_ago=1, prompt_chars=400, idx=1)         # current period
    start = (NOW - timedelta(days=7)).isoformat()
    alerts = get(client, "alerts", start=start).json()["alerts"]
    shift = [a for a in alerts if a["type"] == "input_length_change"]
    assert shift and shift[0]["severity"] == "info"
    assert "not proof of harmful data drift" in shift[0]["message"]


# ---------------- feedback ----------------
def test_feedback_is_linked_to_request_project_and_prompt_version(client, make_client, db):
    with make_client(provider=ScriptedProvider({}, "ok")) as c:
        proj = c.post("/api/projects", json={"name": "FB"}).json()["id"]
        rid = c.post("/api/generate", json={"prompt": "hi", "project_id": proj}).json()["request_id"]
        r = c.post("/api/feedback", json={"request_id": rid, "rating": 4, "comment": "good"})
        assert r.status_code == 201
        fb = r.json()
        assert fb["project_id"] == proj and fb["rating"] == 4 and fb["model"] == "mock-model"
        # rating again replaces, not duplicates
        c.post("/api/feedback", json={"request_id": rid, "rating": 2})
        assert db["feedback"].count_documents({}) == 1
        s = c.get("/api/monitoring/summary", params={"project_id": proj}).json()
        assert s["feedback"]["count"] == 1 and s["feedback"]["avg_rating"] == 2.0


def test_feedback_validation_and_redaction(client, db):
    assert client.post("/api/feedback", json={"request_id": "ghost", "rating": 3}).status_code == 404
    docs = seed(db, 1)
    rid = docs[0]["request_id"]
    assert client.post("/api/feedback", json={"request_id": rid, "rating": 9}).status_code == 422
    r = client.post("/api/feedback", json={
        "request_id": rid, "rating": 1, "comment": "mail me at jane.doe@example.com or +1 415 555 0100"})
    assert "jane.doe@example.com" not in r.json()["comment"]
    assert "[email]" in r.json()["comment"] and "[phone]" in r.json()["comment"]


def test_low_rating_alert(client, db):
    for i in range(6):
        rid = seed(db, 1, idx=i)[0]["request_id"]
        client.post("/api/feedback", json={"request_id": rid, "rating": 1})
    assert "feedback" in [a["type"] for a in get(client, "alerts").json()["alerts"]]


# ---------------- privacy, retention, trace fields ----------------
def test_redaction_patterns():
    text = "Contact a@b.com, key sk-abcdefghijklmnop1234, card 4111 1111 1111 1111, Bearer abcdefgh12345"
    out = redact(text)
    for secret in ("a@b.com", "sk-abcdefghijklmnop1234", "4111 1111 1111 1111", "abcdefgh12345"):
        assert secret not in out
    assert redact("plain text") == "plain text" and redact(None) is None
    assert redact("a@b.com", enabled=False) == "a@b.com"


def test_stored_prompt_text_is_redacted_when_storage_enabled(make_client, db):
    from app.core.config import Settings

    cfg = Settings(_env_file=None, llm_provider="mock", store_prompt_text=True)
    with make_client(cfg=cfg) as c:
        rid = c.post("/api/generate", json={"prompt": "email bob@corp.io please"}).json()["request_id"]
    doc = db["requests"].find_one({"request_id": rid})
    assert "bob@corp.io" not in doc["prompt_text"] and "[email]" in doc["prompt_text"]


def test_trace_has_phase3_fields_and_no_secrets(real_client, db):
    c = real_client
    rid = c.post("/api/generate", json={"prompt": "hello", "provider": "mock"}).json()["request_id"]
    doc = db["requests"].find_one({"request_id": rid})
    for field in ("request_id", "created_at", "project_id", "deployment_id", "provider", "model",
                  "prompt_id", "prompt_version", "status", "input_tokens", "output_tokens",
                  "latency_ms", "retry_count", "error_category", "evaluations"):
        assert field in doc
    assert doc["retry_count"] == 0 and doc["deployment_id"] is None
    assert not any("key" in k.lower() or "authorization" in k.lower() for k in doc)


def test_policy_and_retention_index(settings, db):
    from app.core.config import Settings
    from app.main import create_app
    from fastapi.testclient import TestClient

    cfg = Settings(_env_file=None, llm_provider="mock", trace_retention_days=30)
    with TestClient(create_app(settings=cfg, db=db, provider=ScriptedProvider())) as c:
        p = c.get("/api/monitoring/policy").json()
        assert p["retention_days"] == 30 and p["redaction_enabled"] is True
        assert "not captured" in p["streaming_first_token_time"]
    info = db["requests"].index_information()
    assert info["requests_ttl"]["expireAfterSeconds"] == 30 * 86400
    assert db["feedback"].index_information()["feedback_ttl"]["expireAfterSeconds"] == 30 * 86400


def test_experiment_scores_flow_into_quality_monitoring(make_client):
    qa = "question,answer\nCapital of France?,Paris\nCapital of Spain?,Madrid\n"
    with make_client(provider=ScriptedProvider({"France": "Paris", "Spain": "Barcelona"})) as c:
        proj = c.post("/api/projects", json={"name": "Q"}).json()["id"]
        pr = c.post("/api/prompts", json={"project_id": proj, "name": "p", "template": "{{question}}",
                    "provider": "mock", "model": "mock-model"}).json()["prompt"]["id"]
        ds = c.post("/api/datasets", json={"project_id": proj, "name": "d", "filename": "d.csv",
                    "content": qa}).json()["dataset"]["id"]
        c.post("/api/experiments", json={"project_id": proj, "name": "e", "prompt_id": pr,
               "dataset_id": ds, "reference_field": "answer", "evaluators": [{"type": "exact_match"}]})
        q = c.get("/api/monitoring/quality", params={"project_id": proj}).json()
        assert q["series"][0]["metric"] == "exact_match" and q["series"][0]["mean_score"] == 0.5
        assert q["by_prompt_version"][0]["prompt"] == "p"
        b = c.get("/api/monitoring/breakdown", params={"project_id": proj}).json()
        assert b["prompt_versions"][0]["requests"] == 2
