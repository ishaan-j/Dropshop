from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from data.repository import repo

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "dropshop"}


@router.get("/ready")
async def ready() -> dict:
    settings = get_settings()
    if repo.block_memory or (repo.mongo is None and not settings.mock_mode):
        raise HTTPException(status_code=503, detail=repo.mongo_detail)
    return {
        "status": "ready",
        "persistence": "memory_demo" if repo.mongo is None else repo.mongo_mode,
        "prices": repo.pg_mode,
    }
