from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import current_user
from app.models import AgentEvent
from data.repository import repo

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=list[AgentEvent])
async def activity_feed(limit: int = 50, user_id: str = Depends(current_user)) -> list[AgentEvent]:
    capped = min(max(limit, 1), 200)
    return await repo.list_events(user_id, capped)
