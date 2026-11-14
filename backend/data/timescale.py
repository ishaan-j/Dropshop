"""Tiger Data / TimescaleDB repository: price observations + history queries.
Schema: data/migrations/001_timescale_init.sql

Every price check writes one row to the `price_observations` hypertable. The chart's daily
history comes from the `price_daily` continuous aggregate for completed days, plus today's raw
rows (which also gives today's point its real time instead of midnight). The aggregate is a
real-time one, so a completed day its refresh policy hasn't stored yet is still in the result.

Apply the schema with `python -m data.timescale` (or `python -m data.seed`, which does it too).

This uses psycopg's blocking API on worker threads. Its async API refuses to run on the Proactor
event loop, which is the loop uvicorn uses on Windows.
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg_pool import ConnectionPool, PoolTimeout

from app.config import get_settings
from app.models import PricePoint

logger = logging.getLogger(__name__)

MIGRATIONS = Path(__file__).parent / "migrations"
CONNECT_TIMEOUT_SECONDS = 5  # report an unreachable service quickly instead of hanging a request

_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


class TigerUnavailable(RuntimeError):
    """Tiger Data can't be used right now: unreachable, wrong credentials, or not migrated."""


def _check_reachable(url: str) -> None:
    """Open one direct connection, with a deadline on the whole attempt.

    The pool would keep retrying in the background, and libpq applies `connect_timeout` to each of
    the host's addresses in turn (a Tiger Cloud host has six), so neither gives a quick answer.
    """
    outcome: list[Exception | None] = []

    def attempt() -> None:
        try:
            psycopg.connect(url, connect_timeout=CONNECT_TIMEOUT_SECONDS).close()
            outcome.append(None)
        except psycopg.Error as exc:
            outcome.append(exc)

    thread = threading.Thread(target=attempt, name="tiger-probe", daemon=True)
    thread.start()
    thread.join(CONNECT_TIMEOUT_SECONDS + 1)
    if not outcome:
        raise TigerUnavailable(f"can't connect to TIMESCALE_URL (no answer in {CONNECT_TIMEOUT_SECONDS + 1} s)")
    if outcome[0] is not None:
        raise TigerUnavailable(f"can't connect to TIMESCALE_URL ({str(outcome[0]).strip()[:160]})") from outcome[0]


def _get_pool() -> ConnectionPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            url = get_settings().timescale_url
            _check_reachable(url)
            pool = ConnectionPool(
                url, min_size=1, max_size=4, open=False, timeout=CONNECT_TIMEOUT_SECONDS,
                # autocommit: each statement stands alone, and refreshing a continuous aggregate
                # isn't allowed inside a transaction.
                kwargs={"autocommit": True, "connect_timeout": CONNECT_TIMEOUT_SECONDS},
            )
            pool.open()
            _pool = pool
    return _pool


async def _run(work):
    """Run `work(connection)` on a worker thread with a pooled connection."""

    def call():
        try:
            with _get_pool().connection() as conn:
                return work(conn)
        except PoolTimeout as exc:
            raise TigerUnavailable("no connection to Tiger Data became available") from exc

    return await asyncio.to_thread(call)


async def close() -> None:
    global _pool
    with _pool_lock:
        pool, _pool = _pool, None
    if pool is not None:
        await asyncio.to_thread(pool.close)


def _today() -> datetime:
    """Start of the current UTC day, which is where the daily buckets start."""
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


# --- Schema -------------------------------------------------------------------------------------


def _statements(sql: str) -> list[str]:
    """Split a migration file into statements. Keep migrations to plain statements: no `;` or
    `--` inside string literals, no functions with bodies."""
    without_comments = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in without_comments.split(";") if s.strip()]


async def migrate() -> int:
    """Apply every file in data/migrations. Safe to run again. Returns the number of statements run."""
    statements = [s for path in sorted(MIGRATIONS.glob("*.sql")) for s in _statements(path.read_text(encoding="utf-8"))]

    def work(conn):
        for statement in statements:  # one at a time: a continuous aggregate can't be created in a transaction
            conn.execute(statement)
        return len(statements)

    return await _run(work)


