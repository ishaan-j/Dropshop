"""Run: cd backend && python -m pytest data  (offline).

These check what `data/timescale.py` sends and how it reads results, against a recording stand-in
for the connection. They don't run the SQL: that needs a real TimescaleDB (`python -m data.seed`
against Tiger Cloud is the real check).
"""

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from app.config import get_settings
from app.models import PricePoint
from data import timescale

REAL_GET_POOL = timescale._get_pool  # captured before conftest's guard replaces it
NOW = datetime.now(timezone.utc)
TODAY = NOW.replace(hour=0, minute=0, second=0, microsecond=0)


class FakeConnection:
    def __init__(self):
        self.executed: list[tuple[str, object]] = []  # (sql with whitespace collapsed, params)
        self.rows: list[tuple] = []
        self.fail_on: str | None = None

    def execute(self, sql, params=None):
        if self.fail_on and self.fail_on in sql:
            raise psycopg.OperationalError("refresh failed")
        self.executed.append((" ".join(sql.split()), params))
        return self

    def executemany(self, sql, rows):
        self.executed.append((" ".join(sql.split()), list(rows)))

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)

    @contextmanager
    def transaction(self):
        yield

    @contextmanager
    def cursor(self):
        yield self

    @contextmanager
    def connection(self):  # the pool hands out this same connection
        yield self


@pytest.fixture
def tiger(monkeypatch) -> FakeConnection:
    conn = FakeConnection()
    monkeypatch.setattr(timescale, "_get_pool", lambda: conn)
    return conn


def test_migration_is_split_into_statements_and_run_one_by_one(tiger):
    assert asyncio.run(timescale.migrate()) == 7
    statements = [sql for sql, _ in tiger.executed]
    assert statements[0] == "CREATE EXTENSION IF NOT EXISTS timescaledb"
    assert [s.split("(")[0].strip() for s in statements[2:]] == [
        "SELECT create_hypertable", "CREATE INDEX IF NOT EXISTS idx_price_obs_product_time ON price_observations",
        "CREATE MATERIALIZED VIEW IF NOT EXISTS price_daily WITH", "ALTER MATERIALIZED VIEW price_daily SET",
        "SELECT add_continuous_aggregate_policy",
    ]
    assert all("--" not in s and ";" not in s for s in statements)  # comments (one holds a `;`) are gone


def test_a_price_recorded_now_is_one_insert(tiger):
    asyncio.run(timescale.insert_price("target:x", "Target", 900, source="demo"))
    (sql, params), = tiger.executed
    assert sql.startswith("INSERT INTO price_observations")
    assert params[1:] == ("target:x", "Target", 900, None, "demo") and abs(params[0] - NOW) < timedelta(minutes=1)


def test_a_backdated_price_also_refreshes_that_day_of_the_aggregate(tiger):
    three_days_ago = NOW - timedelta(days=3)
    asyncio.run(timescale.insert_price("target:x", "Target", 1000, time=three_days_ago, source="seed"))
    (insert, _), (refresh, window) = tiger.executed
    assert insert.startswith("INSERT") and "refresh_continuous_aggregate('price_daily'" in refresh
    assert window == (TODAY - timedelta(days=3), TODAY - timedelta(days=2))

    tiger.fail_on = "refresh_continuous_aggregate"  # the insert still counts if the refresh is refused
    asyncio.run(timescale.insert_price("target:x", "Target", 1000, time=three_days_ago))
    assert len(tiger.executed) == 3


def test_history_reads_the_aggregate_plus_todays_rows_and_returns_utc(tiger):
    plus_two = timezone(timedelta(hours=2))
    tiger.rows = [(TODAY - timedelta(days=1), "Target", 1000), (NOW.astimezone(plus_two), "Target", 900)]
    history = asyncio.run(timescale.price_history("target:x", days=7))
    assert history == [
        PricePoint(time=TODAY - timedelta(days=1), retailer="Target", price_cents=1000),
        PricePoint(time=NOW, retailer="Target", price_cents=900),
    ]
    assert all(p.time.utcoffset() == timedelta(0) for p in history)
    (sql, params), = tiger.executed
    assert "FROM price_daily" in sql and "FROM price_observations" in sql and sql.endswith("ORDER BY time")
    assert params["product"] == "target:x" and params["today"] == TODAY
    assert abs(params["cutoff"] - (NOW - timedelta(days=7))) < timedelta(minutes=1)


def test_latest_price(tiger):
    assert asyncio.run(timescale.latest_price("target:x")) is None
    tiger.rows = [(NOW, "Target", 900)]
    assert asyncio.run(timescale.latest_price("target:x")) == PricePoint(time=NOW, retailer="Target", price_cents=900)
    assert tiger.executed[-1][0].endswith("ORDER BY time DESC LIMIT 1")


def test_replace_history_swaps_the_products_rows_and_refreshes_completed_days(tiger):
    points = [PricePoint(time=NOW - timedelta(days=d), retailer="Target", price_cents=1000) for d in (2, 1, 0)]
    assert asyncio.run(timescale.replace_history({"target:x": points, "target:y": points[:1]})) == 4
    (delete, deleted), (insert, rows), (refresh, window) = tiger.executed
    assert delete.startswith("DELETE FROM price_observations") and deleted == (["target:x", "target:y"],)
    assert insert.startswith("INSERT") and len(rows) == 4 and rows[0][1:] == ("target:x", "Target", 1000, None, "seed")
    assert "refresh_continuous_aggregate" in refresh and window == (None, TODAY)


def test_ping_needs_the_schema(tiger):
    tiger.rows = [("price_observations", "price_daily")]
    asyncio.run(timescale.ping())
    tiger.rows = [("price_observations", None)]
    with pytest.raises(timescale.TigerUnavailable, match="schema is missing"):
        asyncio.run(timescale.ping())


def test_an_unreachable_service_is_reported_quickly(monkeypatch):
    monkeypatch.setattr(timescale, "_get_pool", REAL_GET_POOL)
    monkeypatch.setattr(timescale, "_pool", None)
    monkeypatch.setenv("TIMESCALE_URL", "postgresql://nobody:nothing@127.0.0.1:59999/none")  # nothing listens here
    get_settings.cache_clear()
    try:
        with pytest.raises(timescale.TigerUnavailable, match="can't connect"):
            asyncio.run(timescale.latest_price("target:x"))
    finally:
        get_settings.cache_clear()
