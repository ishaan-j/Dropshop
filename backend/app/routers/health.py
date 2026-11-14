from fastapi import APIRouter

from app import finance_gateway, jobs
from app.config import get_settings
from app.store import get_store

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness, plus which backends this process is using (handy when a demo misbehaves)."""
    settings = get_settings()
    return {
        "status": "ok",
        "mock_mode": settings.mock_mode,
        "store": get_store().name,  # memory | db
        "jobs": jobs.mode(),  # inline | arq
        **finance_gateway.modes(),  # bank: simulated | nessie, vault: simulated | solana
        "gemini": "live" if settings.gemini_api_key and not settings.mock_mode else "mock",
        "grok": "live" if settings.xai_api_key and not settings.mock_mode else "off",
    }
