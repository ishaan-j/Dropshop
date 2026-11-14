"""Capital One Nessie sandbox client. Docs: http://api.nessieisreal.com/documentation

Used for: confirming purchases against card transactions, and detecting the refund deposit
(model a retailer refund as a deposit on the demo account).
Keep a mock fallback. Nessie can be slow or down during events.
"""

from app.config import get_settings

settings = get_settings()


async def create_demo_customer_and_account() -> dict:
    """TODO(L5): POST /customers, then POST /customers/{id}/accounts → return ids (used by data/seed.py)."""
    raise NotImplementedError


async def list_purchases(account_id: str) -> list[dict]:
    """TODO(L5): GET /accounts/{id}/purchases?key=..."""
    raise NotImplementedError


async def create_purchase(account_id: str, merchant_id: str, amount_cents: int, description: str) -> dict:
    """TODO(L5): POST /accounts/{id}/purchases (seed data)."""
    raise NotImplementedError


async def list_deposits(account_id: str) -> list[dict]:
    """TODO(L5): GET /accounts/{id}/deposits. Used by reconcile_refunds to find the refund."""
    raise NotImplementedError


async def simulate_refund(account_id: str, amount_cents: int, description: str) -> dict:
    """TODO(L5): POST /accounts/{id}/deposits. The demo 'retailer refund lands' moment."""
    raise NotImplementedError
