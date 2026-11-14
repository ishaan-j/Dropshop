from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import current_user
from app.models import SavingsSummary
from app.services.dashboard import savings_summary

router = APIRouter(prefix="/savings", tags=["savings"])


@router.get("", response_model=SavingsSummary)
async def savings(user_id: str = Depends(current_user)) -> SavingsSummary:
    return await savings_summary(user_id)
