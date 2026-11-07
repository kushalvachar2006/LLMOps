import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_server_key_is_optional_for_real_providers(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    s = Settings(_env_file=None, llm_provider="gemini")
    assert s.server_key("gemini") is None


def test_unknown_provider_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="other")


def test_mock_provider_needs_no_key():
    assert Settings(_env_file=None, llm_provider="mock").llm_provider == "mock"


def test_api_key_is_not_printed():
    s = Settings(_env_file=None, llm_provider="gemini", gemini_api_key="super-secret-123")
    assert "super-secret-123" not in repr(s)
    assert "super-secret-123" not in str(s.model_dump())
    assert s.server_key("gemini") == "super-secret-123"


def test_cors_origin_parsing():
    s = Settings(_env_file=None, llm_provider="mock", cors_origins="http://a.com, http://b.com")
    assert s.cors_origin_list == ["http://a.com", "http://b.com"]
