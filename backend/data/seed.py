"""Seed demo data (see docs/data-model.md → Demo seed data).  Run:  python -m data.seed  (from backend/)

Loads the same demo state the in-memory store starts with (`app/mock_data.build_seed`) into
MongoDB: the demo user, 6 purchases, their claims and the activity feed. Run it again to put the
demo back to its starting state.

It REPLACES the demo user's purchases, claims and events (DEMO_USER_ID). Other users' documents
and the cached retailer policies are left alone.

The 30 days of price history go to Tiger Data, replacing whatever was recorded for the demo
products; the schema is applied first if it isn't there. If Tiger Data can't be reached that part
is skipped and said so: the API then holds price history in its own process, seeded with the
same numbers.

TODO(L5): create matching Nessie purchases here (today `python -m finance.nessie_seed` does that).
"""

from __future__ import annotations

import asyncio

from app import mock_data
from app.config import get_settings
from data import mongo, mongo_indexes, timescale


async def seed(user_id: str | None = None) -> dict[str, int]:
    """Reset `user_id`'s demo state in MongoDB. Returns how many documents of each kind were written."""
    settings = get_settings()
    user_id = user_id or settings.demo_user_id
    data = mock_data.build_seed(user_id)
    database = mongo.db()

    await mongo_indexes.ensure_indexes()
    for collection in ("purchases", "claims", "agent_events"):
        await database[collection].delete_many({"user_id": user_id})
    await database["users"].update_one(
        {"_id": user_id},
        {"$set": {"name": "Demo User", "nessie_account_id": settings.nessie_account_id or None}},
        upsert=True,
    )
    for purchase in data.purchases:
        await mongo.upsert_purchase(purchase)
    for claim in data.claims:
        await mongo.save_claim(claim)
    for event in sorted(data.activity, key=lambda e: e.time):  # oldest first, so insert order matches time
        await mongo.log_event(event)

    price_points = 0
    try:
        await timescale.migrate()
        price_points = await timescale.replace_history(data.prices)
    except timescale.TigerUnavailable as exc:
        print(f"Price history was not written: {exc}")

    return {
        "purchases": len(data.purchases), "claims": len(data.claims), "events": len(data.activity),
        "price_points": price_points,
    }


async def _main() -> None:
    try:
        await mongo.ping()
        counts = await seed()
    finally:
        await mongo.close()
        await timescale.close()
    print(f"Seeded '{get_settings().mongodb_db}' for user '{get_settings().demo_user_id}': {counts}")


if __name__ == "__main__":
    asyncio.run(_main())
