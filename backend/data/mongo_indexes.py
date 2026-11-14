"""Create MongoDB indexes. Run once per environment:  python -m data.mongo_indexes  (from backend/)

Safe to run again: creating an index that already exists does nothing. `data.seed` runs this too.
"""

from __future__ import annotations

import asyncio

from data import mongo

INDEXES = {
    "purchases": [[("user_id", 1), ("purchased_at", -1)], [("status", 1)], [("product_id", 1)]],
    "claims": [[("user_id", 1), ("created_at", -1)], [("purchase_id", 1)], [("status", 1)]],
    "agent_events": [[("user_id", 1), ("time", -1)]],
    "retailer_policies": [[("retailer", 1)]],  # unique
}
UNIQUE = {"retailer_policies"}


async def ensure_indexes() -> int:
    """Create every index in INDEXES. Returns how many were ensured."""
    database = mongo.db()
    count = 0
    for collection, indexes in INDEXES.items():
        for keys in indexes:
            await database[collection].create_index(keys, unique=collection in UNIQUE)
            count += 1
    return count


async def _main() -> None:
    try:
        print(f"Ensured {await ensure_indexes()} indexes on '{mongo.db().name}'.")
    finally:
        await mongo.close()


if __name__ == "__main__":
    asyncio.run(_main())
