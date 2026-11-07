"""FastAPI dependencies. Tests override these to inject fakes."""
from datetime import datetime

from fastapi import Header, Request
from pymongo.database import Database

from app.core.errors import ValidationAppError
from app.repositories.project_repository import ProjectRepository
from app.repositories.request_repository import RequestRepository
from app.services.llm_service import LLMService
from app.services.project_service import ProjectService


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_project_service(request: Request) -> ProjectService:
    return ProjectService(ProjectRepository(get_db(request)), get_db(request))


def get_request_repo(request: Request) -> RequestRepository:
    return RequestRepository(get_db(request))


def get_api_key(x_provider_api_key: str | None = Header(default=None)) -> str | None:
    """The user's own key travels in a header (not the body) and is never stored or logged."""
    key = (x_provider_api_key or "").strip()
    if not key:
        return None
    if len(key) > 500 or any(c.isspace() for c in key):
        raise ValidationAppError("The API key format looks invalid.")
    return key


def build_llm_service(request: Request, api_key: str | None) -> LLMService:
    db = get_db(request)
    return LLMService(
        registry=request.app.state.registry,
        api_key=api_key,
        requests=RequestRepository(db),
        projects=ProjectRepository(db),
        store_prompt_text=request.app.state.settings.store_prompt_text,
        redaction_enabled=request.app.state.settings.redaction_enabled,
    )


def get_prompt_service(request: Request):
    from app.repositories.assets import ExperimentRepository, PromptRepository
    from app.services.prompt_service import PromptService

    db = get_db(request)
    return PromptService(PromptRepository(db), ProjectRepository(db), ExperimentRepository(db))


def get_dataset_service(request: Request):
    from app.repositories.assets import DatasetRepository
    from app.services.dataset_service import DatasetService

    db = get_db(request)
    return DatasetService(DatasetRepository(db), ProjectRepository(db), request.app.state.settings)


def build_experiment_service(request: Request, api_key: str | None):
    from app.repositories.assets import DatasetRepository, ExperimentRepository, PromptRepository
    from app.services.experiment_service import ExperimentService

    db = get_db(request)
    return ExperimentService(
        ExperimentRepository(db), PromptRepository(db), DatasetRepository(db),
        ProjectRepository(db), build_llm_service(request, api_key), request.app.state.settings,
    )


def get_monitoring_service(request: Request):
    from app.repositories.assets import PromptRepository
    from app.repositories.monitoring import (
        FeedbackRepository,
        MetricsRepository,
        PricingRepository,
        SettingsRepository,
    )
    from app.services.monitoring_service import MonitoringService

    db = get_db(request)
    return MonitoringService(
        MetricsRepository(db), PricingRepository(db), SettingsRepository(db),
        PromptRepository(db), RequestRepository(db), FeedbackRepository(db),
        request.app.state.settings,
    )


def get_filters(
    project_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    provider: str | None = None,
    model: str | None = None,
    deployment_id: str | None = None,
):
    from app.services.monitoring_service import Filters, resolve_range

    s, e = resolve_range(start, end)
    return Filters(project_id or None, s, e, provider or None, model or None,
                   deployment_id or None)


def get_deployment_service(request: Request):
    from app.repositories.assets import PromptRepository
    from app.repositories.deployments import DeploymentRepository
    from app.repositories.monitoring import MetricsRepository
    from app.services.deployment_service import DeploymentService

    db = get_db(request)
    return DeploymentService(DeploymentRepository(db), PromptRepository(db),
                             ProjectRepository(db), MetricsRepository(db))


def get_apikey_service(request: Request):
    from app.repositories.deployments import ApiKeyRepository
    from app.services.apikey_service import ApiKeyService

    db = get_db(request)
    return ApiKeyService(ApiKeyRepository(db), ProjectRepository(db), request.app.state.settings)


def build_invoke_service(request: Request, clock=None):
    import time

    from app.repositories.deployments import (
        ApiKeyRepository,
        DeploymentRepository,
        RateLimitRepository,
    )
    from app.services.invoke_service import InvokeService

    db = get_db(request)
    # Public callers never supply a model key: the server's own key is used.
    return InvokeService(
        ApiKeyRepository(db), RateLimitRepository(db), DeploymentRepository(db),
        build_llm_service(request, None), request.app.state.settings,
        clock=clock or getattr(request.app.state, "clock", time.time),
    )
