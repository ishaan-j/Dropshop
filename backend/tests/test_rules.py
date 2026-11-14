from datetime import datetime, timedelta, timezone

from agents.parsing import parse_labeled_email, scrub_item
from app.models import ExtractedItem
from app.services.catalog import demo_emails
from app.services.rules import (
    adjustment_deadline,
    allocation_allowed,
    automation_permitted,
    can_transition,
    claim_reuse,
    duplicate_key,
    evaluate_eligibility,
    explain_unmatched,
    latest_market_point,
    match_deposit,
    price_difference_cents,
    prose_amounts_ok,
    submission_matches,
    window_is_open,
)

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


def test_price_difference_never_goes_negative():
    assert price_difference_cents(12800, 9900) == 2900
    assert price_difference_cents(1000, 1000) == 0
    assert price_difference_cents(1000, 1500) == 0


def test_window_uses_utc_and_inclusive_end():
    purchased = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
    deadline = adjustment_deadline(purchased, 14)
    assert deadline == datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
    assert window_is_open(purchased, 14, deadline) is True
    assert window_is_open(purchased, 14, deadline + timedelta(seconds=1)) is False
    naive = datetime(2026, 11, 1, 12)
    assert adjustment_deadline(naive, 1).tzinfo is not None


def test_eligible_drop_inside_window():
    decision = evaluate_eligibility(
        paid_cents=12800,
        current_cents=9900,
        price_source="demo_catalog",
        purchased_at=NOW - timedelta(days=6),
        window_days=14,
        policy_url="/demo/retailer/policy",
        final_sale=False,
        exclusions=["final sale"],
        now=NOW,
    )
    assert decision["eligible"] is True
    assert decision["refund_cents"] == 2900
    assert decision["needs_review"] is False


def test_final_sale_is_not_eligible_even_when_cheaper():
    decision = evaluate_eligibility(
        paid_cents=4800,
        current_cents=3600,
        price_source="demo_catalog",
        purchased_at=NOW - timedelta(days=4),
        window_days=14,
        policy_url="/demo/retailer/policy",
        final_sale=True,
        exclusions=["final sale"],
        now=NOW,
    )
    assert decision["eligible"] is False
    assert decision["refund_cents"] == 0
    assert "Final Sale" in decision["reason"]


def test_closed_window_is_not_eligible():
    decision = evaluate_eligibility(
        paid_cents=8600,
        current_cents=7200,
        price_source="demo_catalog",
        purchased_at=NOW - timedelta(days=30),
        window_days=14,
        policy_url="/demo/retailer/policy",
        final_sale=False,
        exclusions=["final sale"],
        now=NOW,
    )
    assert decision["eligible"] is False
    assert "closed" in decision["reason"]


def test_missing_price_or_policy_needs_review():
    missing_price = evaluate_eligibility(
        paid_cents=1000,
        current_cents=None,
        price_source=None,
        purchased_at=NOW,
        window_days=14,
        policy_url=None,
        final_sale=False,
        exclusions=[],
        now=NOW,
    )
    missing_policy = evaluate_eligibility(
        paid_cents=1000,
        current_cents=800,
        price_source="demo_catalog",
        purchased_at=NOW,
        window_days=None,
        policy_url=None,
        final_sale=False,
        exclusions=[],
        now=NOW,
    )
    assert missing_price["needs_review"] is True
    assert missing_policy["needs_review"] is True
    assert missing_price["eligible"] is False


def test_duplicate_key_uses_order_number():
    when = NOW
    first = duplicate_key("Harbor & Co", "Bag", "HCO-1", 100, when)
    second = duplicate_key("harbor & co", "bag", "HCO-1", 999, when)
    other = duplicate_key("Harbor & Co", "Bag", "HCO-2", 100, when)
    assert first == second
    assert first != other


def test_claim_transitions_and_reuse():
    assert can_transition("awaiting_approval", "submitting") is True
    assert can_transition("awaiting_approval", "submitted") is False
    assert can_transition("refund_received", "awaiting_approval") is False
    assert claim_reuse(None) == "create"
    assert claim_reuse("rejected") == "create"
    assert claim_reuse("failed") == "reuse"
    assert claim_reuse("submitted") == "block"
    assert claim_reuse("refund_received") == "block"


def test_deposit_match_requires_marker_and_amount():
    deposits = [
        {"_id": "a", "amount": 29.0, "description": "unrelated"},
        {"_id": "b", "amount": 29.0, "description": "dropshop-claim:clm_123"},
        {"_id": "c", "amount": 10.0, "description": "dropshop-claim:clm_123"},
    ]
    matched = match_deposit(2900, "clm_123", deposits, set())
    assert matched["_id"] == "b"
    assert match_deposit(2900, "clm_123", deposits, {"b"}) is None
    text = explain_unmatched(2900, "clm_missing", deposits)
    assert "were not matched" in text


def test_allocation_cannot_exceed_recovered():
    assert allocation_allowed(5000, 2000, 0) == (True, "Within recovered savings.")
    ok, reason = allocation_allowed(5000, 3000, 2500)
    assert ok is False
    assert "larger" in reason
    assert allocation_allowed(5000, 0, 0)[0] is False


def test_prose_rejects_unknown_amounts():
    assert prose_amounts_ok("You paid $128.00 and may see $29.00.", [12800, 9900, 2900]) is True
    assert prose_amounts_ok("You are owed $50.00.", [2900]) is False


def test_submission_must_be_in_progress():
    assert submission_matches("submitting", "HCO-1", 2900, {"order_number": "HCO-1", "refund_cents": 2900})
    assert not submission_matches("awaiting_approval", "HCO-1", 2900, {"order_number": "HCO-1", "refund_cents": 2900})


def test_market_price_ignores_the_receipt_record():
    points = [
        {"time": NOW, "source": "purchase_record", "price_cents": 100},
        {"time": NOW - timedelta(days=1), "source": "demo_catalog", "price_cents": 80},
    ]
    assert latest_market_point(points)["price_cents"] == 80
    assert latest_market_point([points[0]]) is None


def test_parser_reads_demo_email_and_drops_invented_fields():
    email = demo_emails("usr_abcd1234", NOW)[0]["body"]
    parsed = parse_labeled_email(email)
    item = parsed.items[0]
    assert item.retailer == "Harbor & Co"
    assert item.price_paid_cents == 12800
    assert item.missing_fields == []
    invented = ExtractedItem(retailer="Best Buy", product_name="Headphones", price_paid_cents=39999)
    scrubbed = scrub_item(invented, email)
    assert scrubbed.retailer is None
    assert scrubbed.product_name is None
    assert scrubbed.price_paid_cents is None


def test_only_demo_retailer_can_be_automated():
    assert automation_permitted("Harbor & Co") is True
    assert automation_permitted("Best Buy") is False
