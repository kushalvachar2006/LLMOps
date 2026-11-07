from fastapi import APIRouter, Depends, Query

from app.api.deps import get_filters, get_monitoring_service
from app.schemas.monitoring import Thresholds

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/policy")
def policy(svc=Depends(get_monitoring_service)):
    return svc.policy()


@router.get("/summary")
def summary(f=Depends(get_filters), svc=Depends(get_monitoring_service)):
    return svc.summary(f)


@router.get("/timeseries")
def timeseries(granularity: str | None = Query(None, max_length=10), f=Depends(get_filters),
               svc=Depends(get_monitoring_service)):
    return svc.timeseries(f, granularity)


@router.get("/breakdown")
def breakdown(f=Depends(get_filters), svc=Depends(get_monitoring_service)):
    return svc.breakdown(f)


@router.get("/quality")
def quality(granularity: str | None = Query(None, max_length=10), f=Depends(get_filters),
            svc=Depends(get_monitoring_service)):
    return svc.quality(f, granularity)


@router.get("/alerts")
def alerts(f=Depends(get_filters), svc=Depends(get_monitoring_service)):
    return svc.alerts(f)


@router.get("/thresholds")
def get_thresholds(svc=Depends(get_monitoring_service)):
    return svc.get_thresholds()


@router.put("/thresholds")
def put_thresholds(body: Thresholds, svc=Depends(get_monitoring_service)):
    return svc.save_thresholds(body)
