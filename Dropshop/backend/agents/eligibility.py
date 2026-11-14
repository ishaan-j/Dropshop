"""Decide whether a price drop qualifies for a refund, and for how much."""

from app.models import EligibilityResult, Purchase, RetailerPolicy


async def check(purchase: Purchase, current_price_cents: int, policy: RetailerPolicy) -> EligibilityResult:
    """TODO(L3): deterministic pre-checks first (price actually lower? inside window_days?),
    then Gemini for the fuzzy conditions (open-box, marketplace sellers, membership-only prices…).
    Return refund_cents = price_paid_cents - current_price_cents when eligible.
    """
    raise NotImplementedError
