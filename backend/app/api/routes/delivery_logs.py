from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...repository import list_delivery_logs
from ...schemas import DeliveryLogListResponse

router = APIRouter(prefix=settings.api_prefix, tags=["delivery-logs"])


@router.get("/delivery-logs", response_model=DeliveryLogListResponse)
def read_delivery_logs(db: Session = Depends(get_db)) -> DeliveryLogListResponse:
    items = list_delivery_logs(db)
    return DeliveryLogListResponse(items=items, total=len(items))
