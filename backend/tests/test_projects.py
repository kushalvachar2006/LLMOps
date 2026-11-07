def _create(client, name="Alpha", description="first"):
    return client.post("/api/projects", json={"name": name, "description": description})


def test_create_and_get(client):
    r = _create(client)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Alpha" and body["id"]
    assert client.get(f"/api/projects/{body['id']}").json()["name"] == "Alpha"


def test_projects_persist_in_database(client, db):
    pid = _create(client).json()["id"]
    assert db["projects"].count_documents({"id": pid}) == 1


def test_duplicate_name_conflicts_case_insensitive(client):
    _create(client, "Alpha")
    r = _create(client, "alpha")
    assert r.status_code == 409
    assert r.json()["error"]["category"] == "conflict"


def test_blank_name_rejected(client):
    r = client.post("/api/projects", json={"name": "   "})
    assert r.status_code == 422
    assert r.json()["error"]["category"] == "validation_error"


def test_name_whitespace_is_normalised(client):
    assert _create(client, "  My   Project ").json()["name"] == "My Project"


def test_update_changes_fields_and_timestamp(client):
    p = _create(client).json()
    r = client.patch(f"/api/projects/{p['id']}", json={"description": "changed"})
    assert r.status_code == 200
    body = r.json()
    assert body["description"] == "changed" and body["name"] == "Alpha"
    assert body["updated_at"] >= p["updated_at"]


def test_update_to_existing_name_conflicts(client):
    _create(client, "A")
    b = _create(client, "B").json()
    assert client.patch(f"/api/projects/{b['id']}", json={"name": "a"}).status_code == 409


def test_delete(client):
    pid = _create(client).json()["id"]
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_missing_project_404(client):
    assert client.get("/api/projects/nope").status_code == 404
    assert client.delete("/api/projects/nope").status_code == 404
    assert client.patch("/api/projects/nope", json={"name": "x"}).status_code == 404


def test_pagination(client):
    for i in range(5):
        _create(client, f"P{i}")
    page = client.get("/api/projects", params={"skip": 1, "limit": 2}).json()
    assert page["total"] == 5 and len(page["items"]) == 2
    assert client.get("/api/projects", params={"limit": 1000}).status_code == 422
