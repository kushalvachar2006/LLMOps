from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_prompt_service
from app.schemas.prompt import PromptCreate, PromptVersionCreate

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_prompt(body: PromptCreate, svc=Depends(get_prompt_service)):
    return svc.create_prompt(body)


@router.get("")
def list_prompts(project_id: str | None = Query(None, max_length=64), skip: int = Query(0, ge=0),
                 limit: int = Query(50, ge=1, le=100), svc=Depends(get_prompt_service)):
    return svc.list(project_id, skip, limit)


@router.get("/{prompt_id}")
def get_prompt(prompt_id: str, svc=Depends(get_prompt_service)):
    return svc.get(prompt_id)


@router.post("/{prompt_id}/versions", status_code=status.HTTP_201_CREATED)
def add_version(prompt_id: str, body: PromptVersionCreate, svc=Depends(get_prompt_service)):
    return svc.add_version(prompt_id, body)


@router.get("/{prompt_id}/versions")
def list_versions(prompt_id: str, svc=Depends(get_prompt_service)):
    return svc.list_versions(prompt_id)


@router.get("/{prompt_id}/compare")
def compare(prompt_id: str, a: int = Query(..., ge=1), b: int = Query(..., ge=1),
            svc=Depends(get_prompt_service)):
    return svc.compare(prompt_id, a, b)


@router.get("/{prompt_id}/versions/{version}")
def get_version(prompt_id: str, version: int, svc=Depends(get_prompt_service)):
    return svc.get_version(prompt_id, version)


@router.post("/{prompt_id}/versions/{version}/restore", status_code=status.HTTP_201_CREATED)
def restore(prompt_id: str, version: int, svc=Depends(get_prompt_service)):
    return svc.restore(prompt_id, version)
