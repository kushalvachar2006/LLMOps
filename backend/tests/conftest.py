import mongomock
import pytest
from app.core.config import Settings
from app.main import create_app
from app.services.providers.mock import MockProvider
from fastapi.testclient import TestClient


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, llm_provider="mock")


@pytest.fixture
def db():
    return mongomock.MongoClient()["llmops_test"]


@pytest.fixture
def make_client(settings, db):
    def _make(provider=None, db_override=None, cfg=None):
        app = create_app(
            settings=cfg or settings,
            db=db_override if db_override is not None else db,
            provider=provider or MockProvider(),
        )
        return TestClient(app)

    return _make


@pytest.fixture
def client(make_client):
    with make_client() as c:
        yield c


class ScriptedProvider:
    """Deterministic fake model: answers by looking the question up in a dict."""

    name = "mock"
    default_model = "mock-model"

    def __init__(self, answers: dict | None = None, default: str = "unknown", fail=None):
        self.answers, self.default, self.fail, self.calls = answers or {}, default, fail, []

    def generate(self, params):
        from app.services.providers.base import ProviderResult

        self.calls.append(params)
        if self.fail is not None:
            raise self.fail
        text = next((v for k, v in self.answers.items() if k in params.prompt), self.default)
        return ProviderResult(text, 5, 3, 8)


@pytest.fixture
def real_client(settings, db):
    """App WITHOUT an injected provider, so the real registry (keys, providers) is exercised."""
    app = create_app(settings=settings, db=db)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def project(client):
    return client.post("/api/projects", json={"name": "Proj"}).json()
