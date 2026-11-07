from fastapi import APIRouter, Depends, Query

from app.api.deps import get_request_repo
from app.repositories.request_repository import RequestRepository
from app.schemas.llm import RequestPage

router = APIRouter(prefix="/api/requests", tags=["telemetry"])


@router.get("", response_model=RequestPage)
def list_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    project_id: str | None = Query(None, max_length=64),
    repo: RequestRepository = Depends(get_request_repo),
):
    items, total = repo.list(skip, limit, project_id)
    return {"items": items, "total": total, "skip": skip, "limit": limit}
