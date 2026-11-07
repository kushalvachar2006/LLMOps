from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import (
    build_llm_service,
    get_api_key,
    get_deployment_service,
)
from app.schemas.deployment import DeploymentCreate, PromoteRequest, PublishRequest
from app.services.monitoring_service import resolve_range

router = APIRouter(prefix="/api/deployments", tags=["deployments"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_deployment(body: DeploymentCreate, svc=Depends(get_deployment_service)):
    return svc.create(body)


@router.get("")
def list_deployments(project_id: str | None = Query(None, max_length=64),
                     svc=Depends(get_deployment_service)):
    return svc.list(project_id)


@router.get("/{deployment_id}")
def get_deployment(deployment_id: str, svc=Depends(get_deployment_service)):
    return svc.get(deployment_id)


# Plain `def` routes run in the threadpool: publishing makes live model calls.
@router.post("/{deployment_id}/versions", status_code=status.HTTP_201_CREATED)
def publish_version(deployment_id: str, body: PublishRequest, request: Request,
                    api_key: str | None = Depends(get_api_key),
                    svc=Depends(get_deployment_service)):
    return svc.publish(deployment_id, body, build_llm_service(request, api_key))


@router.get("/{deployment_id}/versions")
def list_versions(deployment_id: str, svc=Depends(get_deployment_service)):
    return svc.list_versions(deployment_id)


@router.post("/{deployment_id}/versions/{version}/health-check")
def health_check(deployment_id: str, version: int, request: Request,
                 api_key: str | None = Depends(get_api_key), svc=Depends(get_deployment_service)):
    return svc.health_check(deployment_id, version, build_llm_service(request, api_key))


@router.post("/{deployment_id}/promote")
def promote(deployment_id: str, body: PromoteRequest, svc=Depends(get_deployment_service)):
    return svc.promote(deployment_id, body)


@router.delete("/{deployment_id}/environments/{environment}")
def unpublish(deployment_id: str, environment: str, svc=Depends(get_deployment_service)):
    return svc.unpublish(deployment_id, environment)


@router.get("/{deployment_id}/events")
def events(deployment_id: str, svc=Depends(get_deployment_service)):
    return svc.events(deployment_id)


@router.get("/{deployment_id}/usage")
def usage(deployment_id: str, start: datetime | None = None, end: datetime | None = None,
          svc=Depends(get_deployment_service)):
    s, e = resolve_range(start, end)
    return svc.usage(deployment_id, s, e)
