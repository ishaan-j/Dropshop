"""Put the demo purchases' card charges on the Nessie sandbox account, so a discovered purchase
can be "confirmed against your card" in live mode.

Run from backend/:  python -m finance.nessie_seed

Safe to run again: a charge whose description is already on the account is skipped, and the
merchant from an earlier run is reused. Everything here is Nessie sandbox data, not real money.
"""

from __future__ import annotations

import asyncio

from app.config import get_settings
from finance import nessie

MERCHANT_NAME = "Dropshot Demo Retail"
# (description, amount in cents): the seeded demo purchases and the receipts a scan discovers.
CHARGES = [
    ("Best Buy Sony WH-1000XM6 Headphones", 39999),
    ("Target Ninja Air Fryer 6qt", 12999),
    ("Best Buy Apple AirPods Pro 3", 24999),
    ("Target Hefty Trash Bags 40ct", 949),
]


async def seed(account_id: str) -> dict:
    existing = await nessie.list_purchases(account_id)
    have = {p.get("description") for p in existing}
    merchant_id = next((p["merchant_id"] for p in existing if p.get("merchant_id")), None)
    created = []
    for description, cents in CHARGES:
        if description in have:
            continue
        if merchant_id is None:
            merchant_id = (await nessie.create_merchant(MERCHANT_NAME))["_id"]
        purchase = await nessie.create_purchase(account_id, merchant_id, cents, description)
        created.append((description, cents, purchase.get("_id")))
    return {"created": created, "already_there": len(CHARGES) - len(created), "merchant_id": merchant_id}


async def main() -> None:
    account_id = get_settings().nessie_account_id
    if not account_id:
        raise SystemExit("Set NESSIE_ACCOUNT_ID in .env first (finance.nessie.create_demo_customer_and_account creates one).")
    result = await seed(account_id)
    for description, cents, purchase_id in result["created"]:
        print(f"created  ${cents / 100:,.2f}  {description}  ({purchase_id})")
    print(f"{len(result['created'])} charge(s) created, {result['already_there']} already on the account.")


if __name__ == "__main__":
    asyncio.run(main())
