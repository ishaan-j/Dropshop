from fastapi import APIRouter, HTTPException

from app import mock_data
from app.config import get_settings
from app.models import Purchase, PurchaseCreate

router = APIRouter(prefix="/purchases", tags=["purchases"])
settings = get_settings()


@router.get("", response_model=list[Purchase])
async def list_purchases() -> list[Purchase]:
    if settings.mock_mode:
        return mock_data.PURCHASES
    # TODO(L2): return await data.mongo.list_purchases(settings.demo_user_id)
    raise HTTPException(501, "Not implemented")


@router.get("/{purchase_id}", response_model=Purchase)
async def get_purchase(purchase_id: str) -> Purchase:
    if settings.mock_mode:
        for p in mock_data.PURCHASES:
            if p.id == purchase_id:
                return p
        raise HTTPException(404, "Purchase not found")
    # TODO(L2): data.mongo.get_purchase
    raise HTTPException(501, "Not implemented")


@router.post("", response_model=Purchase)
async def create_purchase(body: PurchaseCreate) -> Purchase:
    # TODO(L2): derive product_id + adjustment_window_ends (via agents.policy_reader), save, start monitoring
    raise HTTPException(501, "Not implemented")


@router.post("/scan")
async def scan_for_purchases() -> dict:
    # TODO(L2): enqueue workers.tasks.scan_new_purchases via arq and return its job id
    return {"job_id": "mock-job"}
