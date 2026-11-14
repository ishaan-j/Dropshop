from fastapi import APIRouter

from app.models import RetailerPolicy
from app.workers import tasks

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("/{retailer}", response_model=RetailerPolicy)
async def retailer_policy(retailer: str) -> RetailerPolicy:
    """The price-adjustment policy Dropshot is using for a retailer (window, conditions, summary).

    This is the stored copy, so it reflects any change the Grok policy watch has picked up. A
    retailer without a known policy comes back with `window_days: null`.
    """
    return await tasks.policy_for(retailer)
