"""Persistence for request telemetry."""
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.errors import DatabaseUnavailableError
from app.db.indexes import REQUESTS

_HIDE = {"_id": 0}


class RequestRepository:
    def __init__(self, db: Database):
        self._col = db[REQUESTS]

    def insert(self, record: dict) -> None:
        self._col.insert_one(dict(record))

    def set_evaluations(self, request_id: str, evaluations: list[dict]) -> None:
        self._col.update_one({"request_id": request_id}, {"$set": {"evaluations": evaluations}})

    def get(self, request_id: str) -> dict | None:
        return self._col.find_one({"request_id": request_id}, _HIDE)

    def list(self, skip: int, limit: int, project_id: str | None) -> tuple[list[dict], int]:
        query = {"project_id": project_id} if project_id else {}
        try:
            total = self._col.count_documents(query)
            cursor = self._col.find(query, _HIDE).sort("created_at", -1).skip(skip).limit(limit)
            return list(cursor), total
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Database unavailable") from exc
