"""Turn a raw receipt (email HTML/text or a photo) into structured purchases."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from agents.gemini_client import generate_structured
from app.models import ExtractedReceipt, PurchaseCreate

PROMPT_PATH = Path(__file__).parent / "prompts" / "receipt_extraction.md"

_RETAILERS = {"best buy": "Best Buy", "bestbuy": "Best Buy", "target": "Target", "amazon": "Amazon"}
_ITEM_RE = re.compile(r"^(?P<name>.+?)\s{2,}(?:Qty\s+\d+\s+)?\$(?P<price>[\d,]+\.\d{2})\s*$")
_SKIP = re.compile(
    r"subtotal|shipping|tax|total|promotion|protection plan|warranty|gift card|handling", re.I
)
_ORDER_RE = re.compile(r"Order\s*(?:Number|#)\s*:?\s*([A-Z0-9][A-Z0-9-]{4,})", re.I)


def _heuristic_parse(raw_text: str) -> ExtractedReceipt:
    """Deterministic offline fallback used when Gemini is unavailable (mock mode / API failure)."""
    header = raw_text[:300].lower()
    retailer = next((name for key, name in _RETAILERS.items() if key in header), "Unknown")

    order = _ORDER_RE.search(raw_text)
    order_number = order.group(1) if order else None

    purchased_at = None
    date_line = re.search(r"^Date:\s*(.+)$", raw_text, re.M)
    if date_line:
        try:
            purchased_at = parsedate_to_datetime(date_line.group(1).strip()).astimezone(timezone.utc)
        except (TypeError, ValueError):
            purchased_at = None

    items: list[PurchaseCreate] = []
    for line in raw_text.splitlines():
        m = _ITEM_RE.match(line.strip())
        if not m or _SKIP.search(m["name"]):
            continue
        items.append(
            PurchaseCreate(
                retailer=retailer,
                product_name=m["name"].strip(),
                price_paid_cents=round(float(m["price"].replace(",", "")) * 100),
                purchased_at=purchased_at or datetime.now(timezone.utc),
                order_number=order_number,
            )
        )
    return ExtractedReceipt(
        retailer=retailer, order_number=order_number, purchased_at=purchased_at, items=items
    )


async def extract(
    raw_text: str | None = None,
    image: bytes | None = None,
    *,
    image_mime_type: str = "image/jpeg",
) -> ExtractedReceipt:
    """Prompt Gemini with prompts/receipt_extraction.md → ExtractedReceipt.

    Falls back to a deterministic text parser when Gemini is unavailable. Image-only
    receipts have no offline fallback and need Gemini.
    """
    if not raw_text and not image:
        raise ValueError("extract() needs raw_text or image")

    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    if raw_text:
        prompt += f"\n\nReceipt text:\n---\n{raw_text}\n---"

    mock = (lambda: _heuristic_parse(raw_text)) if raw_text else None
    return await generate_structured(
        prompt,
        ExtractedReceipt,
        images=[image] if image else None,
        image_mime_type=image_mime_type,
        mock=mock,
    )
