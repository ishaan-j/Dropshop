"""MongoDB Atlas repository: users, purchases, retailer_policies, claims, agent_events.
Collections and indexes are documented in docs/data-model.md.

How documents map to the models in `app/models.py`:
  purchases, claims   the model's fields, with the model `id` as `_id`.
  agent_events        the model's fields; `_id` is Mongo's ObjectId, which increases with every
                      insert and so orders events logged in the same millisecond.
  retailer_policies   the model's fields plus `summarized_at`; `_id` is the lower-cased retailer.
Datetimes are stored as BSON dates (UTC, millisecond precision) and read back timezone-aware.

The client is created on first use, so importing this module never opens a connection.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pymongo import AsyncMongoClient

from app.config import get_settings
from app.models import AgentEvent, Claim, Purchase, RetailerPolicy

SERVER_SELECTION_TIMEOUT_MS = 5000  # report an unreachable cluster in 5 s instead of the default 30

_client: AsyncMongoClient | None = None


def client() -> AsyncMongoClient:
    global _client
    if _client is None:
        _client = AsyncMongoClient(
            get_settings().mongodb_uri, tz_aware=True, serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS
        )
    return _client


def db():
    """The application database (MONGODB_DB) on the cluster at MONGODB_URI."""
    return client()[get_settings().mongodb_db]


async def close() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


async def ping() -> None:
    """Raise if the cluster can't be reached or the credentials are wrong."""
    await client().admin.command("ping")


def _load(model, doc: dict | None):
    if doc is None:
        return None
    return model.model_validate({k: v for k, v in doc.items() if k != "_id"})


async def _save(collection: str, model) -> None:
    # $set rather than a full replace, so fields other code keeps on the document (for example a
    # purchase's raw `receipt`) survive an update.
    await db()[collection].update_one({"_id": model.id}, {"$set": model.model_dump()}, upsert=True)


# --- Purchases ----------------------------------------------------------------------------------


async def list_purchases(user_id: str) -> list[Purchase]:
    """A user's purchases, newest first."""
    docs = await db()["purchases"].find({"user_id": user_id}).sort([("purchased_at", -1)]).to_list()
    return [_load(Purchase, d) for d in docs]


async def get_purchase(purchase_id: str) -> Purchase | None:
    return _load(Purchase, await db()["purchases"].find_one({"_id": purchase_id}))


async def upsert_purchase(purchase: Purchase) -> Purchase:
    await _save("purchases", purchase)
    return purchase


# --- Claims -------------------------------------------------------------------------------------


async def list_claims(user_id: str) -> list[Claim]:
    """A user's claims, newest first."""
    docs = await db()["claims"].find({"user_id": user_id}).sort([("created_at", -1)]).to_list()
    return [_load(Claim, d) for d in docs]


async def get_claim(claim_id: str) -> Claim | None:
    return _load(Claim, await db()["claims"].find_one({"_id": claim_id}))


async def save_claim(claim: Claim) -> Claim:
    await _save("claims", claim)
    return claim


# --- Agent events (activity feed) ---------------------------------------------------------------


async def log_event(event: AgentEvent) -> None:
    await db()["agent_events"].insert_one(event.model_dump())


async def list_events(user_id: str, limit: int = 50) -> list[AgentEvent]:
    """A user's events, newest first. Events with the same timestamp come latest-logged first."""
    cursor = db()["agent_events"].find({"user_id": user_id}).sort([("time", -1), ("_id", -1)]).limit(limit)
    return [_load(AgentEvent, d) for d in await cursor.to_list()]


# --- Retailer policies (cached Gemini / Grok policy reads) --------------------------------------


def _policy_key(retailer: str) -> str:
    return retailer.strip().lower()


async def get_policy(retailer: str) -> RetailerPolicy | None:
    return _load(RetailerPolicy, await db()["retailer_policies"].find_one({"_id": _policy_key(retailer)}))


async def save_policy(policy: RetailerPolicy) -> None:
    fields = {**policy.model_dump(), "summarized_at": datetime.now(timezone.utc)}
    await db()["retailer_policies"].update_one({"_id": _policy_key(policy.retailer)}, {"$set": fields}, upsert=True)
