"""MongoDB access for deployments, API keys and rate-limit counters."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.core.errors import ConflictError, NotFoundError
from app.repositories.assets import _guard

_HIDE = {"_id": 0, "name_lower": 0}


def _now() -> datetime:
    return datetime.now(UTC)


class DeploymentRepository:
    def __init__(self, db: Database):
        self._d = db["deployments"]
        self._v = db["deployment_versions"]
        self._e = db["deployment_events"]

    @_guard
    def create(self, project_id: str, name: str, description: str) -> dict:
        doc = {
            "id": uuid.uuid4().hex, "project_id": project_id, "name": name,
            "name_lower": name.lower(), "description": description, "latest_version": 0,
            "environments": {"development": None, "staging": None, "production": None},
            "created_at": _now(), "updated_at": _now(),
        }
        try:
            self._d.insert_one(dict(doc))
        except DuplicateKeyError as exc:
            raise ConflictError(f"A deployment named '{name}' already exists in this project") from exc
        doc.pop("name_lower")
        return doc

    @_guard
    def get(self, deployment_id: str) -> dict:
        doc = self._d.find_one({"id": deployment_id}, _HIDE)
        if doc is None:
            raise NotFoundError("Deployment not found")
        return doc

    @_guard
    def list(self, project_id: str | None) -> list[dict]:
        q = {"project_id": project_id} if project_id else {}
        return list(self._d.find(q, _HIDE).sort("created_at", -1).limit(200))

    @_guard
    def next_version(self, deployment_id: str) -> int:
        doc = self._d.find_one_and_update(
            {"id": deployment_id}, {"$inc": {"latest_version": 1}, "$set": {"updated_at": _now()}},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            raise NotFoundError("Deployment not found")
        return doc["latest_version"]

    @_guard
    def insert_version(self, doc: dict) -> dict:
        doc = {"id": uuid.uuid4().hex, "created_at": _now(), "updated_at": _now(), **doc}
        self._v.insert_one(dict(doc))
        return doc

    @_guard
    def get_version(self, deployment_id: str, version: int) -> dict:
        doc = self._v.find_one({"deployment_id": deployment_id, "version": version}, {"_id": 0})
        if doc is None:
            raise NotFoundError(f"Deployment version {version} not found")
        return doc

    @_guard
    def list_versions(self, deployment_id: str) -> list[dict]:
        return list(self._v.find({"deployment_id": deployment_id}, {"_id": 0}).sort("version", -1))

    @_guard
    def update_version(self, deployment_id: str, version: int, changes: dict) -> dict:
        doc = self._v.find_one_and_update(
            {"deployment_id": deployment_id, "version": version},
            {"$set": {**changes, "updated_at": _now()}},
            return_document=ReturnDocument.AFTER, projection={"_id": 0},
        )
        if doc is None:
            raise NotFoundError(f"Deployment version {version} not found")
        return doc

    @_guard
    def set_environment(self, deployment_id: str, environment: str, version: int | None) -> dict:
        doc = self._d.find_one_and_update(
            {"id": deployment_id},
            {"$set": {f"environments.{environment}": version, "updated_at": _now()}},
            return_document=ReturnDocument.AFTER, projection=_HIDE,
        )
        if doc is None:
            raise NotFoundError("Deployment not found")
        return doc

    @_guard
    def add_event(self, doc: dict) -> None:
        self._e.insert_one({"id": uuid.uuid4().hex, "at": _now(), **doc})

    @_guard
    def list_events(self, deployment_id: str, limit: int = 50) -> list[dict]:
        return list(self._e.find({"deployment_id": deployment_id}, {"_id": 0})
                    .sort("at", -1).limit(limit))


class ApiKeyRepository:
    def __init__(self, db: Database):
        self._k = db["api_keys"]

    @_guard
    def create(self, doc: dict) -> dict:
        doc = {"id": uuid.uuid4().hex, "created_at": _now(), "revoked_at": None,
               "last_used_at": None, "request_count": 0, **doc}
        self._k.insert_one(dict(doc))
        return doc

    @_guard
    def get_for_auth(self, key_id: str) -> dict | None:
        """Internal only: includes the hash. Never return this document to a client."""
        return self._k.find_one({"key_id": key_id}, {"_id": 0})

    @_guard
    def list(self, project_id: str | None) -> list[dict]:
        q = {"project_id": project_id} if project_id else {}
        return list(self._k.find(q, {"_id": 0, "hash": 0}).sort("created_at", -1).limit(200))

    @_guard
    def revoke(self, key_row_id: str) -> dict:
        doc = self._k.find_one_and_update(
            {"id": key_row_id, "revoked_at": None}, {"$set": {"revoked_at": _now()}},
            return_document=ReturnDocument.AFTER, projection={"_id": 0, "hash": 0},
        )
        if doc is None:
            existing = self._k.find_one({"id": key_row_id}, {"_id": 0, "hash": 0})
            if existing is None:
                raise NotFoundError("API key not found")
            return existing  # already revoked: revoking again is harmless
        return doc

    @_guard
    def touch(self, key_row_id: str) -> None:
        self._k.update_one({"id": key_row_id},
                           {"$inc": {"request_count": 1}, "$set": {"last_used_at": _now()}})


class RateLimitRepository:
    """Fixed one-minute windows stored in MongoDB, so limits hold across several server processes."""

    def __init__(self, db: Database):
        self._c = db["rate_limits"]

    @_guard
    def hit(self, key_id: str, window: int, expires_at: datetime) -> int:
        doc = self._c.find_one_and_update(
            {"key": f"{key_id}:{window}"},
            {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": expires_at}},
            upsert=True, return_document=ReturnDocument.AFTER,
        )
        return doc["count"]
