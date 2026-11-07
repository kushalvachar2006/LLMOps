import pytest
from app.core.errors import ProviderAuthError, ProviderRateLimitError

from tests.conftest import ScriptedProvider

QA = "question,answer\nCapital of France?,Paris\nCapital of Italy?,Rome\nCapital of Spain?,Madrid\n"
ANSWERS = {"France": "Paris", "Italy": "Rome", "Spain": "Barcelona"}  # Spain is deliberately wrong


@pytest.fixture
def setup(make_client):
    """Returns (client, ids) with a project, one prompt (v1) and one dataset (v1)."""
    provider = ScriptedProvider(ANSWERS)
    with make_client(provider=provider) as c:
        proj = c.post("/api/projects", json={"name": "Geo"}).json()
        pr = c.post("/api/prompts", json={
            "project_id": proj["id"], "name": "Capital", "template": "Answer briefly: {{question}}",
            "provider": "mock", "model": "mock-model", "temperature": 0.2, "max_output_tokens": 50,
        }).json()
        ds = c.post("/api/datasets", json={
            "project_id": proj["id"], "name": "QA", "filename": "qa.csv", "content": QA}).json()
        yield c, {"project": proj["id"], "prompt": pr["prompt"]["id"], "dataset": ds["dataset"]["id"],
                  "provider": provider}


def _run(c, ids, **kw):
    body = {"project_id": ids["project"], "name": "run1", "prompt_id": ids["prompt"],
            "dataset_id": ids["dataset"], "reference_field": "answer",
            "evaluators": [{"type": "exact_match"}], **kw}
    return c.post("/api/experiments", json=body)


def test_full_experiment_records_everything(setup):
    c, ids = setup
    r = _run(c, ids)
    assert r.status_code == 201
    e = r.json()
    assert e["status"] == "completed"
    assert e["prompt_version"] == 1 and e["dataset_version"] == 1
    assert e["config"]["model"] == "mock-model" and e["config"]["temperature"] == 0.2
    assert len(e["dataset_sha256"]) == 64 and e["started_at"] and e["finished_at"]
    s = e["summary"]
    assert s["rows_run"] == 3 and s["succeeded"] == 3 and s["total_tokens"] == 24
    m = s["metrics"]["exact_match"]
    assert m["kind"] == "objective" and m["mean_score"] == pytest.approx(2 / 3, abs=1e-3)
    assert m["pass_rate"] == pytest.approx(2 / 3, abs=1e-3)

    res = c.get(f"/api/experiments/{e['id']}/results").json()
    assert res["total"] == 3
    spain = res["items"][2]
    assert spain["input"]["question"] == "Capital of Spain?" and spain["output"] == "Barcelona"
    assert spain["evaluations"][0]["passed"] is False
    assert spain["latency_ms"] is not None and spain["total_tokens"] == 8


def test_experiment_calls_use_prompt_version_config_and_render_template(setup):
    c, ids = setup
    _run(c, ids)
    first = ids["provider"].calls[0]
    assert first.prompt == "Answer briefly: Capital of France?"
    assert first.temperature == 0.2 and first.max_output_tokens == 50 and first.model == "mock-model"


def test_telemetry_links_requests_to_experiment(setup, db):
    c, ids = setup
    e = _run(c, ids).json()
    docs = list(db["requests"].find({"experiment_id": e["id"]}))
    assert len(docs) == 3 and all(d["prompt_version"] == 1 for d in docs)


def test_history_survives_new_versions_and_versions_show_evaluations(setup):
    c, ids = setup
    e1 = _run(c, ids).json()
    c.post(f"/api/prompts/{ids['prompt']}/versions", json={
        "project_id": ids["project"], "name": "x", "template": "Short: {{question}}",
        "provider": "mock", "model": "mock-model", "temperature": 0.2, "max_output_tokens": 50})
    e2 = _run(c, ids, name="run2", prompt_version=2).json()
    assert e2["prompt_version"] == 2
    # run 1 is untouched and still points at version 1
    again = c.get(f"/api/experiments/{e1['id']}").json()
    assert again["prompt_version"] == 1 and again["summary"] == e1["summary"]
    v1 = c.get(f"/api/prompts/{ids['prompt']}/versions/1").json()
    assert [x["experiment_id"] for x in v1["evaluation_results"]] == [e1["id"]]
    assert "exact_match" in v1["evaluation_results"][0]["metrics"]


