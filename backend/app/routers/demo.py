"""Demo controls: reset the state between judge runs, make a price drop on cue, run a job now.

Only available when DEMO_MODE is on (the default).
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import finance_gateway, jobs, price_feed
from app.config import get_settings
from app.store import get_store
from app.workers import tasks


def _demo_only() -> None:
    if not get_settings().demo_mode:
        raise HTTPException(404, "Demo endpoints are disabled (DEMO_MODE=false)")


router = APIRouter(prefix="/demo", tags=["demo"], dependencies=[Depends(_demo_only)])


@router.post("/reset")
async def reset_demo() -> dict:
    """Stop running jobs and reseed the demo state. In-memory store only."""
    store = get_store()
    if store.name != "memory":
        raise HTTPException(
            409, "Reset only works with the in-memory store. Reseed the database with `python -m data.seed`."
        )
    await jobs.cancel_all()
    await store.reset()
    finance_gateway.reset_simulation(store.seed)
    user_id = get_settings().demo_user_id
    return {
        "status": "reset",
        "purchases": len(await store.list_purchases(user_id)),
        "claims": len(await store.list_claims(user_id)),
    }


class PriceDropRequest(BaseModel):
    purchase_id: str | None = None  # default: the most expensive purchase still being monitored
    percent: float = Field(15.0, gt=0, lt=100)
    new_price_cents: int | None = Field(None, gt=0)  # overrides percent


@router.post("/price-drop")
async def price_drop(body: PriceDropRequest | None = None) -> dict:
    """Drop a monitored product's price now. The poller then detects it and the agents take over."""
    body = body or PriceDropRequest()
    store = get_store()
    if body.purchase_id:
        purchase = await store.get_purchase(body.purchase_id)
        if purchase is None:
            raise HTTPException(404, "Purchase not found")
        if purchase.status not in ("monitoring", "drop_detected"):
            raise HTTPException(409, f"That purchase isn't being monitored (status: {purchase.status})")
    else:
        monitoring = [p for p in await store.list_purchases(get_settings().demo_user_id) if p.status == "monitoring"]
        if not monitoring:
            raise HTTPException(409, "No purchase is being monitored. Run a scan or reset the demo first.")
        purchase = max(monitoring, key=lambda p: p.price_paid_cents)
    old_price = await price_feed.held_price_cents(purchase, store)
    try:
        new_price = await price_feed.demo_price_drop(
            purchase, store, percent=body.percent, new_price_cents=body.new_price_cents
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    job_id = await jobs.enqueue("poll_prices")
    return {
        "purchase_id": purchase.id,
        "product_name": purchase.product_name,
        "old_price_cents": old_price,
        "new_price_cents": new_price,
        "job_id": job_id,
    }


JobName = Literal["scan_new_purchases", "poll_prices", "reconcile_refunds", "watch_policies"]


@router.post("/jobs/{name}")
async def run_job(name: JobName) -> dict:
    """Run a scheduled job now instead of waiting for its timer (for example the nightly Grok policy watch)."""
    if name == "watch_policies":
        # Run in the request so the response can say what Grok found.
        return {"job": name, "result": await tasks.watch_policies({"inline": True})}
    return {"job": name, "job_id": await jobs.enqueue(name)}
