"""Decide whether a price drop qualifies for a refund, and for how much."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from agents.gemini_client import generate_structured
from app.models import EligibilityResult, Purchase, RetailerPolicy


class _FuzzyVerdict(BaseModel):
    """What Gemini returns for the judgement-call conditions."""

    eligible: bool
    reason: str
    policy_excerpt: str | None = None
    confidence: float = 0.0


def _money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _window_end(purchase: Purchase, policy: RetailerPolicy) -> datetime | None:
    if purchase.adjustment_window_ends:
        return purchase.adjustment_window_ends
    if policy.window_days is not None:
        return purchase.purchased_at + timedelta(days=policy.window_days)
    return None


def _precheck(
    purchase: Purchase, current_price_cents: int, policy: RetailerPolicy, now: datetime
) -> EligibilityResult | None:
    """Deterministic rules. Returns a final 'not eligible' result, or None if all pass."""
    if current_price_cents >= purchase.price_paid_cents:
        return EligibilityResult(
            eligible=False,
            reason=(
                f"Current price {_money(current_price_cents)} is not lower than the "
                f"{_money(purchase.price_paid_cents)} you paid."
            ),
            confidence=1.0,
        )
    if policy.window_days is None:
        summary = policy.summary.strip()
        looked_up = summary and "no known price-adjustment policy" not in summary.lower()
        reason = summary if looked_up else f"{policy.retailer} has no known price-adjustment policy."
        return EligibilityResult(eligible=False, reason=reason, confidence=0.9)
    end = _window_end(purchase, policy)
    if end is not None and now > end:
        return EligibilityResult(
            eligible=False,
            reason=(
                f"The {policy.window_days}-day price-adjustment window ended on "
                f"{end:%b %d, %Y}."
            ),
            policy_excerpt=policy.summary or None,
            confidence=1.0,
        )
    return None


async def check(
    purchase: Purchase,
    current_price_cents: int,
    policy: RetailerPolicy,
    *,
    now: datetime | None = None,
) -> EligibilityResult:
    """Deterministic pre-checks first (price actually lower? inside the window?), then Gemini
    for the fuzzy conditions (open-box, marketplace sellers, membership-only prices…).

    refund_cents = price_paid_cents - current_price_cents when eligible. Gemini can only
    veto; it never changes the amount. If Gemini is unavailable we trust the pre-checks.
    """
    now = now or datetime.now(timezone.utc)
    blocked = _precheck(purchase, current_price_cents, policy, now)
    if blocked:
        return blocked

    refund = purchase.price_paid_cents - current_price_cents
    passed = EligibilityResult(
        eligible=True,
        refund_cents=refund,
        reason=(
            f"Price dropped from {_money(purchase.price_paid_cents)} to "
            f"{_money(current_price_cents)} within {policy.retailer}'s "
            f"{policy.window_days}-day window; you're owed {_money(refund)}."
        ),
        policy_excerpt=policy.summary or None,
        confidence=0.7,  # deterministic pass, fuzzy conditions unverified
    )
    if not policy.conditions:
        return passed

    conditions = "\n".join(f"- {c}" for c in policy.conditions)
    prompt = (
        "You decide whether a price drop qualifies for a retailer price adjustment.\n"
        "The price is lower and the purchase is inside the window (already verified). Judge ONLY "
        "whether the policy conditions below disqualify this claim. Say eligible=false only if "
        "the facts show a condition is violated; if the facts don't say, assume it's fine and "
        "lower your confidence. Quote the relevant policy text in `policy_excerpt`.\n\n"
        f"Retailer: {policy.retailer}\nPolicy summary: {policy.summary}\nConditions:\n{conditions}\n\n"
        f"Product: {purchase.product_name}\nProduct URL: {purchase.product_url or 'unknown'}\n"
        f"Paid: {_money(purchase.price_paid_cents)}\nCurrent price: {_money(current_price_cents)}"
    )
    verdict = await generate_structured(
        prompt,
        _FuzzyVerdict,
        mock=_FuzzyVerdict(
            eligible=True, reason=passed.reason, policy_excerpt=passed.policy_excerpt, confidence=0.7
        ),
    )
    if not verdict.eligible:
        return EligibilityResult(
            eligible=False,
            reason=verdict.reason,
            policy_excerpt=verdict.policy_excerpt,
            confidence=verdict.confidence,
        )
    return EligibilityResult(
        eligible=True,
        refund_cents=refund,
        reason=passed.reason,
        policy_excerpt=verdict.policy_excerpt or passed.policy_excerpt,
        confidence=verdict.confidence,
    )
