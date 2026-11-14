from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.deps import current_user
from app.models import IntegrationStatus, Preferences, Refund
from app.services.dashboard import integration_statuses
from app.services.orchestrator import WorkflowError, reconcile_nessie, record_demo_refund
from data.repository import repo
from finance import nessie
from integrations import gmail

router = APIRouter(tags=["integrations"])


class PreferenceUpdate(BaseModel):
    notify_price_drop: bool = True
    notify_deadline: bool = True
    notify_claim: bool = True
    sentient_read_enabled: bool = False


class NessieAccountRequest(BaseModel):
    first_name: str = Field(default="Drop", max_length=40)
    last_name: str = Field(default="Shop", max_length=40)


@router.get("/integrations", response_model=list[IntegrationStatus])
async def integrations(user_id: str = Depends(current_user)) -> list[IntegrationStatus]:
    return await integration_statuses(user_id)


@router.post("/integrations/recheck")
async def recheck(user_id: str = Depends(current_user)) -> dict:
    await repo.reconnect()
    return {"integrations": await integration_statuses(user_id)}


@router.get("/preferences", response_model=Preferences)
async def get_preferences(user_id: str = Depends(current_user)) -> Preferences:
    return await repo.get_preferences(user_id)


@router.put("/preferences", response_model=Preferences)
async def put_preferences(body: PreferenceUpdate, user_id: str = Depends(current_user)) -> Preferences:
    prefs = Preferences(user_id=user_id, **body.model_dump())
    return await repo.save_preferences(prefs)


@router.get("/integrations/gmail/start")
async def gmail_start(user_id: str = Depends(current_user)) -> dict:
    try:
        return {"url": gmail.start_url(user_id)}
    except gmail.GmailNotConfigured as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/integrations/gmail/callback")
async def gmail_callback(code: str = "", state: str = "", error: str = "") -> RedirectResponse:
    target = "http://localhost:3000/app/settings"
    if error or not code:
        return RedirectResponse(f"{target}?gmail=error")
    user_id = gmail.take_state(state)
    if not user_id:
        return RedirectResponse(f"{target}?gmail=state")
    try:
        await gmail.exchange_code(user_id, code)
    except gmail.GmailError:
        return RedirectResponse(f"{target}?gmail=error")
    return RedirectResponse(f"{target}?gmail=connected")


@router.get("/integrations/gmail")
async def gmail_status(user_id: str = Depends(current_user)) -> dict:
    return await gmail.connection_view(user_id)


@router.post("/integrations/gmail/disconnect")
async def gmail_disconnect(user_id: str = Depends(current_user)) -> dict:
    await gmail.disconnect(user_id)
    return {"connected": False}


@router.get("/integrations/nessie/customers")
async def nessie_customers(user_id: str = Depends(current_user)) -> dict:
    _ = user_id
    if not nessie.configured():
        raise HTTPException(status_code=409, detail="Nessie is not connected.")
    try:
        customers = await nessie.list_customers()
    except nessie.NessieError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"mode": "sandbox", "customers": customers}


@router.post("/integrations/nessie/sandbox-account")
async def nessie_account(body: NessieAccountRequest, user_id: str = Depends(current_user)) -> dict:
    if not nessie.configured():
        raise HTTPException(status_code=409, detail="Nessie is not connected.")
    try:
        customer = await nessie.create_customer(body.first_name, body.last_name)
        customer_id = customer.get("_id")
        if not customer_id:
            raise HTTPException(status_code=502, detail="Nessie did not return a customer id.")
        account = await nessie.create_account(customer_id)
    except nessie.NessieError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    account_id = account.get("_id")
    await repo.save_connection(
        user_id,
        {"nessie_customer_id": customer_id, "nessie_account_id": account_id},
    )
    return {
        "mode": "sandbox",
        "customer_id": customer_id,
        "account_id": account_id,
        "note": "Created in the Nessie sandbox. This is not your bank.",
    }


@router.get("/integrations/nessie/transactions")
async def nessie_transactions(user_id: str = Depends(current_user)) -> dict:
    account_id = (await repo.get_connection(user_id)).get("nessie_account_id") or get_settings().nessie_account_id
    if not nessie.configured():
        raise HTTPException(status_code=409, detail="Nessie is not connected.")
    if not account_id:
        raise HTTPException(status_code=409, detail="No sandbox account is saved yet.")
    try:
        purchases = await nessie.list_purchases(account_id)
        deposits = await nessie.list_deposits(account_id)
    except nessie.NessieError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"mode": "sandbox", "account_id": account_id, "purchases": purchases, "deposits": deposits}


@router.get("/refunds")
async def list_refunds(user_id: str = Depends(current_user)) -> list[Refund]:
    return await repo.list_refunds(user_id)


@router.post("/refunds/{claim_id}/demo", response_model=Refund)
async def demo_refund(claim_id: str, user_id: str = Depends(current_user)) -> Refund:
    try:
        return await record_demo_refund(user_id, claim_id)
    except WorkflowError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/refunds/{claim_id}/nessie", response_model=Refund)
async def nessie_refund(claim_id: str, user_id: str = Depends(current_user)) -> Refund:
    try:
        return await reconcile_nessie(user_id, claim_id)
    except WorkflowError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
