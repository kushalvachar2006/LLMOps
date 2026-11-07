from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.errors import ConflictError, DatabaseUnavailableError
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate

# Collections whose records belong to a project and must not be orphaned.
_DEPENDENTS = {"prompts": "prompts", "datasets": "datasets", "experiments": "experiments"}


class ProjectService:
    def __init__(self, repo: ProjectRepository, db: Database | None = None):
        self._repo = repo
        self._db = db

    def create(self, data: ProjectCreate) -> dict:
        return self._repo.create(data.name, data.description)

    def get(self, project_id: str) -> dict:
        return self._repo.get(project_id)

    def list(self, skip: int, limit: int) -> dict:
        items, total = self._repo.list(skip, limit)
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def update(self, project_id: str, data: ProjectUpdate) -> dict:
        return self._repo.update(project_id, data.model_dump())

    def delete(self, project_id: str) -> None:
        self._repo.get(project_id)  # 404 if missing
        if self._db is not None:
            try:
                for col, label in _DEPENDENTS.items():
                    n = self._db[col].count_documents({"project_id": project_id})
                    if n:
                        raise ConflictError(
                            f"This project still has {n} {label}. History is never deleted "
                            "silently, so remove or keep the project."
                        )
            except PyMongoError as exc:
                raise DatabaseUnavailableError("Database unavailable") from exc
        self._repo.delete(project_id)
