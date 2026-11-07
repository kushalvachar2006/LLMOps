"""Datasets with immutable versions, schema inspection and train/validation/eval splits."""
from __future__ import annotations

import hashlib
from collections import Counter

from app.core.config import Settings
from app.repositories.assets import DatasetRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.dataset import DatasetCreate, DatasetUpload
from app.services import dataset_parser as dp

CREATED_BY = "local-user"


class DatasetService:
    def __init__(self, datasets: DatasetRepository, projects: ProjectRepository,
                 settings: Settings):
        self._datasets = datasets
        self._projects = projects
        self._settings = settings

    def _prepare(self, up: DatasetUpload):
        """Parse and fully validate BEFORE anything is written."""
        fmt, rows = dp.parse_dataset(
            up.filename, up.content, self._settings.max_dataset_bytes,
            self._settings.max_dataset_rows,
        )
        schema = dp.infer_schema(rows)
        dp.validate_required(rows, schema, up.required_fields)
        labels = dp.assign_splits(rows, up.split_ratios, up.split_seed)
        return fmt, rows, schema, labels

    def _store_version(self, dataset: dict, up: DatasetUpload, prepared) -> dict:
        fmt, rows, schema, labels = prepared
        number = self._datasets.next_version_number(dataset["id"])
        doc = {
            "dataset_id": dataset["id"], "project_id": dataset["project_id"], "version": number,
            "filename": up.filename, "format": fmt, "row_count": len(rows), "schema": schema,
            "required_fields": up.required_fields,
            "split_counts": dict(Counter(labels)),
            "content_sha256": hashlib.sha256(up.content.encode("utf-8")).hexdigest(),
            "change_description": up.change_description, "created_by": CREATED_BY,
        }
        row_docs = [
            {"index": i, "split": labels[i], "data": rows[i]} for i in range(len(rows))
        ]
        return self._datasets.insert_version(doc, row_docs)

    def create(self, data: DatasetCreate) -> dict:
        self._projects.get(data.project_id)
        prepared = self._prepare(data)  # a bad file never leaves an empty dataset behind
        dataset = self._datasets.create(data.project_id, data.name, data.description)
        version = self._store_version(dataset, data, prepared)
        return {"dataset": self._datasets.get(dataset["id"]), "version": version}

    def add_version(self, dataset_id: str, up: DatasetUpload) -> dict:
        dataset = self._datasets.get(dataset_id)
        return self._store_version(dataset, up, self._prepare(up))

    def get(self, dataset_id: str) -> dict:
        return self._datasets.get(dataset_id)

    def list(self, project_id: str | None, skip: int, limit: int) -> dict:
        items, total = self._datasets.list(project_id, skip, limit)
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def list_versions(self, dataset_id: str) -> list[dict]:
        self._datasets.get(dataset_id)
        return self._datasets.list_versions(dataset_id)

    def get_version(self, dataset_id: str, version: int) -> dict:
        self._datasets.get(dataset_id)
        return self._datasets.get_version(dataset_id, version)

    def rows(self, dataset_id: str, version: int, split: str | None, skip: int, limit: int):
        self._datasets.get(dataset_id)
        v = self._datasets.get_version(dataset_id, version)
        items, total = self._datasets.list_rows(v["id"], split, skip, limit)
        return {"items": items, "total": total, "skip": skip, "limit": limit}
