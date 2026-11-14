from fastapi import APIRouter, HTTPException

from app import mock_data
from app.config import get_settings
from app.models import PricePoint

router = APIRouter(prefix="/prices", tags=["prices"])
settings = get_settings()


@router.get("/{product_id}", response_model=list[PricePoint])
async def price_history(product_id: str, days: int = 30) -> list[PricePoint]:
    if settings.mock_mode:
        return mock_data.price_history(product_id, days)
    # TODO(L2): return await data.timescale.price_history(product_id, days)
    raise HTTPException(501, "Not implemented")
