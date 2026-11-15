"""Demo seed data for the in-memory store (MOCK_MODE, or any time Layer 4 isn't available).

`build_seed()` returns a fresh, self-consistent demo state relative to "now": purchases, claims,
activity, price history, and the simulated bank's card charges and refund deposits. Everything the
API reports (savings totals, vault balance) is computed from this state, so the numbers always agree.

Layer 4's `data/seed.py` should load the same shapes into Mongo / Tiger Data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.models import AgentEvent, Claim, PricePoint, Purchase

USER = "demo-user"
VAULT_ADDRESS = "DemoVau1t1111111111111111111111111111111111"
HISTORY_DAYS = 30


@dataclass
class Seed:
    purchases: list[Purchase]
    claims: list[Claim]
    activity: list[AgentEvent]
    prices: dict[str, list[PricePoint]]  # product_id -> observations, oldest first
    # Ledger of the simulated bank in app/finance_gateway.py.
    card_purchases: list[dict] = field(default_factory=list)  # {id, amount_cents, description, date}
    deposits: list[dict] = field(default_factory=list)


def _history(retailer: str, paid: int, current: int | None, drop_days_ago: int | None, now: datetime) -> list[PricePoint]:
    """Daily prices for the last 30 days: flat at `paid`, stepping to `current` at the drop."""
    points = []
    for d in range(HISTORY_DAYS, -1, -1):
        dropped = current is not None and drop_days_ago is not None and d <= drop_days_ago
        points.append(
            PricePoint(time=now - timedelta(days=d), retailer=retailer, price_cents=current if dropped else paid)
        )
    return points


def build_seed(user_id: str = USER, now: datetime | None = None) -> Seed:
    now = now or datetime.now(timezone.utc)
    days = lambda n: timedelta(days=n)  # noqa: E731

    # (id, retailer, product_id, name, paid, current, bought days ago, window days, order, source, status, drop days ago)
    rows = [
        ("p1", "Best Buy", "bestbuy:6505727", "Sony WH-1000XM6 Headphones", 39999, 34999, 6, 15, "BBY01-80612", "sentient", "claim_pending", 2),
        ("p2", "Target", "target:89012345", "Ninja Air Fryer 6qt", 12999, 12999, 3, 14, "912-0045-7731", "email", "monitoring", None),
        ("p3", "Amazon", "amazon:B0CHX1W1XY", "Anker 737 Power Bank", 8999, None, 20, 15, "112-7348291-5502611", "nessie", "expired", None),
        # Past wins. Their refunds are what "savings so far" shows at the start of the demo.
        ("p4", "Best Buy", "bestbuy:6418599", "Breville Bambino Espresso Machine", 29999, 26749, 25, 15, "BBY01-79204", "sentient", "claimed", 18),
        ("p5", "Amazon", "amazon:B0CFPJYX7P", "Kindle Paperwhite", 15999, 13999, 38, 15, "112-9020117-4455620", "email", "claimed", 30),
        ("p6", "Target", "target:87654321", "Patagonia Nano Puff Jacket", 22900, 19900, 52, 14, "912-0038-1160", "email", "claimed", 30),
    ]
    purchases, prices, card = [], {}, []
    for pid, retailer, product_id, name, paid, current, bought, window, order, source, status, drop in rows:
        purchases.append(
            Purchase(
                id=pid, user_id=user_id, retailer=retailer, product_id=product_id, product_name=name,
                price_paid_cents=paid, purchased_at=now - days(bought), order_number=order, source=source,
                nessie_purchase_id=f"sim-card-{pid}", adjustment_window_ends=now - days(bought) + days(window),
                current_price_cents=current, status=status,
            )
        )
        prices[product_id] = _history(retailer, paid, current, drop, now)
        card.append(
            {"id": f"sim-card-{pid}", "amount_cents": paid, "description": f"{retailer} {name}", "date": (now - days(bought)).date()}
        )
    # Card charges for the fixture receipts a scan discovers, so "confirmed against your card" works.
    card += [
        {"id": "sim-card-airpods", "amount_cents": 24999, "description": "Best Buy AirPods Pro 3", "date": (now - days(2)).date()},
        {"id": "sim-card-hefty", "amount_cents": 949, "description": "Target Hefty Trash Bags", "date": (now - days(3)).date()},
    ]

    claims = [
        Claim(
            id="c1", user_id=user_id, purchase_id="p1", retailer="Best Buy", refund_cents=5000,
            status="awaiting_approval", created_at=now - timedelta(hours=2),
            explanation="Best Buy matches its own lower price within 15 days of purchase. "
            "You bought 6 days ago at $399.99; it's now $349.99, so you're owed $50.00.",
        )
    ]
    activity = [
        AgentEvent(id="e3", user_id=user_id, time=now - timedelta(hours=2), kind="claim_drafted",
                   message="Drafted a $50.00 price-adjustment claim for Sony WH-1000XM6 Headphones. Waiting for your approval.",
                   purchase_id="p1", claim_id="c1"),
        AgentEvent(id="e2", user_id=user_id, time=now - timedelta(hours=2, minutes=1), kind="price_drop",
                   message="Price drop: Sony WH-1000XM6 Headphones fell from $399.99 to $349.99 at Best Buy.",
                   purchase_id="p1"),
        AgentEvent(id="e1", user_id=user_id, time=now - days(3), kind="purchase_found",
                   message="Found a new purchase in your email: Ninja Air Fryer 6qt ($129.99, Target).",
                   purchase_id="p2"),
    ]
    deposits = []
    # (claim id, purchase id, retailer, name, refund, refunded days ago)
    for cid, pid, retailer, name, refund, ago in [
        ("c2", "p4", "Best Buy", "Breville Bambino Espresso Machine", 3250, 16),
        ("c3", "p5", "Amazon", "Kindle Paperwhite", 2000, 28),
        ("c4", "p6", "Target", "Patagonia Nano Puff Jacket", 3000, 27),
    ]:
        refunded = now - days(ago)
        claims.append(
            Claim(
                id=cid, user_id=user_id, purchase_id=pid, retailer=retailer, refund_cents=refund,
                status="refund_received", created_at=refunded - days(2), submitted_at=refunded - days(1),
                refund_received_at=refunded, nessie_deposit_id=f"sim-dep-{cid}",
                solana_tx_signature=f"sim-seed-{cid}",
                explanation=f"{retailer} lowered the price of {name} inside its price-adjustment window, "
                f"so you were owed ${refund / 100:,.2f}.",
            )
        )
        deposits.append(
            {"id": f"sim-dep-{cid}", "amount_cents": refund, "description": f"PRICE ADJUSTMENT {retailer}", "date": refunded.date()}
        )
        activity += [
            AgentEvent(id=f"e-{cid}-vault", user_id=user_id, time=refunded + timedelta(minutes=1), kind="vault_recorded",
                       message=f"Recorded ${refund / 100:,.2f} from the {name} refund in your Solana savings vault.",
                       purchase_id=pid, claim_id=cid),
            AgentEvent(id=f"e-{cid}-refund", user_id=user_id, time=refunded, kind="refund_received",
                       message=f"Refund received: ${refund / 100:,.2f} from {retailer} for {name}.",
                       purchase_id=pid, claim_id=cid),
        ]
    return Seed(purchases=purchases, claims=claims, activity=activity, prices=prices, card_purchases=card, deposits=deposits)
