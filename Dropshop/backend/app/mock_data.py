"""Canned data served while MOCK_MODE=true so the frontend can build against real shapes immediately."""

from datetime import datetime, timedelta, timezone

from app.models import AgentEvent, Claim, PricePoint, Purchase, SavingsSummary

NOW = datetime.now(timezone.utc)
USER = "demo-user"

PURCHASES = [
    Purchase(
        id="p1", user_id=USER, retailer="Best Buy", product_id="bestbuy:6505727",
        product_name="Sony WH-1000XM6 Headphones", price_paid_cents=39999,
        purchased_at=NOW - timedelta(days=6), order_number="BBY01-80612",
        source="sentient", adjustment_window_ends=NOW + timedelta(days=9),
        current_price_cents=34999, status="claim_pending",
    ),
    Purchase(
        id="p2", user_id=USER, retailer="Target", product_id="target:89012345",
        product_name="Ninja Air Fryer 6qt", price_paid_cents=12999,
        purchased_at=NOW - timedelta(days=3), source="email",
        adjustment_window_ends=NOW + timedelta(days=11),
        current_price_cents=12999, status="monitoring",
    ),
    Purchase(
        id="p3", user_id=USER, retailer="Amazon", product_id="amazon:B0CHX1W1XY",
        product_name="Anker 737 Power Bank", price_paid_cents=8999,
        purchased_at=NOW - timedelta(days=20), source="nessie",
        adjustment_window_ends=NOW - timedelta(days=5), status="expired",
    ),
]


def price_history(product_id: str, days: int = 30) -> list[PricePoint]:
    base = next((p.price_paid_cents for p in PURCHASES if p.product_id == product_id), 10000)
    pts = []
    for d in range(days, -1, -1):
        price = base if d > 2 else int(base * 0.875)  # drop in the last 2 days
        pts.append(PricePoint(time=NOW - timedelta(days=d), retailer="mock", price_cents=price))
    return pts


CLAIMS = [
    Claim(
        id="c1", user_id=USER, purchase_id="p1", retailer="Best Buy", refund_cents=5000,
        status="awaiting_approval", created_at=NOW - timedelta(hours=2),
        explanation="Best Buy matches its own lower price within 15 days of purchase. "
        "You bought 6 days ago at $399.99; it's now $349.99, so you're owed $50.00.",
    )
]

ACTIVITY = [
    AgentEvent(id="e3", user_id=USER, time=NOW - timedelta(hours=2), kind="claim_drafted",
               message="Drafted a $50.00 price-adjustment claim for Sony WH-1000XM6. Waiting for your approval.",
               purchase_id="p1", claim_id="c1"),
    AgentEvent(id="e2", user_id=USER, time=NOW - timedelta(hours=2, minutes=1), kind="price_drop",
               message="Price drop: Sony WH-1000XM6 fell from $399.99 to $349.99 at Best Buy.",
               purchase_id="p1"),
    AgentEvent(id="e1", user_id=USER, time=NOW - timedelta(days=3), kind="purchase_found",
               message="Found a new purchase in your email: Ninja Air Fryer 6qt ($129.99, Target).",
               purchase_id="p2"),
]

SAVINGS = SavingsSummary(
    total_recovered_cents=8250, pending_cents=5000, claims_submitted=4, claims_won=3,
    vault_address="DemoVau1t1111111111111111111111111111111111", vault_balance_cents=8250,
)
