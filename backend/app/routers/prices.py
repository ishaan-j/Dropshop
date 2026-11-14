from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.deps import current_user
from app.models import PricePoint
from data.repository import PersistenceError, repo

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/{product_id}", response_model=list[PricePoint])
async def price_history(product_id: str, days: int = 30, user_id: str = Depends(current_user)) -> list[PricePoint]:
    if days < 1 or days > 365:
        raise HTTPException(status_code=422, detail="days must be between 1 and 365.")
    try:
        return await repo.price_history(user_id, product_id, days)
    except PersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
