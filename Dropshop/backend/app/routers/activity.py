from fastapi import APIRouter, HTTPException

from app import mock_data
from app.config import get_settings
from app.models import AgentEvent

router = APIRouter(prefix="/activity", tags=["activity"])
settings = get_settings()


@router.get("", response_model=list[AgentEvent])
async def activity_feed(limit: int = 50) -> list[AgentEvent]:
    if settings.mock_mode:
        return mock_data.ACTIVITY[:limit]
    # TODO(L2): return await data.mongo.list_events(settings.demo_user_id, limit)
    raise HTTPException(501, "Not implemented")