def test_pinned_versions_are_reproducible_after_dataset_update(setup):
    c, ids = setup
    e1 = _run(c, ids).json()
    c.post(f"/api/datasets/{ids['dataset']}/versions", json={
        "filename": "qa2.csv", "content": "question,answer\nCapital of Spain?,Madrid\n"})
    e_latest = _run(c, ids, name="latest").json()
    e_pinned = _run(c, ids, name="pinned", dataset_version=1).json()
    assert e_latest["dataset_version"] == 2 and e_latest["summary"]["rows_run"] == 1
    assert e_pinned["dataset_version"] == 1 and e_pinned["summary"] == e1["summary"] | {
        "avg_latency_ms": e_pinned["summary"]["avg_latency_ms"]}


def test_compare_experiments_side_by_side(setup):
    c, ids = setup
    e1 = _run(c, ids).json()
    ids["provider"].answers["Spain"] = "Madrid"  # a "better" second configuration
    c.post(f"/api/prompts/{ids['prompt']}/versions", json={
        "project_id": ids["project"], "name": "x", "template": "Brief: {{question}}",
        "provider": "mock", "model": "mock-model", "temperature": 0.9, "max_output_tokens": 50})
    e2 = _run(c, ids, name="run2", prompt_version=2).json()
    out = c.get("/api/experiments/compare", params={"ids": f"{e1['id']},{e2['id']}"}).json()
    assert out["aligned"] is True
    assert "temperature" in out["config_differences"] and "template" in out["config_differences"]
    assert len(out["rows"]) == 3
    spain = out["rows"][2]["outputs"]
    assert spain[e1["id"]]["output"] == "Barcelona" and spain[e2["id"]]["output"] == "Madrid"
    assert c.get("/api/experiments/compare", params={"ids": e1["id"]}).status_code == 422
    assert c.get("/api/experiments/compare", params={"ids": f"{e1['id']},ghost"}).status_code == 404


def test_validation_errors_do_not_create_experiments(setup):
    c, ids = setup
    n = lambda: c.get("/api/experiments").json()["total"]  # noqa: E731
    assert _run(c, ids, reference_field="nope").status_code == 422
    assert _run(c, ids, evaluators=[{"type": "bogus"}]).status_code == 422
    assert _run(c, ids, evaluators=[{"type": "max_length", "params": {}}]).status_code == 422
    assert _run(c, ids, split="weird").status_code == 422
    assert _run(c, ids, split="train").status_code == 422  # no rows in that split
    assert _run(c, ids, prompt_version=9).status_code == 404
    other = c.post("/api/projects", json={"name": "Other"}).json()["id"]
    assert _run(c, ids, project_id=other).status_code == 422  # asset from another project
    c.post(f"/api/prompts/{ids['prompt']}/versions", json={
        "project_id": ids["project"], "name": "x", "template": "{{missing_col}}",
        "provider": "mock", "model": "mock-model"})
    assert _run(c, ids, prompt_version=2).status_code == 422
    assert n() == 0


def test_max_rows_and_split_selection(setup):
    c, ids = setup
    assert _run(c, ids, max_rows=2).json()["summary"]["rows_run"] == 2
    ds = c.post("/api/datasets", json={
        "project_id": ids["project"], "name": "Split", "filename": "s.csv",
        "content": "question,answer,split\nA?,a,train\nB?,b,eval\n"}).json()["dataset"]["id"]
    e = _run(c, ids, dataset_id=ds, split="eval").json()
    assert e["summary"]["rows_run"] == 1 and e["split"] == "eval"


