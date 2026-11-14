"""Deterministic price-recovery rules. Gemini cannot override these."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from app.models import ClaimStatus

OPEN_CLAIM_STATUSES = {"awaiting_approval", "submitting", "submitted", "refund_received"}
CLAIM_TRANSITIONS: dict[str, set[str]] = {
    "awaiting_approval": {"submitting", "rejected"},
    "submitting": {"submitted", "failed", "awaiting_approval"},
    "submitted": {"refund_received", "rejected", "failed"},
    "failed": {"awaiting_approval"},
    "rejected": set(),
    "refund_received": set(),
}
AUTOMATED_RETAILER = "Harbor & Co"


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def price_difference_cents(paid_cents: int, current_cents: int) -> int:
    if paid_cents < 0 or current_cents < 0:
        raise ValueError("prices must be non-negative")
    return max(0, paid_cents - current_cents)


def adjustment_deadline(purchased_at: datetime, window_days: int) -> datetime:
    if window_days < 0:
        raise ValueError("window_days must be non-negative")
    return utc(purchased_at) + timedelta(days=window_days)


def window_is_open(purchased_at: datetime, window_days: int, now: datetime | None = None) -> bool:
    now = utc(now or datetime.now(timezone.utc))
    return now <= adjustment_deadline(purchased_at, window_days)


def norm(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def duplicate_key(
    retailer: str,
    product_name: str,
    order_number: str | None,
    price_paid_cents: int,
    purchased_at: datetime,
) -> tuple[str, ...]:
    if order_number:
        return (norm(retailer), norm(order_number), norm(product_name))
    return (norm(retailer), norm(product_name), str(price_paid_cents), utc(purchased_at).date().isoformat())


def can_transition(current: ClaimStatus, target: ClaimStatus) -> bool:
    return target in CLAIM_TRANSITIONS.get(current, set())


def claim_reuse(existing_status: ClaimStatus | None) -> str:
    """create, reuse, or block a second claim for the same purchase."""
    if existing_status is None or existing_status == "rejected":
        return "create"
    if existing_status in {"failed", "awaiting_approval"}:
        return "reuse"
    return "block"


def automation_permitted(retailer: str) -> bool:
    return retailer == AUTOMATED_RETAILER


def evaluate_eligibility(
    *,
    paid_cents: int,
    current_cents: int | None,
    price_source: str | None,
    purchased_at: datetime,
    window_days: int | None,
    policy_url: str | None,
    final_sale: bool,
    exclusions: list[str],
    now: datetime | None = None,
) -> dict:
    """A lower price is not enough. Policy, window, exclusions, and source all count."""
    now = utc(now or datetime.now(timezone.utc))
    evidence: list[str] = []
    if policy_url:
        evidence.append(f"Policy source: {policy_url}")
    if price_source:
        evidence.append(f"Price source: {price_source}")
    else:
        evidence.append("No price source recorded.")

    if current_cents is None or not price_source:
        return _decision(
            False,
            True,
            0,
            "No verified current price, so eligibility was not decided.",
            evidence,
        )
    if window_days is None:
        return _decision(
            False,
            True,
            0,
            "No verified adjustment window is on file for this retailer.",
            evidence,
        )

    deadline = adjustment_deadline(purchased_at, window_days)
    evidence.append(f"Adjustment deadline: {deadline.isoformat()}")
    difference = price_difference_cents(paid_cents, current_cents)
    evidence.append(f"Paid {paid_cents} cents. Current {current_cents} cents. Difference {difference} cents.")

    if now > deadline:
        return _decision(False, False, 0, "The adjustment window has closed.", evidence)
    if final_sale:
        evidence.append("The product page marks this item Final Sale.")
        if any("final sale" in item.lower() for item in exclusions):
            evidence.append("The policy text lists Final Sale as an exclusion.")
        return _decision(
            False,
            False,
            0,
            "Final Sale items are excluded, even though the price is lower.",
            evidence,
        )
    if difference <= 0:
        return _decision(False, False, 0, "The verified current price is not below the purchase price.", evidence)
    if price_source == "demo_catalog":
        evidence.append("This price comes from the DropShop demo catalog, not a live retailer.")
    return _decision(
        True,
        False,
        difference,
        "The verified price is lower, the item is inside the window, and no listed exclusion applies. "
        "This is a potential difference, not a promise that the retailer will pay it.",
        evidence,
    )


def _decision(eligible: bool, needs_review: bool, refund_cents: int, reason: str, evidence: list[str]) -> dict:
    return {
        "eligible": eligible,
        "needs_review": needs_review,
        "refund_cents": refund_cents if eligible else 0,
        "reason": reason,
        "evidence": evidence,
    }


def match_deposit(
    expected_cents: int,
    claim_id: str,
    deposits: list[dict],
    used_ids: set[str],
) -> dict | None:
    """Match only a sandbox deposit that names this claim and has the same amount."""
    expected = round(expected_cents / 100, 2)
    marker = f"dropshop-claim:{claim_id}"
    for deposit in deposits:
        external_id = str(deposit.get("_id") or deposit.get("id") or "")
        if not external_id or external_id in used_ids:
            continue
        description = str(deposit.get("description") or "")
        try:
            amount = float(deposit.get("amount"))
        except (TypeError, ValueError):
            continue
        if marker in description and abs(amount - expected) < 0.011:
            return deposit
    return None


def explain_unmatched(expected_cents: int, claim_id: str, deposits: list[dict]) -> str:
    expected = round(expected_cents / 100, 2)
    marker = f"dropshop-claim:{claim_id}"
    close = []
    for deposit in deposits:
        try:
            amount = float(deposit.get("amount"))
        except (TypeError, ValueError):
            continue
        if abs(amount - expected) < 0.011:
            close.append(str(deposit.get("_id") or deposit.get("id") or "unknown"))
    if close:
        return (
            f"Found sandbox deposit(s) {', '.join(close)} for ${expected:.2f}, "
            f"but none include the marker {marker}, so they were not matched."
        )
    return f"No sandbox deposit includes {marker} for ${expected:.2f}."


def allocation_allowed(recovered_cents: int, requested_cents: int, already_allocated_cents: int) -> tuple[bool, str]:
    if requested_cents <= 0:
        return False, "Allocation amount must be greater than zero."
    if requested_cents + already_allocated_cents > recovered_cents:
        return False, "That allocation is larger than recovered savings still available."
    return True, "Within recovered savings."


def prose_amounts_ok(text: str, allowed_cents: list[int]) -> bool:
    allowed = {f"{cents / 100:.2f}" for cents in allowed_cents}
    found = re.findall(r"\$(\d+\.\d{2})", text)
    return all(amount in allowed for amount in found)


def parse_price_cents(raw: str | None) -> int | None:
    if not raw:
        return None
    match = re.search(r"\$?\s*(\d+)\.(\d{2})", raw)
    if not match:
        return None
    return int(match.group(1)) * 100 + int(match.group(2))


def parse_policy_text(text: str) -> dict:
    window = None
    match = re.search(r"Window:\s*(\d+)\s*days", text, re.IGNORECASE)
    if match:
        window = int(match.group(1))
    exclusions = []
    if re.search(r"final sale", text, re.IGNORECASE):
        exclusions.append("final sale")
    return {"window_days": window, "exclusions": exclusions}


def value_in_source(value: str | None, source: str) -> bool:
    if value is None or value == "":
        return True
    return value.lower() in source.lower()


def price_in_source(cents: int | None, source: str) -> bool:
    if cents is None:
        return True
    rendered = f"{cents / 100:.2f}"
    return rendered in source


def date_in_source(value: datetime | None, source: str) -> bool:
    if value is None:
        return True
    return utc(value).date().isoformat() in source


def submission_matches(claim_status: str, order_number: str | None, refund_cents: int, body: dict) -> bool:
    if claim_status != "submitting":
        return False
    if not order_number or body.get("order_number") != order_number:
        return False
    return body.get("refund_cents") == refund_cents


def latest_market_point(points: list[dict]) -> dict | None:
    market = [point for point in points if point.get("source") != "purchase_record"]
    if not market:
        return None
    return max(market, key=lambda point: point["time"])
