from fastapi import APIRouter, Depends, Request, Response
from pymongo.database import Database

from app.api.deps import get_db
from app.db.mongo import ping

router = APIRouter(tags=["health"])


@router.get("/")
def root() -> dict:
    return {"name": "LLMOps Platform API", "docs": "/docs", "health": "/health"}


@router.get("/health")
def health(request: Request, db: Database = Depends(get_db)) -> dict:
    """Always answers 200 with an accurate per-component status."""
    db_ok, db_error = ping(db)
    return {
        "status": "ok" if db_ok else "degraded",
        "api": {"status": "up"},
        "database": {"status": "up" if db_ok else "down", "error_type": db_error},
        "llm_provider": request.app.state.registry.default_provider,
        "admin_auth": request.app.state.settings.admin_token_value is not None,
    }


@router.get("/health/ready")
def ready(response: Response, db: Database = Depends(get_db)) -> dict:
    """Readiness probe for containers: 503 if the database is unreachable."""
    db_ok, _ = ping(db)
    if not db_ok:
        response.status_code = 503
    return {"ready": db_ok}
