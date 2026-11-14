"""Understand a retailer's price-adjustment / price-match policy."""

from app.models import RetailerPolicy


async def get_policy(retailer: str) -> RetailerPolicy:
    """TODO(L3): fetch the retailer's policy page text, have Gemini summarize it into RetailerPolicy
    (window_days, conditions). L2 caches the result in Mongo `retailer_policies`.
    Hardcode 3 demo retailers first; generalize only if time allows.
    """
    raise NotImplementedError
