from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.deps import current_user
from app.models import SavingsAllocation
from app.services.orchestrator import _emit, _id, _now
from app.services.rules import allocation_allowed
from data.repository import repo
from finance.solana_vault import SolanaError, assert_devnet, get_balance_lamports, verify_vault_deposit

router = APIRouter(prefix="/vault", tags=["vault"])
_ADDRESS = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


class WalletLink(BaseModel):
    address: str


class ConfirmTransfer(BaseModel):
    signature: str
    intended_cents: int = Field(default=0, ge=0)


class DemoAllocation(BaseModel):
    amount_cents: int = Field(gt=0)


@router.get("")
async def vault(user_id: str = Depends(current_user)) -> dict:
    settings = get_settings()
    connection = await repo.get_connection(user_id)
    balance = None
    verified = False
    detail = "Devnet balance has not been read."
    mode = "not_connected"
    try:
        assert_devnet(settings.solana_rpc_url)
        mode = "sandbox"
        detail = "RPC URL is Devnet. No Anchor program is deployed."
    except SolanaError as exc:
        mode = "error"
        detail = str(exc)
    if settings.solana_vault_address and mode == "sandbox":
        try:
            balance = await get_balance_lamports(settings.solana_vault_address)
            verified = True
            detail = "Vault balance was read from Devnet."
        except SolanaError as exc:
            mode = "error"
            detail = str(exc)
    elif not settings.solana_vault_address:
        detail = "SOLANA_VAULT_ADDRESS is empty, so deposits are disabled."
    return {
        "network": "devnet",
        "mode": mode,
        "detail": detail,
        "rpc_url": settings.solana_rpc_url if mode != "error" else None,
        "vault_address": settings.solana_vault_address or None,
        "wallet_address": connection.get("solana_address"),
        "balance_lamports": balance,
        "balance_verified": verified,
        "program_deployed": False,
        "allocations": await repo.list_allocations(user_id),
    }


@router.post("/wallet")
async def link_wallet(body: WalletLink, user_id: str = Depends(current_user)) -> dict:
    address = body.address.strip()
    if not _ADDRESS.match(address):
        raise HTTPException(status_code=422, detail="That does not look like a Solana public address.")
    if "private" in address.lower() or address.startswith("["):
        raise HTTPException(status_code=422, detail="Paste a public address only.")
    await repo.save_connection(user_id, {"solana_address": address})
    return {"wallet_address": address, "note": "Only the public address is stored."}


@router.post("/confirm", response_model=SavingsAllocation)
async def confirm(body: ConfirmTransfer, user_id: str = Depends(current_user)) -> SavingsAllocation:
    settings = get_settings()
    if not settings.solana_vault_address:
        raise HTTPException(status_code=409, detail="No Devnet vault address is configured.")
    try:
        verified = await verify_vault_deposit(body.signature, settings.solana_vault_address)
    except SolanaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    kind = "devnet_test"
    note = "Devnet transfer verified. It is not the retailer refund."
    if body.intended_cents > 0:
        ok, reason = await _earmark_ok(user_id, body.intended_cents)
        if not ok:
            raise HTTPException(status_code=409, detail=reason)
        kind = "savings_earmark"
        note = (
            f"Devnet transfer verified for {verified['lamports']} lamports. "
            f"The ${body.intended_cents / 100:.2f} figure is an earmark of recovered savings, not the SOL amount."
        )
    allocation = SavingsAllocation(
        id=_id("alc_"),
        user_id=user_id,
        amount_cents=body.intended_cents,
        kind=kind,  # type: ignore[arg-type]
        data_origin="sandbox",
        network="devnet",
        signature=body.signature,
        confirmed=True,
        vault_address=settings.solana_vault_address,
        lamports=verified["lamports"],
        created_at=_now(),
        note=note,
    )
    await repo.save_allocation(allocation)
    await _emit(
        user_id,
        "vault_recorded",
        note,
        agent="claim",
        run_id=allocation.id,
        origin="sandbox",
    )
    return allocation


@router.post("/demo-allocation", response_model=SavingsAllocation)
async def demo_allocation(body: DemoAllocation, user_id: str = Depends(current_user)) -> SavingsAllocation:
    ok, reason = await _earmark_ok(user_id, body.amount_cents)
    if not ok:
        raise HTTPException(status_code=409, detail=reason)
    allocation = SavingsAllocation(
        id=_id("alc_"),
        user_id=user_id,
        amount_cents=body.amount_cents,
        kind="demo_earmark",
        data_origin="demo",
        signature=None,
        confirmed=False,
        created_at=_now(),
        note="Demo ledger earmark only. No Solana transaction was created.",
    )
    await repo.save_allocation(allocation)
    await _emit(
        user_id,
        "savings_allocated",
        allocation.note,
        agent="claim",
        run_id=allocation.id,
        origin="demo",
    )
    return allocation


async def _earmark_ok(user_id: str, amount_cents: int) -> tuple[bool, str]:
    refunds = await repo.list_refunds(user_id)
    recovered = sum(item.amount_cents for item in refunds if item.status == "matched")
    allocated = sum(
        item.amount_cents
        for item in await repo.list_allocations(user_id)
        if item.kind in {"savings_earmark", "demo_earmark"}
    )
    return allocation_allowed(recovered, amount_cents, allocated)
