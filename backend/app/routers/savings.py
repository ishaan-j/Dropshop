import logging

from fastapi import APIRouter

from app import finance_gateway
from app.config import get_settings
from app.models import SavingsSummary
from app.store import get_store

router = APIRouter(prefix="/savings", tags=["savings"])
logger = logging.getLogger(__name__)

PENDING = {"awaiting_approval", "submitting", "submitted"}


@router.get("", response_model=SavingsSummary)
async def savings_summary() -> SavingsSummary:
    """Totals computed from the claims, plus the Solana vault's address and balance."""
    user_id = get_settings().demo_user_id
    claims = await get_store().list_claims(user_id)
    won = [c for c in claims if c.status == "refund_received"]
    recorded = sum(c.refund_cents for c in claims if c.solana_tx_signature)
    try:
        address = await finance_gateway.vault_address(user_id)
        balance = await finance_gateway.vault_balance_cents(user_id, claims)
    except Exception as exc:  # the vault being down shouldn't blank the dashboard
        logger.warning("Vault unavailable (%s); reporting the recorded total instead", type(exc).__name__)
        address, balance = None, recorded
    return SavingsSummary(
        total_recovered_cents=sum(c.refund_cents for c in won),
        pending_cents=sum(c.refund_cents for c in claims if c.status in PENDING),
        claims_submitted=sum(1 for c in claims if c.status in ("submitted", "refund_received")),
        claims_won=len(won),
        vault_address=address,
        vault_balance_cents=balance,
    )
