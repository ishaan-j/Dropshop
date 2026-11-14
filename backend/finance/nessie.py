"""Capital One Nessie sandbox client. Docs: http://api.nessieisreal.com/documentation

Used for: confirming purchases against card transactions, and detecting the refund deposit
(a retailer refund is modelled as a deposit on the demo account).

This module is the live client only. Every call raises `NessieError` (or an httpx error) when
Nessie is down or rejects the request. The mock fallback lives one layer up, in
`app/finance_gateway.py`: it simulates the bank in MOCK_MODE and takes over when a call here fails.

Nessie amounts are dollars (numbers); this client takes cents and converts. Records come back as
Nessie returns them: dicts with `_id`, `amount`, `description` and a date field.

Nessie keeps whole dollars only: a $399.99 purchase is stored and returned as 399. Callers that
compare amounts (Layer 2's refund and card-charge matching) have to allow for the dropped cents.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import httpx

from app.config import get_settings

TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class NessieError(RuntimeError):
    """Nessie rejected the request or isn't configured."""


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


async def _request(method: str, path: str, *, json: dict | None = None) -> Any:
    settings = get_settings()
    if not settings.nessie_api_key:
        raise NessieError("NESSIE_API_KEY is not set")
    url = f"{settings.nessie_base_url.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # The key goes in the query string, so never put the URL in a log or error message.
        response = await client.request(method, url, params={"key": settings.nessie_api_key}, json=json)
    if response.status_code >= 400:
        raise NessieError(f"Nessie {method} {path} failed: {response.status_code} {response.text[:200]}")
    return response.json()


def _created(body: Any) -> dict:
    """POSTs answer `{code, message, objectCreated}`; return the created object."""
    if isinstance(body, dict):
        return body.get("objectCreated", body)
    return {}


async def create_demo_customer_and_account(
    first_name: str = "Demo", last_name: str = "User", balance_cents: int = 500_000
) -> dict:
    """Create a sandbox customer with a checking account. Returns `{customer_id, account_id}`."""
    customer = _created(
        await _request(
            "POST", "/customers",
            json={
                "first_name": first_name, "last_name": last_name,
                "address": {"street_number": "1", "street_name": "Main St", "city": "McLean", "state": "VA", "zip": "22102"},
            },
        )
    )
    account = _created(
        await _request(
            "POST", f"/customers/{customer['_id']}/accounts",
            json={"type": "Checking", "nickname": "Dropshot Demo", "rewards": 0, "balance": balance_cents // 100},
        )
    )
    return {"customer_id": customer["_id"], "account_id": account["_id"]}


async def get_account(account_id: str) -> dict:
    """The account record, including its `balance` in dollars."""
    return await _request("GET", f"/accounts/{account_id}")


async def list_purchases(account_id: str) -> list[dict]:
    """Card purchases on the account. Used to confirm a discovered purchase."""
    return await _request("GET", f"/accounts/{account_id}/purchases")


async def create_merchant(name: str, category: str = "retail") -> dict:
    """Create a merchant to attach seeded purchases to. Returns the merchant record."""
    return _created(
        await _request(
            "POST", "/merchants",
            json={
                "name": name, "category": category,
                "address": {"street_number": "1", "street_name": "Market St", "city": "McLean", "state": "VA", "zip": "22102"},
                "geocode": {"lat": 38.93, "lng": -77.18},
            },
        )
    )


async def create_purchase(
    account_id: str, merchant_id: str, amount_cents: int, description: str, purchase_date: date | None = None
) -> dict:
    """Record a card purchase (seed data). Returns the purchase record."""
    return _created(
        await _request(
            "POST", f"/accounts/{account_id}/purchases",
            json={
                "merchant_id": merchant_id, "medium": "balance",
                "purchase_date": (purchase_date.isoformat() if purchase_date else _today()),
                "amount": amount_cents / 100, "status": "pending", "description": description,
            },
        )
    )


async def list_deposits(account_id: str) -> list[dict]:
    """Deposits on the account. `reconcile_refunds` looks for the retailer's refund here."""
    return await _request("GET", f"/accounts/{account_id}/deposits")


async def simulate_refund(account_id: str, amount_cents: int, description: str) -> dict:
    """The demo 'retailer refund lands' moment: a deposit on the account. Returns the deposit record."""
    return _created(
        await _request(
            "POST", f"/accounts/{account_id}/deposits",
            json={
                "medium": "balance", "transaction_date": _today(), "status": "pending",
                "amount": amount_cents / 100, "description": description,
            },
        )
    )
