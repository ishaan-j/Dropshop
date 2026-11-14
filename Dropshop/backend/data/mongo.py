"""MongoDB Atlas repository: users, purchases, retailer_policies, claims, agent_events.
Collections and indexes are documented in docs/data-model.md.
"""

from app.config import get_settings
from app.models import AgentEvent, Claim, Purchase

settings = get_settings()

# TODO(L4):
#   from pymongo import AsyncMongoClient
#   client = AsyncMongoClient(settings.mongodb_uri)
#   db = client[settings.mongodb_db]


async def list_purchases(user_id: str) -> list[Purchase]:
    raise NotImplementedError


async def get_purchase(purchase_id: str) -> Purchase | None:
    raise NotImplementedError


async def upsert_purchase(purchase: Purchase) -> Purchase:
    raise NotImplementedError


async def list_claims(user_id: str) -> list[Claim]:
    raise NotImplementedError


async def save_claim(claim: Claim) -> Claim:
    raise NotImplementedError


async def log_event(event: AgentEvent) -> None:
    raise NotImplementedError


async def list_events(user_id: str, limit: int = 50) -> list[AgentEvent]:
    raise NotImplementedError
