from fastapi import APIRouter, HTTPException

from app import mock_data
from app.config import get_settings
from app.models import Claim

router = APIRouter(prefix="/claims", tags=["claims"])
settings = get_settings()


@router.get("", response_model=list[Claim])
async def list_claims() -> list[Claim]:
    if settings.mock_mode:
        return mock_data.CLAIMS
    raise HTTPException(501, "Not implemented")


@router.post("/{claim_id}/approve", response_model=Claim)
async def approve_claim(claim_id: str) -> Claim:
    if settings.mock_mode:
        claim = next((c for c in mock_data.CLAIMS if c.id == claim_id), None)
        if not claim:
            raise HTTPException(404, "Claim not found")
        return claim.model_copy(update={"status": "submitting"})
    # TODO(L2): set status=submitting, enqueue workers.tasks.submit_claim(claim_id)
    raise HTTPException(501, "Not implemented")


@router.post("/{claim_id}/reject", response_model=Claim)
async def reject_claim(claim_id: str) -> Claim:
    # TODO(L2): set status=rejected
    raise HTTPException(501, "Not implemented")
