import json

CSV = "question,answer\nCapital of France?,Paris\nCapital of Italy?,Rome\nCapital of Spain?,Madrid\n"


def _up(client, project, name="Geo", filename="geo.csv", content=CSV, **kw):
    body = {"project_id": project["id"], "name": name, "filename": filename, "content": content,
            **kw}
    return client.post("/api/datasets", json=body)


def test_csv_upload_schema_and_preview(client, project):
    r = _up(client, project, required_fields=["question", "answer"])
    assert r.status_code == 201
    v = r.json()["version"]
    assert v["version"] == 1 and v["row_count"] == 3 and v["format"] == "csv"
    assert [f["name"] for f in v["schema"]] == ["question", "answer"]
    assert len(v["content_sha256"]) == 64
    did = r.json()["dataset"]["id"]
    rows = client.get(f"/api/datasets/{did}/versions/1/rows", params={"limit": 2}).json()
    assert rows["total"] == 3 and len(rows["items"]) == 2
    assert rows["items"][0]["data"]["answer"] == "Paris"


def test_jsonl_upload_with_nested_values_flattened(client, project):
    lines = "\n".join(json.dumps(x) for x in [{"q": "a", "meta": {"k": 1}}, {"q": "b", "meta": [1]}])
    r = _up(client, project, filename="d.jsonl", content=lines)
    assert r.status_code == 201
    did = r.json()["dataset"]["id"]
    row = client.get(f"/api/datasets/{did}/versions/1/rows").json()["items"][0]["data"]
    assert row["meta"] == '{"k": 1}'


def test_required_field_validation_rejects_and_leaves_nothing_behind(client, project, db):
    bad = "question,answer\nQ1,\n"
    r = _up(client, project, content=bad, required_fields=["answer"])
    assert r.status_code == 422 and "Required-field" in r.json()["error"]["message"]
    r = _up(client, project, required_fields=["nonexistent"])
    assert r.status_code == 422
    assert db["datasets"].count_documents({}) == 0 and db["dataset_rows"].count_documents({}) == 0


def test_format_and_content_validation(client, project):
    assert _up(client, project, filename="x.exe").status_code == 422
    assert _up(client, project, filename="x.csv", content="a,b\n1\n").status_code == 422
    assert _up(client, project, filename="x.csv", content="a,a\n1,2\n").status_code == 422
    assert _up(client, project, filename="x.jsonl", content='{"a":1}\nnot json').status_code == 422
    assert _up(client, project, filename="x.jsonl", content='[1,2]').status_code == 422
    assert _up(client, project, filename="x.csv", content="a,b\n").status_code == 422
    assert _up(client, project, filename="x.csv", content="a\n\x00").status_code == 422


def test_size_limit(client, project):
    big = "a\n" + "x" * 2_100_000
    r = _up(client, project, content=big)
    assert r.status_code == 413 and r.json()["error"]["category"] == "payload_too_large"


def test_splits_by_ratio_are_deterministic_and_complete(client, project):
    content = "id\n" + "\n".join(str(i) for i in range(20))
    ratios = {"train": 0.6, "validation": 0.2, "eval": 0.2}
    a = _up(client, project, "A", content=content, split_ratios=ratios, split_seed=7).json()
    b = _up(client, project, "B", content=content, split_ratios=ratios, split_seed=7).json()
    assert a["version"]["split_counts"] == {"train": 12, "validation": 4, "eval": 4}
    ra = client.get(f"/api/datasets/{a['dataset']['id']}/versions/1/rows", params={"limit": 100})
    rb = client.get(f"/api/datasets/{b['dataset']['id']}/versions/1/rows", params={"limit": 100})
    assert [r["split"] for r in ra.json()["items"]] == [r["split"] for r in rb.json()["items"]]
    ev = client.get(f"/api/datasets/{a['dataset']['id']}/versions/1/rows", params={"split": "eval"})
    assert ev.json()["total"] == 4


def test_split_column_and_bad_ratios(client, project):
    ok = _up(client, project, "S", content="q,split\na,train\nb,eval\n")
    assert ok.json()["version"]["split_counts"] == {"train": 1, "eval": 1}
    assert _up(client, project, "S2", content="q,split\na,bogus\n").status_code == 422
    assert _up(client, project, "S3", split_ratios={"train": 0.5}).status_code == 422


def test_new_version_keeps_old_version_intact(client, project):
    did = _up(client, project).json()["dataset"]["id"]
    r = client.post(f"/api/datasets/{did}/versions", json={
        "filename": "geo2.csv", "content": "question,answer\nQ,A\n", "change_description": "tiny"})
    assert r.status_code == 201 and r.json()["version"] == 2
    v1 = client.get(f"/api/datasets/{did}/versions/1/rows").json()
    v2 = client.get(f"/api/datasets/{did}/versions/2/rows").json()
    assert v1["total"] == 3 and v2["total"] == 1
    assert [v["version"] for v in client.get(f"/api/datasets/{did}/versions").json()] == [2, 1]


def test_dataset_404s_and_duplicates(client, project):
    assert _up(client, project).status_code == 201
    assert _up(client, project, name="geo").status_code == 409
    assert client.get("/api/datasets/ghost").status_code == 404
    assert client.get("/api/datasets/ghost/versions/1/rows").status_code == 404
