"""MongoDB access for prompts, datasets and experiments. No business rules here."""
from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps

from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.errors import ConflictError, DatabaseUnavailableError, NotFoundError

_HIDE = {"_id": 0}


def _guard(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except PyMongoError as exc:
            if isinstance(exc, DuplicateKeyError):
                raise
            raise DatabaseUnavailableError("Database unavailable") from exc

    return wrapper


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid.uuid4().hex


class PromptRepository:
    def __init__(self, db: Database):
        self._p = db["prompts"]
        self._v = db["prompt_versions"]

    @_guard
    def create(self, project_id: str, name: str, description: str) -> dict:
        doc = {
            "id": _new_id(), "project_id": project_id, "name": name,
            "name_lower": name.lower(), "description": description,
            "latest_version": 0, "created_at": _now(), "updated_at": _now(),
        }
        try:
            self._p.insert_one(dict(doc))
        except DuplicateKeyError as exc:
            raise ConflictError(f"A prompt named '{name}' already exists in this project") from exc
        doc.pop("name_lower")
        return doc

    @_guard
    def get(self, prompt_id: str) -> dict:
        doc = self._p.find_one({"id": prompt_id}, {**_HIDE, "name_lower": 0})
        if doc is None:
            raise NotFoundError("Prompt not found")
        return doc

    @_guard
    def list(self, project_id: str | None, skip: int, limit: int) -> tuple[list[dict], int]:
        q = {"project_id": project_id} if project_id else {}
        cur = self._p.find(q, {**_HIDE, "name_lower": 0}).sort("created_at", -1)
        return list(cur.skip(skip).limit(limit)), self._p.count_documents(q)

    @_guard
    def next_version_number(self, prompt_id: str) -> int:
        doc = self._p.find_one_and_update(
            {"id": prompt_id},
            {"$inc": {"latest_version": 1}, "$set": {"updated_at": _now()}},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            raise NotFoundError("Prompt not found")
        return doc["latest_version"]

    @_guard
    def insert_version(self, doc: dict) -> dict:
        doc = {"id": _new_id(), "created_at": _now(), **doc}
        self._v.insert_one(dict(doc))
        return doc

    @_guard
    def get_version(self, prompt_id: str, version: int) -> dict:
        doc = self._v.find_one({"prompt_id": prompt_id, "version": version}, _HIDE)
        if doc is None:
            raise NotFoundError(f"Version {version} not found")
        return doc

    @_guard
    def list_versions(self, prompt_id: str) -> list[dict]:
        return list(self._v.find({"prompt_id": prompt_id}, _HIDE).sort("version", -1))


class DatasetRepository:
    def __init__(self, db: Database):
        self._d = db["datasets"]
        self._v = db["dataset_versions"]
        self._r = db["dataset_rows"]

    @_guard
    def create(self, project_id: str, name: str, description: str) -> dict:
        doc = {
            "id": _new_id(), "project_id": project_id, "name": name,
            "name_lower": name.lower(), "description": description,
            "latest_version": 0, "created_at": _now(), "updated_at": _now(),
        }
        try:
            self._d.insert_one(dict(doc))
        except DuplicateKeyError as exc:
            raise ConflictError(f"A dataset named '{name}' already exists in this project") from exc
        doc.pop("name_lower")
        return doc

    @_guard
    def get(self, dataset_id: str) -> dict:
        doc = self._d.find_one({"id": dataset_id}, {**_HIDE, "name_lower": 0})
        if doc is None:
            raise NotFoundError("Dataset not found")
        return doc

    @_guard
    def list(self, project_id: str | None, skip: int, limit: int) -> tuple[list[dict], int]:
        q = {"project_id": project_id} if project_id else {}
        cur = self._d.find(q, {**_HIDE, "name_lower": 0}).sort("created_at", -1)
        return list(cur.skip(skip).limit(limit)), self._d.count_documents(q)

    @_guard
    def next_version_number(self, dataset_id: str) -> int:
        doc = self._d.find_one_and_update(
            {"id": dataset_id},
            {"$inc": {"latest_version": 1}, "$set": {"updated_at": _now()}},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            raise NotFoundError("Dataset not found")
        return doc["latest_version"]

    @_guard
    def insert_version(self, doc: dict, rows: list[dict]) -> dict:
        doc = {"id": _new_id(), "created_at": _now(), **doc}
        self._v.insert_one(dict(doc))
        for start in range(0, len(rows), 500):
            chunk = [
                {"dataset_version_id": doc["id"], **r} for r in rows[start:start + 500]
            ]
            self._r.insert_many(chunk)
        return doc

    @_guard
    def get_version(self, dataset_id: str, version: int) -> dict:
        doc = self._v.find_one({"dataset_id": dataset_id, "version": version}, _HIDE)
        if doc is None:
            raise NotFoundError(f"Dataset version {version} not found")
        return doc

    @_guard
    def list_versions(self, dataset_id: str) -> list[dict]:
        return list(self._v.find({"dataset_id": dataset_id}, _HIDE).sort("version", -1))

    @_guard
    def list_rows(self, version_id: str, split: str | None, skip: int, limit: int):
        q = {"dataset_version_id": version_id}
        if split and split != "all":
            q["split"] = split
        cur = self._r.find(q, {"_id": 0, "dataset_version_id": 0}).sort("index", 1)
        return list(cur.skip(skip).limit(limit)), self._r.count_documents(q)


class ExperimentRepository:
    def __init__(self, db: Database):
        self._e = db["experiments"]
        self._r = db["experiment_results"]

    @_guard
    def insert(self, doc: dict) -> dict:
        doc = {"id": _new_id(), "created_at": _now(), **doc}
        self._e.insert_one(dict(doc))
        return doc

    @_guard
    def update(self, exp_id: str, changes: dict) -> None:
        self._e.update_one({"id": exp_id}, {"$set": changes})

    @_guard
    def get(self, exp_id: str) -> dict:
        doc = self._e.find_one({"id": exp_id}, _HIDE)
        if doc is None:
            raise NotFoundError("Experiment not found")
        return doc

    @_guard
    def list(self, project_id: str | None, skip: int, limit: int) -> tuple[list[dict], int]:
        q = {"project_id": project_id} if project_id else {}
        cur = self._e.find(q, _HIDE).sort("created_at", -1)
        return list(cur.skip(skip).limit(limit)), self._e.count_documents(q)

    @_guard
    def for_prompt_version(self, prompt_id: str, version: int) -> list[dict]:
        q = {"prompt_id": prompt_id, "prompt_version": version}
        return list(self._e.find(q, _HIDE).sort("created_at", -1))

    @_guard
    def insert_result(self, doc: dict) -> None:
        self._r.insert_one(dict(doc))

    @_guard
    def list_results(self, exp_id: str, skip: int, limit: int) -> tuple[list[dict], int]:
        q = {"experiment_id": exp_id}
        cur = self._r.find(q, _HIDE).sort("row_index", 1)
        return list(cur.skip(skip).limit(limit)), self._r.count_documents(q)
