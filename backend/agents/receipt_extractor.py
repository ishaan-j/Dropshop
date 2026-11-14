"""Turn order-confirmation text into structured items, then reject invented fields."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agents.gemini_client import GeminiCallError, GeminiNotConfigured, configured, generate_structured
from agents.parsing import missing_required, parse_labeled_email, scrub_receipt
from app.models import ExtractedItem, ExtractedReceipt


class _GeminiItem(BaseModel):
    retailer: str | None = None
    product_name: str | None = None
    product_url: str | None = None
    product_id: str | None = None
    price_paid_cents: int | None = None
    purchased_at: str | None = None
    order_number: str | None = None


class _GeminiReceipt(BaseModel):
    items: list[_GeminiItem] = Field(default_factory=list)


async def extract(raw_text: str) -> ExtractedReceipt:
    if configured():
        try:
            return await _extract_with_gemini(raw_text)
        except (GeminiNotConfigured, GeminiCallError) as exc:
            fallback = parse_labeled_email(raw_text)
            fallback.warnings.append(f"Gemini failed ({exc}). Fell back only for the labeled field format.")
            if fallback.items and not missing_required(fallback.items[0]):
                fallback.extractor = "deterministic"
                return fallback
            fallback.extractor = "none"
            fallback.warnings.append("The email did not match the labeled format, so no purchase was extracted.")
            return fallback
    parsed = parse_labeled_email(raw_text)
    if parsed.items and missing_required(parsed.items[0]):
        parsed.warnings.append("Required fields are missing. Nothing was guessed.")
    if not parsed.items:
        parsed.extractor = "none"
        parsed.warnings.append("No labeled purchase fields were found, and Gemini is not configured.")
    return parsed


async def _extract_with_gemini(raw_text: str) -> ExtractedReceipt:
    prompt = (
        "Extract purchase lines from this order email. "
        "Use null for anything not explicitly stated. Do not guess prices, dates, retailers, or urls.\n\n"
        f"{raw_text}"
    )
    raw = await generate_structured(prompt, _GeminiReceipt)
    items: list[ExtractedItem] = []
    for item in raw.items:
        purchased = None
        if item.purchased_at:
            from datetime import datetime, timezone

            try:
                purchased = datetime.fromisoformat(item.purchased_at.replace("Z", "+00:00"))
                if purchased.tzinfo is None:
                    purchased = purchased.replace(tzinfo=timezone.utc)
            except ValueError:
                purchased = None
        items.append(
            ExtractedItem(
                retailer=item.retailer,
                product_name=item.product_name,
                product_url=item.product_url,
                product_id=item.product_id,
                price_paid_cents=item.price_paid_cents,
                purchased_at=purchased,
                order_number=item.order_number,
            )
        )
    receipt = scrub_receipt(
        ExtractedReceipt(items=items, extractor="gemini"),
        raw_text,
    )
    for item in receipt.items:
        item.missing_fields = missing_required(item)
    return receipt
