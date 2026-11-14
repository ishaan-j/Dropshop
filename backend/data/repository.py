"""Persistence. MongoDB and Timescale are used when a connection succeeds.

If the default localhost database is down and MOCK_MODE is on, records stay in
memory and are reported as demo persistence. A configured remote database that
fails is an error: this module does not silently switch that failure to memory.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TypeVar

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError

from app.config import get_settings
from app.models import (
    AgentEvent,
    AgentRun,
    Claim,
    Preferences,
    PricePoint,
    Purchase,
    ReceiptRecord,
    Refund,
    RetailerPolicy,
    SavingsAllocation,
    UserApproval,
)
from app.security import safe_detail

log = logging.getLogger("dropshop.repo")
T = TypeVar("T")

_OBS_ALTERS = [
    "ALTER TABLE price_observations ADD COLUMN IF NOT EXISTS currency TEXT NOT NULL DEFAULT 'USD'",
    "ALTER TABLE price_observations ADD COLUMN IF NOT EXISTS product_url TEXT",
    "ALTER TABLE price_observations ADD COLUMN IF NOT EXISTS availability TEXT",
    "ALTER TABLE price_observations ADD COLUMN IF NOT EXISTS collection_status TEXT NOT NULL DEFAULT 'recorded'",
    "ALTER TABLE price_observations ADD COLUMN IF NOT EXISTS data_origin TEXT NOT NULL DEFAULT 'demo'",
    "ALTER TABLE price_observations ADD COLUMN IF NOT EXISTS user_id TEXT",
    "ALTER TABLE price_observations ADD COLUMN IF NOT EXISTS purchase_id TEXT",
]


class PersistenceError(RuntimeError):
    pass


class Repository:
    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
        self.purchases: dict[str, Purchase] = {}
        self.claims: dict[str, Claim] = {}
        self.events: list[AgentEvent] = []
        self.runs: dict[str, AgentRun] = {}
        self.refunds: dict[str, Refund] = {}
        self.allocations: dict[str, SavingsAllocation] = {}
        self.approvals: dict[str, UserApproval] = {}
        self.receipts: dict[str, ReceiptRecord] = {}
        self.policies: dict[str, RetailerPolicy] = {}
        self.preferences: dict[str, Preferences] = {}
        self.connections: dict[str, dict] = {}
        self.prices: list[dict] = []
        self.price_changes: list[dict] = []
        self.monitoring: list[dict] = []
        self.demo_submissions: dict[str, dict] = {}
        self.mongo = None
        self.pg = None
        self.mongo_mode = "not_connected"
        self.mongo_detail = "MongoDB has not been checked."
        self.pg_mode = "not_connected"
        self.pg_detail = "TimescaleDB has not been checked."
        self.pg_is_timescale = False
        self.block_memory = False
        self.block_price_memory = False
        self._did_connect = False
        self._pg_lock = asyncio.Lock()
        self._subscribers: list[asyncio.Queue] = []

    async def connect(self) -> None:
        if self._did_connect:
            return
        await asyncio.to_thread(self._connect_mongo)
        await asyncio.to_thread(self._connect_pg)
        self._did_connect = True
        log.info("persistence mongo=%s timescale=%s", self.mongo_mode, self.pg_mode)

    async def reconnect(self) -> None:
        self.close()
        self.mongo = None
        self.pg = None
        self._did_connect = False
        await self.connect()

    def _connect_mongo(self) -> None:
        settings = get_settings()
        try:
            client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=800)
            client.admin.command("ping")
            self.mongo = client[settings.mongodb_db]
            self._ensure_indexes()
            remote = "mongodb.net" in settings.mongodb_uri or settings.mongodb_uri.startswith("mongodb+srv://")
            local = "localhost" in settings.mongodb_uri or "127.0.0.1" in settings.mongodb_uri
            if remote:
                self.mongo_mode = "live"
                self.mongo_detail = "MongoDB Atlas is connected. It is the source of truth for application records."
            elif local:
                self.mongo_mode = "sandbox"
                self.mongo_detail = "Local MongoDB is connected. This is not a MongoDB Atlas cluster."
            else:
                self.mongo_mode = "live"
                self.mongo_detail = "MongoDB is connected."
            self.block_memory = False
        except PyMongoError as exc:
            self.mongo = None
            remote = "mongodb.net" in settings.mongodb_uri or settings.mongodb_uri.startswith("mongodb+srv://")
            local = "localhost" in settings.mongodb_uri or "127.0.0.1" in settings.mongodb_uri
            if remote or not local:
                self.block_memory = True
                self.mongo_mode = "error"
                self.mongo_detail = f"Configured MongoDB failed: {safe_detail(exc)}"
            elif settings.mock_mode:
                self.block_memory = False
                self.mongo_mode = "demo"
                self.mongo_detail = "MongoDB is not running. Records stay in memory for this process and are demo data."
            else:
                self.block_memory = True
                self.mongo_mode = "error"
                self.mongo_detail = "MongoDB is not connected and MOCK_MODE is false."

    def _ensure_indexes(self) -> None:
        db = self.mongo
        db.purchases.create_index([("user_id", ASCENDING), ("purchased_at", DESCENDING)])
        db.purchases.create_index([("user_id", ASCENDING), ("order_number", ASCENDING)])
        db.claims.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        db.claims.create_index([("user_id", ASCENDING), ("purchase_id", ASCENDING)])
        db.agent_events.create_index([("user_id", ASCENDING), ("time", DESCENDING)])
        db.agent_runs.create_index([("user_id", ASCENDING), ("started_at", DESCENDING)])
        db.refunds.create_index([("user_id", ASCENDING), ("claim_id", ASCENDING)])
        db.receipts.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        db.retailer_policies.create_index("retailer")
        db.savings_allocations.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])

    def _connect_pg(self) -> None:
        settings = get_settings()
        url = settings.timescale_url
        local = "localhost" in url or "127.0.0.1" in url
        try:
            import psycopg

            conn = psycopg.connect(url, connect_timeout=2, autocommit=True)
            self._ensure_price_schema(conn)
            self.pg = conn
            self.block_price_memory = False
            if self.pg_is_timescale and local:
                self.pg_mode = "sandbox"
                self.pg_detail = "Local TimescaleDB is connected. This is the Tiger Data engine, not a Tiger Cloud service."
            elif self.pg_is_timescale:
                self.pg_mode = "live"
                self.pg_detail = "TimescaleDB is connected on the configured host."
            elif local:
                self.pg_mode = "sandbox"
                self.pg_detail = "PostgreSQL is connected, but the TimescaleDB extension is missing, so this is not Tiger Data."
            else:
                self.pg_mode = "error"
                self.pg_detail = "The configured database answered, but the TimescaleDB extension is not installed."
        except Exception as exc:  # noqa: BLE001 — connection failures must become a status, not a crash
            self.pg = None
            if not local:
                self.block_price_memory = True
                self.pg_mode = "error"
                self.pg_detail = f"Configured Timescale URL failed: {safe_detail(exc)}"
            elif settings.mock_mode:
                self.block_price_memory = False
                self.pg_mode = "demo"
                self.pg_detail = "TimescaleDB is not running. Price points stay in memory and are labeled demo."
            else:
                self.block_price_memory = True
                self.pg_mode = "error"
                self.pg_detail = "TimescaleDB is not connected and MOCK_MODE is false."

    def _ensure_price_schema(self, conn) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS price_observations (
                time TIMESTAMPTZ NOT NULL,
                product_id TEXT NOT NULL,
                retailer TEXT NOT NULL,
                price_cents INTEGER NOT NULL,
                in_stock BOOLEAN,
                source TEXT NOT NULL DEFAULT 'poller',
                currency TEXT NOT NULL DEFAULT 'USD',
                product_url TEXT,
                availability TEXT,
                collection_status TEXT NOT NULL DEFAULT 'recorded',
                data_origin TEXT NOT NULL DEFAULT 'demo',
                user_id TEXT,
                purchase_id TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS price_change_events (
                time TIMESTAMPTZ NOT NULL,
                user_id TEXT,
                product_id TEXT NOT NULL,
                purchase_id TEXT,
                retailer TEXT NOT NULL,
                previous_price_cents INTEGER,
                new_price_cents INTEGER NOT NULL,
                delta_cents INTEGER NOT NULL,
                source TEXT NOT NULL,
                data_origin TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS monitoring_events (
                time TIMESTAMPTZ NOT NULL,
                user_id TEXT,
                product_id TEXT NOT NULL,
                purchase_id TEXT,
                status TEXT NOT NULL,
                detail TEXT,
                data_origin TEXT NOT NULL
            )
            """,
        ]
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
            for alter in _OBS_ALTERS:
                cur.execute(alter)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_price_obs_product_time ON price_observations (product_id, time DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_price_obs_user_product ON price_observations (user_id, product_id, time DESC)")
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
                cur.execute("SELECT create_hypertable('price_observations', by_range('time'), if_not_exists => TRUE)")
                self.pg_is_timescale = True
            except Exception:
                conn.rollback() if not conn.autocommit else None
                cur.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')")
                self.pg_is_timescale = bool(cur.fetchone()[0])

    def close(self) -> None:
        if self.pg is not None:
            self.pg.close()
            self.pg = None
        if self.mongo is not None:
            self.mongo.client.close()
            self.mongo = None

    def reset_memory(self) -> None:
        """Test helper. Does not touch a real database."""
        self.__init__()

    def _guard(self) -> None:
        if self.mongo is not None:
            return
        if self.block_memory or not get_settings().mock_mode:
            raise PersistenceError(self.mongo_detail)

    def _guard_prices(self) -> None:
        if self.pg is not None:
            return
        if self.block_price_memory or not get_settings().mock_mode:
            raise PersistenceError(self.pg_detail)

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def _publish(self, event: AgentEvent) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue

    async def save_user(self, user_id: str, display_name: str) -> dict:
        self._guard()
        doc = {
            "id": user_id,
            "display_name": display_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.mongo is not None:
            await asyncio.to_thread(
                lambda: self.mongo.users.replace_one({"_id": user_id}, {**doc, "_id": user_id}, upsert=True)
            )
        else:
            self.users[user_id] = doc
        return doc

    async def get_user(self, user_id: str) -> dict | None:
        self._guard()
        if self.mongo is not None:
            doc = await asyncio.to_thread(lambda: self.mongo.users.find_one({"_id": user_id}))
            return doc
        return self.users.get(user_id)

    async def list_user_ids(self) -> list[str]:
        self._guard()
        if self.mongo is not None:
            docs = await asyncio.to_thread(lambda: list(self.mongo.users.find({}, {"_id": 1})))
            return [doc["_id"] for doc in docs]
        return list(self.users)

    async def save_purchase(self, purchase: Purchase) -> Purchase:
        self._guard()
        if self.mongo is not None:
            await asyncio.to_thread(lambda: self._upsert(self.mongo.purchases, purchase))
        else:
            self.purchases[purchase.id] = purchase
        return purchase

    async def list_purchases(self, user_id: str) -> list[Purchase]:
        self._guard()
        if self.mongo is not None:
            docs = await asyncio.to_thread(
                lambda: list(self.mongo.purchases.find({"user_id": user_id}).sort("purchased_at", DESCENDING))
            )
            return [self._load(Purchase, doc) for doc in docs]
        rows = [row for row in self.purchases.values() if row.user_id == user_id]
        return sorted(rows, key=lambda row: row.purchased_at, reverse=True)

    async def get_purchase(self, user_id: str, purchase_id: str) -> Purchase | None:
        self._guard()
        if self.mongo is not None:
            doc = await asyncio.to_thread(
                lambda: self.mongo.purchases.find_one({"_id": purchase_id, "user_id": user_id})
            )
            return self._load(Purchase, doc) if doc else None
        row = self.purchases.get(purchase_id)
        if row and row.user_id == user_id:
            return row
        return None

    async def save_claim(self, claim: Claim) -> Claim:
        self._guard()
        if self.mongo is not None:
            await asyncio.to_thread(lambda: self._upsert(self.mongo.claims, claim))
        else:
            self.claims[claim.id] = claim
        return claim

    async def list_claims(self, user_id: str) -> list[Claim]:
        self._guard()
        if self.mongo is not None:
            docs = await asyncio.to_thread(
                lambda: list(self.mongo.claims.find({"user_id": user_id}).sort("created_at", DESCENDING))
            )
            return [self._load(Claim, doc) for doc in docs]
        rows = [row for row in self.claims.values() if row.user_id == user_id]
        return sorted(rows, key=lambda row: row.created_at, reverse=True)

    async def get_claim(self, user_id: str, claim_id: str) -> Claim | None:
        self._guard()
        if self.mongo is not None:
            doc = await asyncio.to_thread(lambda: self.mongo.claims.find_one({"_id": claim_id, "user_id": user_id}))
            return self._load(Claim, doc) if doc else None
        row = self.claims.get(claim_id)
        if row and row.user_id == user_id:
            return row
        return None

    async def claims_for_purchase(self, user_id: str, purchase_id: str) -> list[Claim]:
        return [claim for claim in await self.list_claims(user_id) if claim.purchase_id == purchase_id]

    async def claims_by_status(self, status: str) -> list[Claim]:
        self._guard()
        if self.mongo is not None:
            docs = await asyncio.to_thread(lambda: list(self.mongo.claims.find({"status": status})))
            return [self._load(Claim, doc) for doc in docs]
        return [row for row in self.claims.values() if row.status == status]

    async def log_event(self, event: AgentEvent) -> AgentEvent:
        self._guard()
        if self.mongo is not None:
            await asyncio.to_thread(lambda: self._upsert(self.mongo.agent_events, event))
        else:
            self.events.append(event)
        self._publish(event)
        return event

    async def list_events(self, user_id: str, limit: int = 50) -> list[AgentEvent]:
        self._guard()
        if self.mongo is not None:
            docs = await asyncio.to_thread(
                lambda: list(self.mongo.agent_events.find({"user_id": user_id}).sort("time", DESCENDING).limit(limit))
            )
            return [self._load(AgentEvent, doc) for doc in docs]
        rows = [row for row in self.events if row.user_id == user_id]
        return sorted(rows, key=lambda row: row.time, reverse=True)[:limit]

    async def save_run(self, run: AgentRun) -> AgentRun:
        self._guard()
        if self.mongo is not None:
            await asyncio.to_thread(lambda: self._upsert(self.mongo.agent_runs, run))
        else:
            self.runs[run.id] = run
        return run

    async def list_runs(self, user_id: str, limit: int = 40) -> list[AgentRun]:
        self._guard()
        if self.mongo is not None:
            docs = await asyncio.to_thread(
                lambda: list(self.mongo.agent_runs.find({"user_id": user_id}).sort("started_at", DESCENDING).limit(limit))
            )
            return [self._load(AgentRun, doc) for doc in docs]
        rows = [row for row in self.runs.values() if row.user_id == user_id]
        return sorted(rows, key=lambda row: row.started_at, reverse=True)[:limit]

    async def save_refund(self, refund: Refund) -> Refund:
        self._guard()
        if self.mongo is not None:
            await asyncio.to_thread(lambda: self._upsert(self.mongo.refunds, refund))
        else:
            self.refunds[refund.id] = refund
        return refund

    async def list_refunds(self, user_id: str) -> list[Refund]:
        self._guard()
        if self.mongo is not None:
            docs = await asyncio.to_thread(lambda: list(self.mongo.refunds.find({"user_id": user_id})))
            return [self._load(Refund, doc) for doc in docs]
        return [row for row in self.refunds.values() if row.user_id == user_id]

    async def save_allocation(self, allocation: SavingsAllocation) -> SavingsAllocation:
        self._guard()
        if self.mongo is not None:
            await asyncio.to_thread(lambda: self._upsert(self.mongo.savings_allocations, allocation))
        else:
            self.allocations[allocation.id] = allocation
        return allocation

    async def list_allocations(self, user_id: str) -> list[SavingsAllocation]:
        self._guard()
        if self.mongo is not None:
            docs = await asyncio.to_thread(
                lambda: list(
                    self.mongo.savings_allocations.find({"user_id": user_id}).sort("created_at", DESCENDING)
                )
            )
            return [self._load(SavingsAllocation, doc) for doc in docs]
        rows = [row for row in self.allocations.values() if row.user_id == user_id]
        return sorted(rows, key=lambda row: row.created_at, reverse=True)

    async def save_approval(self, approval: UserApproval) -> UserApproval:
        self._guard()
        if self.mongo is not None:
            await asyncio.to_thread(lambda: self._upsert(self.mongo.user_approvals, approval))
        else:
            self.approvals[approval.id] = approval
        return approval

    async def save_receipt(self, receipt: ReceiptRecord) -> ReceiptRecord:
        self._guard()
        if self.mongo is not None:
            await asyncio.to_thread(lambda: self._upsert(self.mongo.receipts, receipt))
        else:
            self.receipts[receipt.id] = receipt
        return receipt

    async def list_receipts(self, user_id: str) -> list[ReceiptRecord]:
        self._guard()
        if self.mongo is not None:
            docs = await asyncio.to_thread(lambda: list(self.mongo.receipts.find({"user_id": user_id})))
            return [self._load(ReceiptRecord, doc) for doc in docs]
        return [row for row in self.receipts.values() if row.user_id == user_id]

    async def save_policy(self, policy: RetailerPolicy) -> RetailerPolicy:
        self._guard()
        if self.mongo is not None:
            await asyncio.to_thread(
                lambda: self.mongo.retailer_policies.replace_one(
                    {"_id": policy.retailer}, {**policy.model_dump(mode="json"), "_id": policy.retailer}, upsert=True
                )
            )
        else:
            self.policies[policy.retailer] = policy
        return policy

    async def get_policy(self, retailer: str) -> RetailerPolicy | None:
        self._guard()
        if self.mongo is not None:
            doc = await asyncio.to_thread(lambda: self.mongo.retailer_policies.find_one({"_id": retailer}))
            if not doc:
                return None
            doc.pop("_id", None)
            return RetailerPolicy.model_validate(doc)
        return self.policies.get(retailer)

    async def get_preferences(self, user_id: str) -> Preferences:
        self._guard()
        if self.mongo is not None:
            doc = await asyncio.to_thread(lambda: self.mongo.notification_preferences.find_one({"_id": user_id}))
            if not doc:
                return Preferences(user_id=user_id)
            doc.pop("_id", None)
            return Preferences.model_validate(doc)
        return self.preferences.get(user_id) or Preferences(user_id=user_id)

    async def save_preferences(self, prefs: Preferences) -> Preferences:
        self._guard()
        if self.mongo is not None:
            await asyncio.to_thread(
                lambda: self.mongo.notification_preferences.replace_one(
                    {"_id": prefs.user_id}, {**prefs.model_dump(mode="json"), "_id": prefs.user_id}, upsert=True
                )
            )
        else:
            self.preferences[prefs.user_id] = prefs
        return prefs

    async def get_connection(self, user_id: str) -> dict:
        self._guard()
        if self.mongo is not None:
            doc = await asyncio.to_thread(lambda: self.mongo.integration_connections.find_one({"_id": user_id}))
            return doc or {"user_id": user_id}
        return self.connections.get(user_id) or {"user_id": user_id}

    async def save_connection(self, user_id: str, patch: dict) -> dict:
        self._guard()
        current = await self.get_connection(user_id)
        current.update(patch)
        current["user_id"] = user_id
        if self.mongo is not None:
            await asyncio.to_thread(
                lambda: self.mongo.integration_connections.replace_one(
                    {"_id": user_id}, {**current, "_id": user_id}, upsert=True
                )
            )
        else:
            self.connections[user_id] = current
        return current

    async def insert_price(self, row: dict) -> None:
        self._guard_prices()
        if self.pg is not None:
            await self._pg(
                """
                INSERT INTO price_observations (
                    time, product_id, retailer, price_cents, in_stock, source, currency,
                    product_url, availability, collection_status, data_origin, user_id, purchase_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    row["time"],
                    row["product_id"],
                    row["retailer"],
                    row["price_cents"],
                    row.get("in_stock"),
                    row["source"],
                    row.get("currency", "USD"),
                    row.get("product_url"),
                    row.get("availability"),
                    row.get("collection_status", "recorded"),
                    row["data_origin"],
                    row["user_id"],
                    row.get("purchase_id"),
                ),
            )
        else:
            self.prices.append(row)

    async def price_history(self, user_id: str, product_id: str, days: int = 30) -> list[PricePoint]:
        self._guard_prices()
        since = datetime.now(timezone.utc) - timedelta(days=days)
        if self.pg is not None:
            rows = await self._pg(
                """
                SELECT time, retailer, price_cents, source, data_origin, product_url,
                       collection_status, currency, in_stock
                FROM price_observations
                WHERE user_id = %s AND product_id = %s AND time >= %s
                ORDER BY time ASC
                """,
                (user_id, product_id, since),
                fetch=True,
            )
            return [
                PricePoint(
                    time=row[0],
                    retailer=row[1],
                    price_cents=row[2],
                    source=row[3],
                    data_origin=row[4],
                    product_url=row[5],
                    collection_status=row[6],
                    currency=row[7],
                    in_stock=row[8],
                )
                for row in rows
            ]
        points = []
        for row in self.prices:
            if row["user_id"] == user_id and row["product_id"] == product_id and row["time"] >= since:
                points.append(PricePoint.model_validate(row))
        return sorted(points, key=lambda point: point.time)

    async def record_price_change(self, row: dict) -> None:
        self._guard_prices()
        if self.pg is not None:
            await self._pg(
                """
                INSERT INTO price_change_events (
                    time, user_id, product_id, purchase_id, retailer, previous_price_cents,
                    new_price_cents, delta_cents, source, data_origin
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    row["time"],
                    row["user_id"],
                    row["product_id"],
                    row.get("purchase_id"),
                    row["retailer"],
                    row.get("previous_price_cents"),
                    row["new_price_cents"],
                    row["delta_cents"],
                    row["source"],
                    row["data_origin"],
                ),
            )
        else:
            self.price_changes.append(row)

    async def list_price_changes(self, user_id: str) -> list[dict]:
        self._guard_prices()
        if self.pg is not None:
            rows = await self._pg(
                """
                SELECT time, product_id, purchase_id, new_price_cents, delta_cents, source, data_origin
                FROM price_change_events WHERE user_id = %s ORDER BY time DESC
                """,
                (user_id,),
                fetch=True,
            )
            return [
                {
                    "time": row[0],
                    "product_id": row[1],
                    "purchase_id": row[2],
                    "new_price_cents": row[3],
                    "delta_cents": row[4],
                    "source": row[5],
                    "data_origin": row[6],
                }
                for row in rows
            ]
        return [row for row in self.price_changes if row["user_id"] == user_id]

    async def record_monitoring(self, row: dict) -> None:
        self._guard_prices()
        if self.pg is not None:
            await self._pg(
                """
                INSERT INTO monitoring_events (time, user_id, product_id, purchase_id, status, detail, data_origin)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    row["time"],
                    row["user_id"],
                    row["product_id"],
                    row.get("purchase_id"),
                    row["status"],
                    row.get("detail"),
                    row["data_origin"],
                ),
            )
        else:
            self.monitoring.append(row)

    async def save_demo_submission(self, submission: dict) -> dict:
        self._guard()
        if self.mongo is not None:
            await asyncio.to_thread(
                lambda: self.mongo.demo_submissions.replace_one(
                    {"_id": submission["id"]}, {**submission, "_id": submission["id"]}, upsert=True
                )
            )
        else:
            self.demo_submissions[submission["id"]] = submission
        return submission

    async def get_demo_submission(self, submission_id: str) -> dict | None:
        self._guard()
        if self.mongo is not None:
            doc = await asyncio.to_thread(lambda: self.mongo.demo_submissions.find_one({"_id": submission_id}))
            return doc
        return self.demo_submissions.get(submission_id)

    async def delete_demo_for_user(self, user_id: str) -> None:
        self._guard()
        demo_claim_ids = {claim.id for claim in await self.list_claims(user_id) if claim.data_origin == "demo"}
        if self.mongo is not None:
            def _wipe() -> None:
                query = {"user_id": user_id, "data_origin": "demo"}
                for name in (
                    "purchases",
                    "claims",
                    "agent_events",
                    "agent_runs",
                    "refunds",
                    "receipts",
                    "savings_allocations",
                ):
                    self.mongo[name].delete_many(query)
                if demo_claim_ids:
                    self.mongo.user_approvals.delete_many(
                        {"user_id": user_id, "claim_id": {"$in": list(demo_claim_ids)}}
                    )

            await asyncio.to_thread(_wipe)
        else:
            self.purchases = {k: v for k, v in self.purchases.items() if not _demo(v, user_id)}
            self.claims = {k: v for k, v in self.claims.items() if not _demo(v, user_id)}
            self.events = [row for row in self.events if not _demo(row, user_id)]
            self.runs = {k: v for k, v in self.runs.items() if not _demo(v, user_id)}
            self.refunds = {k: v for k, v in self.refunds.items() if not _demo(v, user_id)}
            self.receipts = {k: v for k, v in self.receipts.items() if not _demo(v, user_id)}
            self.allocations = {k: v for k, v in self.allocations.items() if not _demo(v, user_id)}
            self.approvals = {
                k: v
                for k, v in self.approvals.items()
                if not (v.user_id == user_id and v.claim_id in demo_claim_ids)
            }
        self._guard_prices()
        if self.pg is not None:
            await self._pg("DELETE FROM price_observations WHERE user_id = %s AND data_origin = 'demo'", (user_id,))
            await self._pg("DELETE FROM price_change_events WHERE user_id = %s AND data_origin = 'demo'", (user_id,))
            await self._pg("DELETE FROM monitoring_events WHERE user_id = %s AND data_origin = 'demo'", (user_id,))
        else:
            self.prices = [row for row in self.prices if not (row.get("user_id") == user_id and row.get("data_origin") == "demo")]
            self.price_changes = [
                row for row in self.price_changes if not (row.get("user_id") == user_id and row.get("data_origin") == "demo")
            ]
            self.monitoring = [
                row for row in self.monitoring if not (row.get("user_id") == user_id and row.get("data_origin") == "demo")
            ]

    async def _pg(self, sql: str, params: tuple, fetch: bool = False):
        if self.pg is None:
            raise PersistenceError(self.pg_detail)

        def run():
            with self.pg.cursor() as cur:
                cur.execute(sql, params)
                if fetch:
                    return cur.fetchall()
                return None

        async with self._pg_lock:
            try:
                return await asyncio.to_thread(run)
            except Exception as exc:
                raise PersistenceError(safe_detail(exc)) from exc

    @staticmethod
    def _upsert(collection, model) -> None:
        data = model.model_dump(mode="json")
        data["_id"] = model.id
        collection.replace_one({"_id": model.id}, data, upsert=True)

    @staticmethod
    def _load(model_cls: type[T], doc: dict) -> T:
        payload = dict(doc)
        payload.pop("_id", None)
        return model_cls.model_validate(payload)


def _demo(row, user_id: str) -> bool:
    return getattr(row, "user_id", None) == user_id and getattr(row, "data_origin", None) == "demo"


repo = Repository()
