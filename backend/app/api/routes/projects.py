from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_project_service
from app.schemas.project import ProjectCreate, ProjectOut, ProjectPage, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, svc: ProjectService = Depends(get_project_service)):
    return svc.create(body)


@router.get("", response_model=ProjectPage)
def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    svc: ProjectService = Depends(get_project_service),
):
    return svc.list(skip, limit)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, svc: ProjectService = Depends(get_project_service)):
    return svc.get(project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: str, body: ProjectUpdate, svc: ProjectService = Depends(get_project_service)
):
    return svc.update(project_id, body)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, svc: ProjectService = Depends(get_project_service)):
    svc.delete(project_id)