def test_partial_failures_are_recorded_per_row(make_client):
    class Flaky(ScriptedProvider):
        def generate(self, params):
            if "Italy" in params.prompt:
                raise ProviderRateLimitError("quota")
            return super().generate(params)

    with make_client(provider=Flaky(ANSWERS)) as c:
        proj = c.post("/api/projects", json={"name": "P"}).json()["id"]
        pr = c.post("/api/prompts", json={"project_id": proj, "name": "p", "template": "{{question}}",
                    "provider": "mock", "model": "mock-model"}).json()["prompt"]["id"]
        ds = c.post("/api/datasets", json={"project_id": proj, "name": "d", "filename": "d.csv",
                    "content": QA}).json()["dataset"]["id"]
        e = c.post("/api/experiments", json={"project_id": proj, "name": "e", "prompt_id": pr,
                   "dataset_id": ds}).json()
        assert e["status"] == "partial" and e["summary"]["failed"] == 1
        rows = c.get(f"/api/experiments/{e['id']}/results").json()["items"]
        assert rows[1]["status"] == "error" and rows[1]["error_category"] == "rate_limited"
        assert rows[0]["status"] == "success"


def test_auth_failure_aborts_the_run_early(make_client):
    provider = ScriptedProvider(fail=ProviderAuthError("bad key"))
    with make_client(provider=provider) as c:
        proj = c.post("/api/projects", json={"name": "P"}).json()["id"]
        pr = c.post("/api/prompts", json={"project_id": proj, "name": "p", "template": "{{question}}",
                    "provider": "mock", "model": "mock-model"}).json()["prompt"]["id"]
        ds = c.post("/api/datasets", json={"project_id": proj, "name": "d", "filename": "d.csv",
                    "content": QA}).json()["dataset"]["id"]
        e = c.post("/api/experiments", json={"project_id": proj, "name": "e", "prompt_id": pr,
                   "dataset_id": ds}).json()
    assert e["status"] == "aborted" and e["abort_reason"] == "provider_auth"
    assert len(provider.calls) == 1  # did not keep burning calls on a bad key


def test_missing_api_key_fails_fast_without_saving_anything(real_client):
    c = real_client
    proj = c.post("/api/projects", json={"name": "P"}).json()["id"]
    pr = c.post("/api/prompts", json={"project_id": proj, "name": "p", "template": "{{question}}",
                "provider": "openai", "model": "gpt-4.1-mini"}).json()["prompt"]["id"]
    ds = c.post("/api/datasets", json={"project_id": proj, "name": "d", "filename": "d.csv",
                "content": QA}).json()["dataset"]["id"]
    r = c.post("/api/experiments", json={"project_id": proj, "name": "e", "prompt_id": pr,
               "dataset_id": ds})
    assert r.status_code == 400 and r.json()["error"]["category"] == "missing_api_key"
    assert c.get("/api/experiments").json()["total"] == 0


def test_llm_judge_in_experiment_is_labelled_model_judgment(make_client):
    class Judged(ScriptedProvider):
        def generate(self, params):
            if "grading an AI answer" in params.prompt:
                from app.services.providers.base import ProviderResult
                return ProviderResult('{"score": 4, "reason": "ok"}', 1, 1, 2)
            return super().generate(params)

    with make_client(provider=Judged(ANSWERS)) as c:
        proj = c.post("/api/projects", json={"name": "P"}).json()["id"]
        pr = c.post("/api/prompts", json={"project_id": proj, "name": "p", "template": "{{question}}",
                    "provider": "mock", "model": "mock-model"}).json()["prompt"]["id"]
        ds = c.post("/api/datasets", json={"project_id": proj, "name": "d", "filename": "d.csv",
                    "content": QA}).json()["dataset"]["id"]
        e = c.post("/api/experiments", json={
            "project_id": proj, "name": "e", "prompt_id": pr, "dataset_id": ds,
            "evaluators": [{"type": "llm_judge", "params": {"rubric": "Is it correct?"}},
                           {"type": "max_length", "params": {"max_chars": 100}}]}).json()
    m = e["summary"]["metrics"]
    assert m["llm_judge"]["kind"] == "model_judgment" and m["llm_judge"]["mean_score"] == 4.0
    assert m["max_length"]["kind"] == "objective"


def test_duplicate_evaluator_types_get_unique_names(setup):
    c, ids = setup
    e = _run(c, ids, evaluators=[{"type": "max_length", "params": {"max_chars": 3}},
                                 {"type": "max_length", "params": {"max_chars": 100}}]).json()
    assert set(e["summary"]["metrics"]) == {"max_length", "max_length_2"}
