from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.limiter import allow
from app.models import SessionResponse
from app.security import issue_token, session_secret_is_ephemeral
from data.repository import repo

router = APIRouter(prefix="/auth", tags=["auth"])


class SessionRequest(BaseModel):
    display_name: str = Field(default="Local user", max_length=80)


@router.post("/session", response_model=SessionResponse)
async def create_session(body: SessionRequest) -> SessionResponse:
    if not allow("auth", 30):
        raise HTTPException(status_code=429, detail="Too many session requests.")
    user_id = "usr_" + secrets.token_hex(8)
    await repo.save_user(user_id, body.display_name.strip() or "Local user")
    note = "Hackathon session for this browser. It is not a bank login."
    if session_secret_is_ephemeral():
        note += " SESSION_SECRET is unset, so this token dies when the API restarts."
    return SessionResponse(token=issue_token(user_id), user_id=user_id, expires_in=60 * 60 * 24 * 3, note=note)
