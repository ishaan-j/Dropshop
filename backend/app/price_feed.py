"""Where `poll_prices` gets a product's current price.

Two sources, tried in order:

  live      The purchase has a `product_url` and MOCK_MODE is off: `agents.price_reader` reads the
            price the retailer publishes on that page. Retailers that block automated requests
            just yield nothing.
  held      Otherwise, and whenever the live read fails: the product's last recorded observation.
            This is the simulated feed, and it's deterministic: a price only moves when something
            writes a new observation, which is what `demo_price_drop` does to make the hero
            product drop on cue. The poller then detects that drop through the normal pipeline.

The demo purchases have no `product_url`, so the demo always runs on the held feed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from agents import price_reader
from app.config import get_settings
from app.models import Purchase
from app.store import Store

logger = logging.getLogger(__name__)

# A live price this far from what was paid is almost certainly a different product or variant.
MIN_PLAUSIBLE, MAX_PLAUSIBLE = 0.2, 3.0


async def held_price_cents(purchase: Purchase, store: Store) -> int:
    """The last price we recorded for the product."""
    latest = await store.latest_price(purchase.product_id)
    if latest is not None:
        return latest.price_cents
    if purchase.current_price_cents is not None:
        return purchase.current_price_cents
    return purchase.price_paid_cents


async def live_price_cents(purchase: Purchase) -> int | None:
    """The price on the retailer's product page, if we can read a believable one."""
    if get_settings().mock_mode or not purchase.product_url:
        return None
    try:
        price = await price_reader.fetch_price_cents(purchase.product_url)
    except Exception:
        logger.exception("Price read failed for %s", purchase.product_id)
        return None
    if price is None:
        return None
    paid = purchase.price_paid_cents
    if not MIN_PLAUSIBLE * paid <= price <= MAX_PLAUSIBLE * paid:
        logger.warning("Ignoring implausible live price %d for %s (paid %d)", price, purchase.product_id, paid)
        return None
    return price


async def current_price_cents(purchase: Purchase, store: Store) -> int:
    live = await live_price_cents(purchase)
    return live if live is not None else await held_price_cents(purchase, store)


async def demo_price_drop(
    purchase: Purchase, store: Store, *, percent: float = 15.0, new_price_cents: int | None = None
) -> int:
    """Script a drop: record a lower price for the product. Returns the new price in cents."""
    base = await held_price_cents(purchase, store)
    target = new_price_cents if new_price_cents is not None else round(base * (100 - percent) / 100)
    if target <= 0 or target >= base:
        raise ValueError(f"New price must be between 1 and {base - 1} cents")
    await store.insert_price(
        purchase.product_id, purchase.retailer, target, time=datetime.now(timezone.utc), source="demo"
    )
    return target
