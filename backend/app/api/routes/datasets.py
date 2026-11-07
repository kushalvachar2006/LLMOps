from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_dataset_service
from app.schemas.dataset import DatasetCreate, DatasetUpload

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_dataset(body: DatasetCreate, svc=Depends(get_dataset_service)):
    return svc.create(body)


@router.get("")
def list_datasets(project_id: str | None = Query(None, max_length=64), skip: int = Query(0, ge=0),
                  limit: int = Query(50, ge=1, le=100), svc=Depends(get_dataset_service)):
    return svc.list(project_id, skip, limit)


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str, svc=Depends(get_dataset_service)):
    return svc.get(dataset_id)


@router.post("/{dataset_id}/versions", status_code=status.HTTP_201_CREATED)
def add_version(dataset_id: str, body: DatasetUpload, svc=Depends(get_dataset_service)):
    return svc.add_version(dataset_id, body)


@router.get("/{dataset_id}/versions")
def list_versions(dataset_id: str, svc=Depends(get_dataset_service)):
    return svc.list_versions(dataset_id)


@router.get("/{dataset_id}/versions/{version}")
def get_version(dataset_id: str, version: int, svc=Depends(get_dataset_service)):
    return svc.get_version(dataset_id, version)


@router.get("/{dataset_id}/versions/{version}/rows")
def preview_rows(dataset_id: str, version: int, split: str | None = Query(None, max_length=20),
                 skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                 svc=Depends(get_dataset_service)):
    return svc.rows(dataset_id, version, split, skip, limit)
