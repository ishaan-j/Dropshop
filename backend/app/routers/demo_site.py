from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.demo_retailer import claim_form, home, policy, product
from app.services.orchestrator import receive_demo_submission

router = APIRouter(prefix="/demo/retailer", tags=["demo-retailer"])


class DemoForm(BaseModel):
    order_number: str
    product_name: str
    price_paid: str
    current_price: str
    refund_amount: str
    message: str = ""


@router.get("", response_class=HTMLResponse)
async def retailer_home() -> str:
    return home()


@router.get("/policy", response_class=HTMLResponse)
async def retailer_policy() -> str:
    return policy()


@router.get("/claim", response_class=HTMLResponse)
async def retailer_claim() -> str:
    return claim_form()


@router.get("/products/{product_id}", response_class=HTMLResponse)
async def retailer_product(product_id: str) -> HTMLResponse:
    page = product(product_id)
    if not page:
        return HTMLResponse("<p>Unknown demo product.</p>", status_code=404)
    return HTMLResponse(page)


@router.post("/submissions")
async def retailer_submission(body: DemoForm) -> dict:
    return await receive_demo_submission(body.model_dump())
