from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_filters, get_monitoring_service
from app.schemas.monitoring import FeedbackCreate

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", status_code=status.HTTP_201_CREATED)
def add_feedback(body: FeedbackCreate, svc=Depends(get_monitoring_service)):
    """One rating per request; sending again replaces the earlier rating."""
    return svc.add_feedback(body)


@router.get("")
def list_feedback(limit: int = Query(20, ge=1, le=100), f=Depends(get_filters),
                  svc=Depends(get_monitoring_service)):
    return svc.recent_feedback(f, limit)
