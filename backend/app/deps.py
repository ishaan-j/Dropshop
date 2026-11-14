from __future__ import annotations

from fastapi import Header, HTTPException

from app.security import read_token
from app.services.orchestrator import WorkflowError
from data.repository import PersistenceError


def user_from_token(token: str | None) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Sign in required.")
    user_id = read_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired. Sign in again.")
    return user_id


async def current_user(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in required.")
    return user_from_token(authorization.removeprefix("Bearer ").strip())


def http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, WorkflowError):
        return HTTPException(status_code=exc.status_code, detail=exc.message)
    if isinstance(exc, PersistenceError):
        return HTTPException(status_code=503, detail=str(exc))
    raise exc
