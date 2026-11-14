from fastapi import APIRouter, HTTPException

from app import jobs
from app.config import get_settings
from app.models import Claim
from app.store import get_store

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("", response_model=list[Claim])
async def list_claims() -> list[Claim]:
    """All claims, newest first."""
    return await get_store().list_claims(get_settings().demo_user_id)


async def _claim_or_404(claim_id: str) -> Claim:
    claim = await get_store().get_claim(claim_id)
    if claim is None:
        raise HTTPException(404, "Claim not found")
    return claim


@router.post("/{claim_id}/approve", response_model=Claim)
async def approve_claim(claim_id: str) -> Claim:
    """User approval. Marks the claim `submitting` and queues the bot; poll GET /claims for the result.

    A `failed` claim can be approved again to retry. Any other status is returned unchanged, so
    approving twice never files the claim twice.
    """
    store = get_store()
    claim = await _claim_or_404(claim_id)
    if claim.status not in ("awaiting_approval", "failed"):
        return claim
    claim = await store.save_claim(claim.model_copy(update={"status": "submitting"}))
    purchase = await store.get_purchase(claim.purchase_id)
    if purchase and purchase.status != "claim_pending":
        await store.save_purchase(purchase.model_copy(update={"status": "claim_pending"}))
    await jobs.enqueue("submit_claim", claim.id)
    return claim


@router.post("/{claim_id}/reject", response_model=Claim)
async def reject_claim(claim_id: str) -> Claim:
    """User declines a drafted claim."""
    store = get_store()
    claim = await _claim_or_404(claim_id)
    if claim.status == "rejected":
        return claim
    if claim.status != "awaiting_approval":
        raise HTTPException(409, f"Only a claim awaiting approval can be rejected (this one is {claim.status})")
    claim = await store.save_claim(claim.model_copy(update={"status": "rejected"}))
    purchase = await store.get_purchase(claim.purchase_id)
    if purchase:
        # drop_detected: keep watching, but only draft again if the price falls further.
        await store.save_purchase(purchase.model_copy(update={"status": "drop_detected"}))
    return claim
