"""Tiger Data / TimescaleDB repository: price observations + history queries.
Schema: data/migrations/001_timescale_init.sql
"""

from datetime import datetime

from app.config import get_settings
from app.models import PricePoint

settings = get_settings()

# TODO(L4): psycopg AsyncConnectionPool(settings.timescale_url)


async def insert_price(product_id: str, retailer: str, price_cents: int, *, time: datetime | None = None,
                       in_stock: bool | None = None, source: str = "poller") -> None:
    raise NotImplementedError


async def latest_price(product_id: str) -> PricePoint | None:
    raise NotImplementedError


async def price_history(product_id: str, days: int = 30) -> list[PricePoint]:
    """Read from the price_daily continuous aggregate (fall back to raw rows for the last bucket)."""
    raise NotImplementedError
