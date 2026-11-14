"""Where Layer 2 keeps application state. Routers and jobs only talk to a `Store`.

Two backends behind one interface:
  MemoryStore  demo data held in this process (MOCK_MODE, or while Layer 4 isn't implemented).
  DbStore      Mongo + Tiger Data through `backend/data` (Layer 4's repositories).

`init_store()` picks one at startup (see `Settings.data_backend`); `get_store()` returns it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Protocol

from app import mock_data
from app.config import get_settings
from app.models import AgentEvent, Claim, PricePoint, Purchase, RetailerPolicy

logger = logging.getLogger(__name__)


class Store(Protocol):
    name: str  # "memory" | "db"
    prices: str  # where price history lives: "memory" | "tiger" ("unchecked" until a db store has looked)

    async def list_purchases(self, user_id: str) -> list[Purchase]: ...  # newest first
    async def get_purchase(self, purchase_id: str) -> Purchase | None: ...
    async def save_purchase(self, purchase: Purchase) -> Purchase: ...
    async def list_claims(self, user_id: str) -> list[Claim]: ...  # newest first
    async def get_claim(self, claim_id: str) -> Claim | None: ...
    async def save_claim(self, claim: Claim) -> Claim: ...
    async def log_event(self, event: AgentEvent) -> None: ...
    async def list_events(self, user_id: str, limit: int = 50) -> list[AgentEvent]: ...  # newest first
    async def insert_price(
        self, product_id: str, retailer: str, price_cents: int, *, time: datetime | None = None, source: str = "poller"
    ) -> None: ...
    async def latest_price(self, product_id: str) -> PricePoint | None: ...
    async def price_history(self, product_id: str, days: int = 30) -> list[PricePoint]: ...  # oldest first
    async def get_policy(self, retailer: str) -> RetailerPolicy | None: ...
    async def save_policy(self, policy: RetailerPolicy) -> None: ...
    async def reset(self) -> None: ...  # reseed the demo state


def _key(retailer: str) -> str:
    return retailer.strip().lower()


class MemoryStore:
    """Demo state in process memory. Lost on restart; reseeded by `reset()`."""

    name = "memory"
    prices = "memory"

    def __init__(self) -> None:
        self._load(mock_data.build_seed(get_settings().demo_user_id))

    def _load(self, seed: mock_data.Seed) -> None:
        self.seed = seed
        self._purchases = {p.id: p for p in seed.purchases}
        self._claims = {c.id: c for c in seed.claims}
        self._events = sorted(seed.activity, key=lambda e: e.time)  # oldest first; appended in order
        self._prices = {pid: list(points) for pid, points in seed.prices.items()}
        self._policies: dict[str, RetailerPolicy] = {}

    async def list_purchases(self, user_id: str) -> list[Purchase]:
        mine = [p.model_copy() for p in self._purchases.values() if p.user_id == user_id]
        return sorted(mine, key=lambda p: p.purchased_at, reverse=True)

    async def get_purchase(self, purchase_id: str) -> Purchase | None:
        found = self._purchases.get(purchase_id)
        return found.model_copy() if found else None

    async def save_purchase(self, purchase: Purchase) -> Purchase:
        self._purchases[purchase.id] = purchase.model_copy()
        return purchase

    async def list_claims(self, user_id: str) -> list[Claim]:
        mine = [c.model_copy() for c in self._claims.values() if c.user_id == user_id]
        return sorted(mine, key=lambda c: c.created_at, reverse=True)

    async def get_claim(self, claim_id: str) -> Claim | None:
        found = self._claims.get(claim_id)
        return found.model_copy() if found else None

    async def save_claim(self, claim: Claim) -> Claim:
        self._claims[claim.id] = claim.model_copy()
        return claim

    async def log_event(self, event: AgentEvent) -> None:
        self._events.append(event.model_copy())

    async def list_events(self, user_id: str, limit: int = 50) -> list[AgentEvent]:
        mine = [e for e in self._events if e.user_id == user_id]
        # Stable sort on the reversed list keeps "logged later" first when timestamps tie.
        newest_first = sorted(reversed(mine), key=lambda e: e.time, reverse=True)
        return [e.model_copy() for e in newest_first[:limit]]

    async def insert_price(
        self, product_id: str, retailer: str, price_cents: int, *, time: datetime | None = None, source: str = "poller"
    ) -> None:
        point = PricePoint(time=time or datetime.now(timezone.utc), retailer=retailer, price_cents=price_cents)
        series = self._prices.setdefault(product_id, [])
        series.append(point)
        if len(series) > 1 and series[-2].time > point.time:
            series.sort(key=lambda p: p.time)

    async def latest_price(self, product_id: str) -> PricePoint | None:
        series = self._prices.get(product_id)
        return series[-1].model_copy() if series else None

    async def price_history(self, product_id: str, days: int = 30) -> list[PricePoint]:
        """One point per day (the day's last price), like Tiger Data's `price_daily` rollup."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        by_day: dict = {}
        for point in self._prices.get(product_id, []):
            if point.time >= cutoff:
                by_day[point.time.date()] = point  # series is oldest first, so the last one wins
        return [by_day[day].model_copy() for day in sorted(by_day)]

    async def get_policy(self, retailer: str) -> RetailerPolicy | None:
        found = self._policies.get(_key(retailer))
        return found.model_copy(deep=True) if found else None

    async def save_policy(self, policy: RetailerPolicy) -> None:
        self._policies[_key(policy.retailer)] = policy.model_copy(deep=True)

    async def reset(self) -> None:
        self._load(mock_data.build_seed(get_settings().demo_user_id))


class DbStore:
    """Mongo + Tiger Data through Layer 4's repositories (`data.mongo`, `data.timescale`).

    App state is in MongoDB. Prices are in Tiger Data when it answers the first time prices are
    needed (at startup, when started through `init_store`). If it doesn't (not configured, not
    reachable, not migrated), price history is held in this process instead, seeded like the
    demo, until the process restarts. `prices` and GET /health say which one is in use.

    `mongo.get_claim` and `mongo.get_policy / save_policy` are used when they exist. Without them
    claims are found by listing, and retailer policies are cached in this process only.
    """

    name = "db"

    def __init__(self) -> None:
        from data import mongo, timescale  # imported here so the API starts without DB drivers

        self._mongo, self._timescale = mongo, timescale
        self._policies: dict[str, RetailerPolicy] = {}
        self._price_source = None  # data.timescale, or a MemoryStore when Tiger Data isn't available

    @property
    def prices(self) -> str:
        if self._price_source is None:
            return "unchecked"  # only before the first price call of a process not started by init_store
        return "memory" if isinstance(self._price_source, MemoryStore) else "tiger"

    async def choose_price_source(self):
        """Decide once where prices live, so one run never splits its history across two places."""
        if self._price_source is None:
            try:
                await self._timescale.ping()
                self._price_source = self._timescale
                logger.info("Prices: Tiger Data")
            except Exception as exc:
                logger.warning(
                    "Tiger Data isn't available (%s: %s). Holding price history in this process until restart.",
                    type(exc).__name__, str(exc)[:200],
                )
                self._price_source = MemoryStore()
        return self._price_source

    async def _prices(self, call: str, *args, **kwargs):
        return await getattr(await self.choose_price_source(), call)(*args, **kwargs)

    async def close(self) -> None:
        await self._mongo.close()
        await self._timescale.close()

    async def list_purchases(self, user_id: str) -> list[Purchase]:
        return await self._mongo.list_purchases(user_id)

    async def get_purchase(self, purchase_id: str) -> Purchase | None:
        return await self._mongo.get_purchase(purchase_id)

    async def save_purchase(self, purchase: Purchase) -> Purchase:
        return await self._mongo.upsert_purchase(purchase)

    async def list_claims(self, user_id: str) -> list[Claim]:
        return await self._mongo.list_claims(user_id)

    async def get_claim(self, claim_id: str) -> Claim | None:
        if hasattr(self._mongo, "get_claim"):
            return await self._mongo.get_claim(claim_id)
        claims = await self._mongo.list_claims(get_settings().demo_user_id)  # single demo user
        return next((c for c in claims if c.id == claim_id), None)

    async def save_claim(self, claim: Claim) -> Claim:
        return await self._mongo.save_claim(claim)

    async def log_event(self, event: AgentEvent) -> None:
        await self._mongo.log_event(event)

    async def list_events(self, user_id: str, limit: int = 50) -> list[AgentEvent]:
        return await self._mongo.list_events(user_id, limit)

    async def insert_price(
        self, product_id: str, retailer: str, price_cents: int, *, time: datetime | None = None, source: str = "poller"
    ) -> None:
        await self._prices("insert_price", product_id, retailer, price_cents, time=time, source=source)

    async def latest_price(self, product_id: str) -> PricePoint | None:
        return await self._prices("latest_price", product_id)

    async def price_history(self, product_id: str, days: int = 30) -> list[PricePoint]:
        return await self._prices("price_history", product_id, days)

    async def get_policy(self, retailer: str) -> RetailerPolicy | None:
        if hasattr(self._mongo, "get_policy"):
            return await self._mongo.get_policy(retailer)
        return self._policies.get(_key(retailer))

    async def save_policy(self, policy: RetailerPolicy) -> None:
        if hasattr(self._mongo, "save_policy"):
            await self._mongo.save_policy(policy)
        else:
            self._policies[_key(policy.retailer)] = policy

    async def reset(self) -> None:
        raise NotImplementedError(
            "Demo reset only works with the in-memory store. Reseed the database with `python -m data.seed`."
        )


_store: Store | None = None


async def init_store() -> Store:
    """Choose the backend for this process. Called once at API / worker startup."""
    store = await _choose_store()
    if isinstance(store, DbStore):
        await store.choose_price_source()
    return store


async def _choose_store() -> Store:
    global _store
    settings = get_settings()
    choice = settings.data_backend
    if choice == "auto":
        choice = "memory" if settings.mock_mode else "db"
        if choice == "db":
            # Layer 4 may not have landed: fall back to demo data instead of answering 501 everywhere.
            try:
                candidate = DbStore()
                await candidate.list_purchases(settings.demo_user_id)
                _store = candidate
                logger.info("Store: database (Mongo + Tiger Data)")
                return _store
            except (NotImplementedError, ImportError) as exc:
                logger.warning(
                    "Layer 4 (backend/data) isn't available yet (%s). Using the in-memory demo store; "
                    "set DATA_BACKEND=db to force the database.", type(exc).__name__,
                )
                choice = "memory"
            except Exception:
                # Implemented but unreachable right now: keep the database so nothing silently
                # switches to demo data. Requests will report the error until it's back.
                logger.exception("Database check failed at startup; keeping the database store")
                _store = DbStore()
                return _store
    _store = MemoryStore() if choice == "memory" else DbStore()
    logger.info("Store: %s", _store.name)
    return _store


def get_store() -> Store:
    global _store
    if _store is None:  # not started through the app lifespan (scripts, some tests)
        settings = get_settings()
        use_db = settings.data_backend == "db" or (settings.data_backend == "auto" and not settings.mock_mode)
        _store = DbStore() if use_db else MemoryStore()
    return _store


def set_store(store: Store | None) -> None:
    """Swap the store (tests)."""
    global _store
    _store = store
