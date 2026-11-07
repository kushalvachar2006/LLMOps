from fastapi import APIRouter, Depends, status

from app.api.deps import get_monitoring_service
from app.schemas.monitoring import PricingCreate

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


@router.post("", status_code=status.HTTP_201_CREATED)
def add_price(body: PricingCreate, svc=Depends(get_monitoring_service)):
    return svc.add_price(body)


@router.get("")
def list_prices(svc=Depends(get_monitoring_service)):
    return svc.list_prices()


@router.delete("/{pricing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_price(pricing_id: str, svc=Depends(get_monitoring_service)):
    svc.delete_price(pricing_id)
