from unittest.mock import MagicMock

from pymongo.errors import ServerSelectionTimeoutError


def test_root(client):
    assert client.get("/").json()["name"] == "LLMOps Platform API"


def test_health_reports_database_up(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["api"]["status"] == "up"
    assert body["database"]["status"] == "up"
    assert body["llm_provider"] == "mock"


def test_health_reports_database_down(make_client):
    broken = MagicMock()
    broken.command.side_effect = ServerSelectionTimeoutError("mongodb://user:pw@host down")
    broken.__getitem__.side_effect = ServerSelectionTimeoutError("down")
    with make_client(db_override=broken) as c:
        body = c.get("/health").json()
        assert body["status"] == "degraded"
        assert body["database"]["status"] == "down"
        assert "pw" not in str(body)
        assert c.get("/health/ready").status_code == 503
