from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.deps import current_user, http_error
from app.limiter import allow
from app.models import Purchase, PurchaseCreate
from app.services.orchestrator import WorkflowError, _id, _now, _slug, run_receipt_agent
from data.repository import repo

router = APIRouter(prefix="/purchases", tags=["purchases"])


@router.get("", response_model=list[Purchase])
async def list_purchases(user_id: str = Depends(current_user)) -> list[Purchase]:
    try:
        return await repo.list_purchases(user_id)
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.get("/{purchase_id}", response_model=Purchase)
async def get_purchase(purchase_id: str, user_id: str = Depends(current_user)) -> Purchase:
    try:
        purchase = await repo.get_purchase(user_id, purchase_id)
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found.")
    return purchase


@router.post("", response_model=Purchase)
async def create_purchase(body: PurchaseCreate, user_id: str = Depends(current_user)) -> Purchase:
    purchased = body.purchased_at
    if purchased.tzinfo is None:
        purchased = purchased.replace(tzinfo=timezone.utc)
    if purchased > datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Purchase date cannot be in the future.")
    now = _now()
    purchase = Purchase(
        id=_id("pur_"),
        user_id=user_id,
        retailer=body.retailer.strip(),
        product_name=body.product_name.strip(),
        product_url=body.product_url,
        product_id=body.product_id or _slug(body.retailer, body.product_name),
        price_paid_cents=body.price_paid_cents,
        purchased_at=purchased,
        order_number=body.order_number,
        source="manual",
        data_origin="demo",
        created_at=now,
        updated_at=now,
    )
    if not purchase.retailer or not purchase.product_name:
        raise HTTPException(status_code=422, detail="Retailer and product name are required.")
    try:
        saved = await repo.save_purchase(purchase)
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc
    return saved


@router.post("/scan")
async def scan_for_purchases(user_id: str = Depends(current_user)) -> dict:
    if not allow(f"scan:{user_id}", 8):
        raise HTTPException(status_code=429, detail="Too many scans.")
    try:
        run = await run_receipt_agent(user_id, demo=False)
    except WorkflowError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc
    return {"run_id": run.id, "status": run.status, "summary": run.result_summary, "error": run.error}
