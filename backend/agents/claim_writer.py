"""Claim copy uses verified numbers. A template is the default; Gemini may rephrase it."""

from __future__ import annotations

from pydantic import BaseModel

from agents.gemini_client import GeminiCallError, GeminiNotConfigured, configured, generate_structured
from app.models import EligibilityResult, Purchase, RetailerPolicy
from app.services.rules import prose_amounts_ok


class _Copy(BaseModel):
    explanation: str
    form_message: str
    missing_information: list[str]


def money(cents: int) -> str:
    return f"${cents / 100:.2f}"


def template_explanation(purchase: Purchase, result: EligibilityResult, policy: RetailerPolicy) -> str:
    window = f"{policy.window_days} days" if policy.window_days is not None else "an unknown window"
    current = money(purchase.current_price_cents) if purchase.current_price_cents is not None else "unknown"
    return (
        f"{purchase.retailer} lists a price-adjustment window of {window} "
        f"(source: {policy.policy_url or 'not recorded'}). "
        f"You paid {money(purchase.price_paid_cents)} for {purchase.product_name}. "
        f"The current {purchase.price_source or 'unverified'} price is {current}. "
        f"Potential difference: {money(result.refund_cents)}. "
        "This is not a promise that the retailer will issue a refund. "
        f"{result.reason}"
    )


def template_form(purchase: Purchase, result: EligibilityResult) -> str:
    current = money(purchase.current_price_cents) if purchase.current_price_cents is not None else "unknown"
    return (
        f"Order {purchase.order_number or '(missing)'}: {purchase.product_name}. "
        f"Paid {money(purchase.price_paid_cents)}. Current price {current}. "
        f"Requested adjustment {money(result.refund_cents)}."
    )


def missing_information(purchase: Purchase) -> list[str]:
    missing = []
    if not purchase.order_number:
        missing.append("order number")
    if purchase.current_price_cents is None:
        missing.append("verified current price")
    if not purchase.policy_url:
        missing.append("policy source")
    return missing


async def compose(purchase: Purchase, result: EligibilityResult, policy: RetailerPolicy) -> tuple[str, str, list[str], str]:
    """Returns explanation, form message, missing fields, and source (template or gemini)."""
    missing = missing_information(purchase)
    explanation = template_explanation(purchase, result, policy)
    form_message = template_form(purchase, result)
    if not configured():
        return explanation, form_message, missing, "template"
    prompt = (
        "Rewrite the claim explanation and the form message. Use only the supplied facts. "
        "Do not say the refund is guaranteed. Do not add dollar amounts that are not in the template.\n\n"
        f"Explanation:\n{explanation}\n\nForm:\n{form_message}"
    )
    try:
        copy = await generate_structured(prompt, _Copy)
    except (GeminiNotConfigured, GeminiCallError):
        return explanation, form_message, missing, "template"
    allowed = [purchase.price_paid_cents, purchase.current_price_cents or 0, result.refund_cents]
    if not prose_amounts_ok(copy.explanation + "\n" + copy.form_message, allowed):
        return explanation, form_message, missing, "template"
    if "guaranteed" in (copy.explanation + copy.form_message).lower():
        return explanation, form_message, missing, "template"
    return copy.explanation, copy.form_message, missing or copy.missing_information, "gemini"
