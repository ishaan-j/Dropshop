"""Eligibility is decided by rules. The model may comment; it may not overrule."""

from __future__ import annotations

from pydantic import BaseModel

from agents.gemini_client import GeminiCallError, GeminiNotConfigured, configured, generate_structured
from app.models import EligibilityResult, Purchase, RetailerPolicy
from app.services.rules import evaluate_eligibility, prose_amounts_ok


class _Comment(BaseModel):
    comment: str


async def check(purchase: Purchase, current_price_cents: int | None, policy: RetailerPolicy) -> EligibilityResult:
    decision = evaluate_eligibility(
        paid_cents=purchase.price_paid_cents,
        current_cents=current_price_cents,
        price_source=purchase.price_source,
        purchased_at=purchase.purchased_at,
        window_days=policy.window_days,
        policy_url=policy.policy_url,
        final_sale=purchase.final_sale,
        exclusions=policy.exclusions,
    )
    comment = None
    if configured() and decision["eligible"]:
        comment = await _comment(purchase, decision, policy)
    return EligibilityResult(
        eligible=decision["eligible"],
        needs_review=decision["needs_review"],
        refund_cents=decision["refund_cents"],
        reason=decision["reason"],
        evidence=decision["evidence"],
        policy_excerpt=policy.summary,
        model_comment=comment,
    )


async def _comment(purchase: Purchase, decision: dict, policy: RetailerPolicy) -> str | None:
    prompt = (
        "Explain this eligibility decision in two sentences using only these facts. "
        "Do not change the decision. Do not say the refund is guaranteed. "
        "Do not introduce dollar amounts other than the ones given.\n"
        f"Retailer: {purchase.retailer}\n"
        f"Product: {purchase.product_name}\n"
        f"Paid cents: {purchase.price_paid_cents}\n"
        f"Current cents: {purchase.current_price_cents}\n"
        f"Refund cents: {decision['refund_cents']}\n"
        f"Reason: {decision['reason']}\n"
        f"Policy summary: {policy.summary}\n"
    )
    try:
        result = await generate_structured(prompt, _Comment)
    except (GeminiNotConfigured, GeminiCallError):
        return None
    allowed = [purchase.price_paid_cents, purchase.current_price_cents or 0, decision["refund_cents"]]
    if not prose_amounts_ok(result.comment, allowed):
        return None
    if "guaranteed" in result.comment.lower():
        return None
    return result.comment
