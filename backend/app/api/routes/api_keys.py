from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_apikey_service
from app.schemas.deployment import ApiKeyCreate

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_key(body: ApiKeyCreate, response: Response, svc=Depends(get_apikey_service)):
    """The full key appears in this response only. It cannot be shown again."""
    response.headers["Cache-Control"] = "no-store"
    return svc.create(body)


@router.get("")
def list_keys(project_id: str | None = Query(None, max_length=64), svc=Depends(get_apikey_service)):
    return svc.list(project_id)


@router.post("/{key_id}/revoke")
def revoke_key(key_id: str, svc=Depends(get_apikey_service)):
    return svc.revoke(key_id)
