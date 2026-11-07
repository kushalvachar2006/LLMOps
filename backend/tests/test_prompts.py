def _body(project_id, **kw):
    base = {"project_id": project_id, "name": "Summariser", "template": "Summarise: {{text}}",
            "system_instruction": "Be brief", "provider": "mock", "model": "mock-model",
            "temperature": 0.5, "max_output_tokens": 200}
    return {**base, **kw}


def test_create_prompt_makes_version_1(client, project):
    r = client.post("/api/prompts", json=_body(project["id"]))
    assert r.status_code == 201
    out = r.json()
    assert out["version"]["version"] == 1 and out["version"]["variables"] == ["text"]
    assert out["prompt"]["latest_version"] == 1
    assert out["version"]["created_by"] and out["version"]["created_at"]


def test_new_versions_never_modify_old_ones(client, project):
    pid = client.post("/api/prompts", json=_body(project["id"])).json()["prompt"]["id"]
    v1_before = client.get(f"/api/prompts/{pid}/versions/1").json()
    v2 = client.post(f"/api/prompts/{pid}/versions", json={
        **_body(project["id"], template="TL;DR {{text}}", change_description="shorter"),
    }).json()
    assert v2["version"] == 2 and v2["change_description"] == "shorter"
    assert client.get(f"/api/prompts/{pid}/versions/1").json() == v1_before
    versions = client.get(f"/api/prompts/{pid}/versions").json()
    assert [v["version"] for v in versions] == [2, 1]


def test_no_endpoint_can_edit_or_delete_a_version(client, project):
    pid = client.post("/api/prompts", json=_body(project["id"])).json()["prompt"]["id"]
    assert client.put(f"/api/prompts/{pid}/versions/1", json={}).status_code == 405
    assert client.patch(f"/api/prompts/{pid}/versions/1", json={}).status_code == 405
    assert client.delete(f"/api/prompts/{pid}/versions/1").status_code == 405


def test_restore_creates_new_version_from_old(client, project):
    pid = client.post("/api/prompts", json=_body(project["id"])).json()["prompt"]["id"]
    client.post(f"/api/prompts/{pid}/versions", json=_body(project["id"], template="changed"))
    r = client.post(f"/api/prompts/{pid}/versions/1/restore")
    assert r.status_code == 201
    v3 = r.json()
    assert v3["version"] == 3 and v3["template"] == "Summarise: {{text}}"
    assert v3["change_description"] == "Restored from version 1"
    assert client.get(f"/api/prompts/{pid}/versions/2").json()["template"] == "changed"


def test_compare_versions_shows_changes_and_diff(client, project):
    pid = client.post("/api/prompts", json=_body(project["id"])).json()["prompt"]["id"]
    client.post(f"/api/prompts/{pid}/versions", json=_body(project["id"], template="New {{text}}",
                                                           temperature=1.0))
    out = client.get(f"/api/prompts/{pid}/compare", params={"a": 1, "b": 2}).json()
    assert out["changes"]["template"]["changed"] is True
    assert out["changes"]["temperature"] == {"a": 0.5, "b": 1.0, "changed": True}
    assert out["changes"]["model"]["changed"] is False
    assert any(line.startswith("+New") for line in out["diffs"]["template"])


def test_prompt_validation_and_conflicts(client, project):
    assert client.post("/api/prompts", json=_body("ghost")).status_code == 404
    assert client.post("/api/prompts", json=_body(project["id"], provider="zzz")).status_code == 422
    assert client.post("/api/prompts", json=_body(project["id"], template="")).status_code == 422
    client.post("/api/prompts", json=_body(project["id"]))
    assert client.post("/api/prompts", json=_body(project["id"], name="summariser")).status_code == 409
    assert client.get("/api/prompts/ghost").status_code == 404
    assert client.get("/api/prompts/ghost/versions/1").status_code == 404


def test_provider_parameter_limits_enforced_on_versions(client, project):
    r = client.post("/api/prompts", json=_body(project["id"], provider="anthropic",
                                               model="claude-haiku-5-5", temperature=1.8))
    assert r.status_code == 422


def test_list_prompts_filtered_by_project(client, project):
    other = client.post("/api/projects", json={"name": "Other"}).json()
    client.post("/api/prompts", json=_body(project["id"]))
    client.post("/api/prompts", json=_body(other["id"]))
    assert client.get("/api/prompts", params={"project_id": project["id"]}).json()["total"] == 1


def test_project_with_assets_cannot_be_deleted(client, project):
    client.post("/api/prompts", json=_body(project["id"]))
    r = client.delete(f"/api/projects/{project['id']}")
    assert r.status_code == 409 and r.json()["error"]["category"] == "conflict"
