"""All MongoDB access for projects lives here (no business rules)."""
import uuid
from datetime import UTC, datetime

from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.errors import ConflictError, DatabaseUnavailableError, NotFoundError
from app.db.indexes import PROJECTS

_HIDE = {"_id": 0, "name_lower": 0}


class ProjectRepository:
    def __init__(self, db: Database):
        self._col = db[PROJECTS]

    def create(self, name: str, description: str) -> dict:
        now = datetime.now(UTC)
        doc = {
            "id": uuid.uuid4().hex,
            "name": name,
            "name_lower": name.lower(),
            "description": description,
            "created_at": now,
            "updated_at": now,
        }
        try:
            self._col.insert_one(dict(doc))
        except DuplicateKeyError as exc:
            raise ConflictError(f"A project named '{name}' already exists") from exc
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Database unavailable") from exc
        doc.pop("name_lower")
        return doc

    def get(self, project_id: str) -> dict:
        try:
            doc = self._col.find_one({"id": project_id}, _HIDE)
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Database unavailable") from exc
        if doc is None:
            raise NotFoundError("Project not found")
        return doc

    def list(self, skip: int, limit: int) -> tuple[list[dict], int]:
        try:
            total = self._col.count_documents({})
            cursor = self._col.find({}, _HIDE).sort("created_at", -1).skip(skip).limit(limit)
            return list(cursor), total
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Database unavailable") from exc

    def update(self, project_id: str, changes: dict) -> dict:
        changes = {k: v for k, v in changes.items() if v is not None}
        if "name" in changes:
            changes["name_lower"] = changes["name"].lower()
        changes["updated_at"] = datetime.now(UTC)
        try:
            doc = self._col.find_one_and_update(
                {"id": project_id},
                {"$set": changes},
                projection=_HIDE,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError as exc:
            raise ConflictError("Another project already uses that name") from exc
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Database unavailable") from exc
        if doc is None:
            raise NotFoundError("Project not found")
        return doc

    def delete(self, project_id: str) -> None:
        try:
            result = self._col.delete_one({"id": project_id})
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Database unavailable") from exc
        if result.deleted_count == 0:
            raise NotFoundError("Project not found")

    def exists(self, project_id: str) -> bool:
        try:
            return self._col.count_documents({"id": project_id}, limit=1) > 0
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Database unavailable") from exc
