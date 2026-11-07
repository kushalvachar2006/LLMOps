"""FastAPI application factory."""
import logging
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.database import Database

from app.api.routes import (
    api_keys,
    datasets,
    deployments,
    experiments,
    feedback,
    generate,
    health,
    invoke,
    models,
    monitoring,
    pricing,
    projects,
    prompts,
    telemetry,
)
from app.core.config import Settings, get_settings
from app.core.errors import AppError, RateLimitedError
from app.core.logging import setup_logging
from app.core.security import admin_token_ok
from app.db.indexes import (
    ensure_deployment_indexes,
    ensure_indexes,
    ensure_monitoring_indexes,
    ensure_workspace_indexes,
)
from app.db.mongo import create_client, get_database
from app.services.providers.base import LLMProvider
from app.services.providers.registry import ProviderRegistry

log = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    db: Database | None = None,
    provider: LLMProvider | None = None,
) -> FastAPI:
    """Dependencies can be injected (tests) or built from settings (production)."""
    settings = settings or get_settings()
    setup_logging(settings.log_level)
    client = None
    if db is None:
        client = create_client(settings)
        db = get_database(client, settings)
    registry = ProviderRegistry(settings, override=provider)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            ensure_indexes(db)
            ensure_workspace_indexes(db)
            ensure_monitoring_indexes(db, settings.trace_retention_days)
            ensure_deployment_indexes(db)
        except Exception as exc:  # noqa: BLE001 - API should still start; /health shows DB down
            log.error("index creation failed", extra={"ctx": {"error_type": type(exc).__name__}})
        yield
        if client is not None:
            client.close()

    production = settings.app_env.lower() == "production"
    app = FastAPI(
        title="LLMOps Platform API", version="0.1.0", lifespan=lifespan,
        # Interactive docs reveal the whole API surface, so they are off in production.
        docs_url=None if production else "/docs", redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )
    app.state.settings = settings
    app.state.db = db
    app.state.registry = registry

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://llmops-kva.netlify.app"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Provider-Api-Key",
            "X-Admin-Token",
        ],
    )

    @app.middleware("http")
    async def require_admin_token(request: Request, call_next):
        """When ADMIN_TOKEN is set, the management API (/api/*) needs it. /v1/* uses API keys."""
        expected = settings.admin_token_value or os.getenv("ADMIN_TOKEN")
        path = request.url.path
        if (expected and path.startswith("/api") and request.method != "OPTIONS"
                and not admin_token_ok(request.headers.get("x-admin-token"), expected)):
            return JSONResponse(
                status_code=401,
                content={"error": {"category": "unauthorized",
                                   "message": "Missing or invalid admin token."}},
            )
        return await call_next(request)

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        body = {"category": exc.category, "message": exc.message}
        if getattr(exc, "request_id", None):
            body["request_id"] = exc.request_id
        headers = {}
        if isinstance(exc, RateLimitedError):
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(status_code=exc.status_code, content={"error": body}, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        fields = [".".join(str(p) for p in e["loc"] if p != "body") for e in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "category": "validation_error",
                    "message": "Invalid input",
                    "fields": fields,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception):
        log.error("unhandled error", extra={"ctx": {"error_type": type(exc).__name__}})
        return JSONResponse(
            status_code=500,
            content={"error": {"category": "internal_error", "message": "Internal server error"}},
        )

    for module in (
        health, projects, generate, models, prompts, datasets, experiments, telemetry,
        monitoring, pricing, feedback, deployments, api_keys, invoke,
    ):
        app.include_router(module.router)
    return app


def app_factory() -> FastAPI:
    """Entry point for uvicorn: `uvicorn app.main:app_factory --factory`."""
    return create_app()
