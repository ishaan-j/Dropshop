"""Deterministic extraction for emails that use DropShop's labeled field format.

This parser does not guess. If a field is missing or the price is not explicit, it stays null.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.models import ExtractedItem, ExtractedReceipt
from app.services.rules import date_in_source, parse_price_cents, price_in_source, value_in_source

_LINE = re.compile(r"^([A-Za-z][A-Za-z ]*): (.+)$", re.MULTILINE)


def _fields(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for match in _LINE.finditer(text):
        found[match.group(1).strip().lower()] = match.group(2).strip()
    return found


def parse_labeled_email(text: str) -> ExtractedReceipt:
    fields = _fields(text)
    warnings: list[str] = []
    purchased_at = None
    raw_date = fields.get("order date")
    if raw_date:
        try:
            purchased_at = datetime.fromisoformat(raw_date).replace(tzinfo=timezone.utc)
        except ValueError:
            warnings.append("Order date was present but not an ISO date, so it was left blank.")
            purchased_at = None
    price = parse_price_cents(fields.get("price"))
    item = ExtractedItem(
        retailer=fields.get("retailer"),
        product_name=fields.get("product"),
        product_url=fields.get("product url"),
        product_id=fields.get("product id"),
        price_paid_cents=price,
        purchased_at=purchased_at,
        order_number=fields.get("order number"),
    )
    item = scrub_item(item, text)
    item.warnings = warnings + item.warnings
    missing = missing_required(item)
    item.missing_fields = missing
    return ExtractedReceipt(
        retailer=item.retailer,
        order_number=item.order_number,
        purchased_at=item.purchased_at,
        items=[item] if any([item.retailer, item.product_name, item.price_paid_cents]) else [],
        extractor="deterministic",
        warnings=warnings,
    )


def scrub_item(item: ExtractedItem, source: str) -> ExtractedItem:
    """Drop any value that does not literally appear in the source text."""
    warnings = list(item.warnings)
    updates: dict = {}
    checks = {
        "retailer": item.retailer,
        "product_name": item.product_name,
        "product_url": item.product_url,
        "product_id": item.product_id,
        "order_number": item.order_number,
    }
    for field, value in checks.items():
        if value and not value_in_source(value, source):
            updates[field] = None
            warnings.append(f"Removed {field} because it did not appear in the source text.")
    if item.price_paid_cents is not None and not price_in_source(item.price_paid_cents, source):
        updates["price_paid_cents"] = None
        warnings.append("Removed price because that amount does not appear in the source text.")
    if item.purchased_at is not None and not date_in_source(item.purchased_at, source):
        updates["purchased_at"] = None
        warnings.append("Removed purchase date because that date does not appear in the source text.")
    scrubbed = item.model_copy(update=updates)
    scrubbed.warnings = warnings
    return scrubbed


def missing_required(item: ExtractedItem) -> list[str]:
    missing = []
    if not item.retailer:
        missing.append("retailer")
    if not item.product_name:
        missing.append("product_name")
    if item.price_paid_cents is None:
        missing.append("price_paid_cents")
    if item.purchased_at is None:
        missing.append("purchased_at")
    return missing


def scrub_receipt(receipt: ExtractedReceipt, source: str) -> ExtractedReceipt:
    items = []
    warnings = list(receipt.warnings)
    for item in receipt.items:
        clean = scrub_item(item, source)
        clean.missing_fields = missing_required(clean)
        warnings.extend(clean.warnings)
        items.append(clean)
    return receipt.model_copy(update={"items": items, "warnings": warnings})
