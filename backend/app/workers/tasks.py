"""Optional arq jobs. The API runs the same functions inline when Redis is down."""

from __future__ import annotations

from app.services.orchestrator import prepare_claims, run_eligibility_agent, run_price_agent, run_receipt_agent
from data.repository import repo


async def scan_new_purchases(ctx: dict, user_id: str) -> None:
    await repo.connect()
    await run_receipt_agent(user_id, demo=False)


async def poll_prices(ctx: dict) -> None:
    await repo.connect()
    for user_id in await repo.list_user_ids():
        await run_price_agent(user_id)
        await run_eligibility_agent(user_id)


async def evaluate_purchase(ctx: dict, purchase_id: str) -> None:
    await repo.connect()
    _ = purchase_id
    for user_id in await repo.list_user_ids():
        await run_eligibility_agent(user_id)
        await prepare_claims(user_id)


async def submit_claim(ctx: dict, claim_id: str) -> None:
    """Claims are submitted from the approve endpoint, which holds the user lock.
    This job does not submit anything by itself.
    """
    _ = (ctx, claim_id)


async def reconcile_refunds(ctx: dict) -> None:
    """Refunds are matched only when a user asks. This job does not invent deposits."""
    _ = ctx
