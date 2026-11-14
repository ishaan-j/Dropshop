from fastapi import APIRouter, Query

from app.config import get_settings
from app.models import AgentEvent
from app.store import get_store

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=list[AgentEvent])
async def activity_feed(limit: int = Query(50, ge=1, le=200)) -> list[AgentEvent]:
    """The agent activity feed, newest first."""
    return await get_store().list_events(get_settings().demo_user_id, limit)
