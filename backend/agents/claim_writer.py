"""Generate the human-readable explanation + form text for a claim."""

from __future__ import annotations

from pydantic import BaseModel

from agents import grok_bot
from agents.gemini_client import generate_structured
from app.models import EligibilityResult, Purchase


class _Text(BaseModel):
    text: str


def _money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _facts(purchase: Purchase, result: EligibilityResult) -> str:
    new_price = purchase.price_paid_cents - result.refund_cents
    lines = [
        f"Retailer: {purchase.retailer}",
        f"Product: {purchase.product_name}",
        f"Order number: {purchase.order_number or 'not available'}",
        f"Purchased: {purchase.purchased_at:%B %d, %Y}",
        f"Price paid: {_money(purchase.price_paid_cents)}",
        f"Current price: {_money(new_price)}",
        f"Refund owed: {_money(result.refund_cents)}",
        f"Policy basis: {result.policy_excerpt or result.reason}",
    ]
    return "\n".join(lines)


def _require_eligible(result: EligibilityResult) -> None:
    if not result.eligible or result.refund_cents <= 0:
        raise ValueError("Can't write a claim for an ineligible result")


async def explain(purchase: Purchase, result: EligibilityResult) -> str:
    """Short, friendly explanation shown on the claim card in the dashboard."""
    _require_eligible(result)
    fallback = (
        f"{purchase.retailer} dropped the price of {purchase.product_name} from "
        f"{_money(purchase.price_paid_cents)} to "
        f"{_money(purchase.price_paid_cents - result.refund_cents)}, and your purchase is still "
        f"inside its price-adjustment window. You're owed {_money(result.refund_cents)}."
    )
    prompt = (
        "Write a friendly 1-2 sentence explanation for a shopper of why they qualify for a price "
        "adjustment refund. Mention the retailer, the product, the amounts and the policy basis. "
        "Use only the facts below; never invent details. Plain text, no markdown.\n\n"
        + _facts(purchase, result)
    )
    return (await generate_structured(prompt, _Text, mock=_Text(text=fallback))).text.strip()


def _draft_is_faithful(text: str, purchase: Purchase, result: EligibilityResult) -> bool:
    """A claim draft must state the amounts (and order number) exactly as we have them."""
    new_price = purchase.price_paid_cents - result.refund_cents
    required = [_money(result.refund_cents), _money(purchase.price_paid_cents), _money(new_price)]
    if purchase.order_number:
        required.append(purchase.order_number)
    return 40 <= len(text) <= 1200 and all(fact in text for fact in required)


async def form_message(purchase: Purchase, result: EligibilityResult) -> str:
    """The message the bot pastes into the retailer's claim/chat form.

    Written by Grok (the claim agent) when it's available and its draft states the facts exactly;
    otherwise by Gemini; otherwise from a template.
    """
    _require_eligible(result)
    new_price = purchase.price_paid_cents - result.refund_cents
    draft = await grok_bot.write_claim_message(_facts(purchase, result))
    if draft and _draft_is_faithful(draft, purchase, result):
        return draft
    fallback = (
        f"Hello, I'd like to request a price adjustment on order "
        f"{purchase.order_number or '(order number on file)'}. I purchased {purchase.product_name} "
        f"on {purchase.purchased_at:%B %d, %Y} for {_money(purchase.price_paid_cents)}, and it is now "
        f"listed at {_money(new_price)}. Per your price-adjustment policy, please refund the "
        f"{_money(result.refund_cents)} difference to my original payment method. Thank you!"
    )
    prompt = (
        "Write a polite, concise message (3-4 sentences) a customer sends to a retailer's support "
        "form requesting a price adjustment. Include the order number, product, purchase date, "
        "both prices, and the refund amount requested. Reference the policy basis. Use only the "
        "facts below; never invent details. Plain text, no markdown, no subject line.\n\n"
        + _facts(purchase, result)
    )
    return (await generate_structured(prompt, _Text, mock=_Text(text=fallback))).text.strip()
