"""Capital One Nessie sandbox client.

Customer endpoints and the `key` query parameter are documented at
http://api.nessieisreal.com/ and https://nessieisreal.com/docs.
Amounts are dollars, not cents. This client never invents a response.
"""

from __future__ import annotations

import httpx

from app.config import get_settings

NESSIE_DOCS = "http://api.nessieisreal.com/"


class NessieNotConfigured(RuntimeError):
    pass


class NessieError(RuntimeError):
    pass


def configured() -> bool:
    return bool(get_settings().nessie_api_key.strip())


async def _request(method: str, path: str, body: dict | None = None):
    settings = get_settings()
    if not settings.nessie_api_key.strip():
        raise NessieNotConfigured("Nessie API key is not configured.")
    url = settings.nessie_base_url.rstrip("/") + path
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.request(method, url, params={"key": settings.nessie_api_key}, json=body)
    except httpx.HTTPError as exc:
        raise NessieError(f"Nessie request failed: {exc.__class__.__name__}") from exc
    if response.status_code >= 400:
        raise NessieError(f"Nessie returned HTTP {response.status_code} for {path}.")
    if not response.content:
        return {}
    return response.json()


async def list_customers() -> list:
    data = await _request("GET", "/customers")
    if isinstance(data, list):
        return data
    raise NessieError("Nessie customers response was not a list.")


async def create_customer(first_name: str, last_name: str) -> dict:
    return await _request(
        "POST",
        "/customers",
        {
            "first_name": first_name,
            "last_name": last_name,
            "address": {
                "street_number": "650",
                "street_name": "N Pleasant St",
                "city": "Amherst",
                "state": "MA",
                "zip": "01003",
            },
        },
    )


async def list_accounts(customer_id: str) -> list:
    data = await _request("GET", f"/customers/{customer_id}/accounts")
    if isinstance(data, list):
        return data
    raise NessieError("Nessie accounts response was not a list.")


async def create_account(customer_id: str, nickname: str = "DropShop sandbox") -> dict:
    return await _request(
        "POST",
        f"/customers/{customer_id}/accounts",
        {"type": "Checking", "nickname": nickname, "rewards": 0, "balance": 1000},
    )


async def list_purchases(account_id: str) -> list:
    data = await _request("GET", f"/accounts/{account_id}/purchases")
    if isinstance(data, list):
        return data
    raise NessieError("Nessie purchases response was not a list.")


async def list_deposits(account_id: str) -> list:
    data = await _request("GET", f"/accounts/{account_id}/deposits")
    if isinstance(data, list):
        return data
    raise NessieError("Nessie deposits response was not a list.")


async def create_deposit(account_id: str, amount_cents: int, description: str) -> dict:
    from datetime import datetime, timezone

    return await _request(
        "POST",
        f"/accounts/{account_id}/deposits",
        {
            "medium": "balance",
            "transaction_date": datetime.now(timezone.utc).date().isoformat(),
            "status": "completed",
            "amount": round(amount_cents / 100, 2),
            "description": description,
        },
    )


async def list_merchants() -> list:
    data = await _request("GET", "/merchants")
    if isinstance(data, list):
        return data
    raise NessieError("Nessie merchants response was not a list.")
