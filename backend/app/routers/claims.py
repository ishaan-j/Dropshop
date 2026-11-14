from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from agents.claim_bot import SHOT_DIR
from app.deps import current_user
from app.models import Claim, ClaimActionResult
from app.services.orchestrator import WorkflowError, approve_claim, reject_claim
from data.repository import repo

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("", response_model=list[Claim])
async def list_claims(user_id: str = Depends(current_user)) -> list[Claim]:
    return await repo.list_claims(user_id)


@router.post("/{claim_id}/approve", response_model=ClaimActionResult)
async def approve(claim_id: str, user_id: str = Depends(current_user)) -> ClaimActionResult:
    try:
        claim, submitted, note = await approve_claim(user_id, claim_id)
    except WorkflowError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return ClaimActionResult(claim=claim, submitted=submitted, note=note)


@router.post("/{claim_id}/reject", response_model=Claim)
async def reject(claim_id: str, user_id: str = Depends(current_user)) -> Claim:
    try:
        return await reject_claim(user_id, claim_id)
    except WorkflowError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/{claim_id}/screenshots/{name}")
async def screenshot(claim_id: str, name: str, user_id: str = Depends(current_user)) -> FileResponse:
    if "/" in name or "\\" in name or not name.startswith(claim_id):
        raise HTTPException(status_code=404, detail="Screenshot not found.")
    claim = await repo.get_claim(user_id, claim_id)
    path = Path(SHOT_DIR) / name
    if not claim or name not in claim.screenshots or not path.is_file():
        raise HTTPException(status_code=404, detail="Screenshot not found.")
    return FileResponse(path)
