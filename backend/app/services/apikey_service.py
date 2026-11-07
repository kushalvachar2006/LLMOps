from __future__ import annotations

from app.core.config import Settings
from app.core.errors import ValidationAppError
from app.core.security import generate_api_key, hash_secret
from app.repositories.deployments import ApiKeyRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.deployment import ApiKeyCreate


class ApiKeyService:
    def __init__(self, keys: ApiKeyRepository, projects: ProjectRepository, settings: Settings):
        self._keys = keys
        self._projects = projects
        self._settings = settings

    def create(self, data: ApiKeyCreate) -> dict:
        """Returns the full key ONCE inside `secret`. Only its keyed hash is stored."""
        self._projects.get(data.project_id)
        limit = data.rate_limit_per_minute or self._settings.default_rate_limit_per_minute
        if limit > self._settings.max_rate_limit_per_minute:
            raise ValidationAppError(
                f"Rate limit cannot exceed {self._settings.max_rate_limit_per_minute} per minute."
            )
        key_id, secret, token = generate_api_key()
        doc = self._keys.create({
            "key_id": key_id, "hash": hash_secret(secret, self._settings.pepper),
            "project_id": data.project_id, "name": data.name,
            "environments": data.environments, "rate_limit_per_minute": limit,
        })
        public = {k: v for k, v in doc.items() if k != "hash"}
        return {**public, "prefix": f"llmops_{key_id}", "secret": token}

    def list(self, project_id: str | None) -> list[dict]:
        return [{**k, "prefix": f"llmops_{k['key_id']}"} for k in self._keys.list(project_id)]

    def revoke(self, key_row_id: str) -> dict:
        row = self._keys.revoke(key_row_id)
        return {**row, "prefix": f"llmops_{row['key_id']}"}
