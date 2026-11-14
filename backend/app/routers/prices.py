from fastapi import APIRouter, Query

from app.models import PricePoint
from app.store import get_store

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/{product_id}", response_model=list[PricePoint])
async def price_history(product_id: str, days: int = Query(30, ge=1, le=365)) -> list[PricePoint]:
    """Daily price history for the chart, oldest first."""
    return await get_store().price_history(product_id, days)