async def ping() -> None:
    """Raise `TigerUnavailable` unless the service is reachable and the schema is there."""

    def work(conn):
        return conn.execute("SELECT to_regclass('price_observations'), to_regclass('price_daily')").fetchone()

    if None in await _run(work):
        raise TigerUnavailable("the schema is missing; run `python -m data.seed` or `python -m data.timescale`")


def _refresh_daily(conn, start: datetime | None, end: datetime) -> None:
    """Bring `price_daily` up to date for the days in [start, end). `start=None` means from the beginning."""
    conn.execute("CALL refresh_continuous_aggregate('price_daily', %s::timestamptz, %s::timestamptz)", (start, end))


# --- Prices -------------------------------------------------------------------------------------

_INSERT = (
    "INSERT INTO price_observations (time, product_id, retailer, price_cents, in_stock, source) "
    "VALUES (%s, %s, %s, %s, %s, %s)"
)


async def insert_price(product_id: str, retailer: str, price_cents: int, *, time: datetime | None = None,
                       in_stock: bool | None = None, source: str = "poller") -> None:
    when = _utc(time) if time else datetime.now(timezone.utc)

    def work(conn):
        conn.execute(_INSERT, (when, product_id, retailer, price_cents, in_stock, source))
        today = _today()
        if when < today:
            # A backdated observation (a purchase found after the fact). The aggregate's own
            # policy would pick it up within 15 minutes; refresh that day now so the chart has it.
            day = when.replace(hour=0, minute=0, second=0, microsecond=0)
            try:
                _refresh_daily(conn, day, day + timedelta(days=1))
            except psycopg.Error as exc:
                logger.warning("price_daily wasn't refreshed for %s (%s); its policy will catch up", day.date(), exc)

    await _run(work)


async def replace_history(prices: dict[str, list[PricePoint]], *, source: str = "seed") -> int:
    """Replace everything recorded for these products with the given observations (demo seed)."""
    rows = [
        (_utc(point.time), product_id, point.retailer, point.price_cents, None, source)
        for product_id, points in prices.items() for point in points
    ]

    def work(conn):
        with conn.transaction():
            conn.execute("DELETE FROM price_observations WHERE product_id = ANY(%s)", (list(prices),))
            with conn.cursor() as cursor:
                cursor.executemany(_INSERT, rows)
        _refresh_daily(conn, None, _today())
        return len(rows)

    return await _run(work)


async def latest_price(product_id: str) -> PricePoint | None:
    def work(conn):
        return conn.execute(
            "SELECT time, retailer, price_cents FROM price_observations WHERE product_id = %s ORDER BY time DESC LIMIT 1",
            (product_id,),
        ).fetchone()

    row = await _run(work)
    return PricePoint(time=_utc(row[0]), retailer=row[1], price_cents=row[2]) if row else None


_HISTORY = """
SELECT day AS time, retailer, close_price_cents AS price_cents
  FROM price_daily
 WHERE product_id = %(product)s AND day > %(cutoff)s AND day < %(today)s
UNION ALL
SELECT max(time), last(retailer, time), last(price_cents, time)
  FROM price_observations
 WHERE product_id = %(product)s AND time >= %(today)s AND time >= %(cutoff)s
HAVING count(*) > 0
ORDER BY time
"""


async def price_history(product_id: str, days: int = 30) -> list[PricePoint]:
    """One point per day (the day's last price), oldest first.

    Completed days come from the `price_daily` continuous aggregate; today comes from the raw
    rows, so a price recorded a moment ago is already in the result.
    """
    params = {"product": product_id, "today": _today(), "cutoff": datetime.now(timezone.utc) - timedelta(days=days)}

    def work(conn):
        return conn.execute(_HISTORY, params).fetchall()

    return [PricePoint(time=_utc(time), retailer=retailer, price_cents=cents) for time, retailer, cents in await _run(work)]


async def _main() -> None:
    try:
        print(f"Applied {await migrate()} migration statements.")
        await ping()
        print("Tiger Data is reachable and the schema is in place.")
    finally:
        await close()


if __name__ == "__main__":
    asyncio.run(_main())
