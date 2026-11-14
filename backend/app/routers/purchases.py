from fastapi import APIRouter, HTTPException

from app import jobs
from app.config import get_settings
from app.models import Purchase, PurchaseCreate
from app.store import get_store
from app.workers import tasks

router = APIRouter(prefix="/purchases", tags=["purchases"])


@router.get("", response_model=list[Purchase])
async def list_purchases() -> list[Purchase]:
    """Purchases being monitored, newest first."""
    return await get_store().list_purchases(get_settings().demo_user_id)


@router.post("/scan")
async def scan_for_purchases() -> dict:
    """Look for new purchases in receipts (Sentient OS, or the sample receipts). Runs in the background."""
    job_id = await jobs.enqueue("scan_new_purchases", get_settings().demo_user_id)
    return {"job_id": job_id}


@router.get("/{purchase_id}", response_model=Purchase)
async def get_purchase(purchase_id: str) -> Purchase:
    purchase = await get_store().get_purchase(purchase_id)
    if purchase is None:
        raise HTTPException(404, "Purchase not found")
    return purchase


@router.post("", response_model=Purchase)
async def create_purchase(body: PurchaseCreate) -> Purchase:
    """Add a purchase by hand: the fallback when receipt discovery misses one."""
    if body.price_paid_cents <= 0:
        raise HTTPException(422, "price_paid_cents must be positive")
    purchase = await tasks.register_purchase(body, user_id=get_settings().demo_user_id, source="manual")
    await tasks.log_event(
        "purchase_found",
        f"Added by you: {purchase.product_name} ({tasks.money(purchase.price_paid_cents)}, {purchase.retailer}).",
        purchase=purchase,
    )
    return purchase
