"""Run: cd backend && python -m pytest data  (offline: Mongo is the in-process fake from conftest.py)."""

import asyncio
from datetime import datetime, timedelta, timezone

from app.models import AgentEvent, Claim, Purchase, RetailerPolicy
from data import mongo, mongo_indexes, seed

NOW = datetime.now(timezone.utc)


def _purchase(pid: str, days_ago: int, user: str = "u1") -> Purchase:
    return Purchase(id=pid, user_id=user, retailer="Target", product_id=f"target:{pid}", product_name=pid,
                    price_paid_cents=1000, purchased_at=NOW - timedelta(days=days_ago))


def test_purchases_round_trip_newest_first_and_updates_keep_other_fields(fake_mongo):
    async def scenario():
        for pid, days in (("old", 9), ("new", 1), ("mid", 4)):
            await mongo.upsert_purchase(_purchase(pid, days))
        await mongo.upsert_purchase(_purchase("theirs", 0, user="u2"))
        assert [p.id for p in await mongo.list_purchases("u1")] == ["new", "mid", "old"]
        assert await mongo.get_purchase("missing") is None

        fake_mongo["purchases"].docs[0]["receipt"] = {"raw": "..."}  # extra data another layer stored
        await mongo.upsert_purchase(_purchase("old", 9).model_copy(update={"status": "claimed"}))
        assert (await mongo.get_purchase("old")).status == "claimed"
        stored = await fake_mongo["purchases"].find_one({"_id": "old"})
        assert stored["receipt"] == {"raw": "..."} and len(fake_mongo["purchases"].docs) == 4

    asyncio.run(scenario())


def test_claims_round_trip_and_update_in_place(fake_mongo):
    async def scenario():
        first = Claim(id="c1", user_id="u1", purchase_id="p1", retailer="Target", refund_cents=500, created_at=NOW - timedelta(hours=2))
        second = Claim(id="c2", user_id="u1", purchase_id="p2", retailer="Target", refund_cents=700, created_at=NOW)
        await mongo.save_claim(first)
        await mongo.save_claim(second)
        await mongo.save_claim(first.model_copy(update={"status": "submitted", "submitted_at": NOW}))
        assert [(c.id, c.status) for c in await mongo.list_claims("u1")] == [("c2", "awaiting_approval"), ("c1", "submitted")]
        assert (await mongo.get_claim("c1")).submitted_at is not None
        assert await mongo.get_claim("missing") is None

    asyncio.run(scenario())


def test_events_come_back_newest_first_with_ties_in_logging_order(fake_mongo):
    async def scenario():
        def event(eid: str, when: datetime) -> AgentEvent:
            return AgentEvent(id=eid, user_id="u1", time=when, kind="price_checked", message=eid)

        await mongo.log_event(event("earlier", NOW - timedelta(minutes=5)))
        # Two events inside the same millisecond: Mongo stores them with the same time.
        same_ms = NOW.replace(microsecond=5000)
        await mongo.log_event(event("tie-first", same_ms + timedelta(microseconds=100)))
        await mongo.log_event(event("tie-second", same_ms + timedelta(microseconds=200)))
        assert [e.id for e in await mongo.list_events("u1")] == ["tie-second", "tie-first", "earlier"]
        assert [e.id for e in await mongo.list_events("u1", limit=1)] == ["tie-second"]
        assert await mongo.list_events("someone-else") == []

    asyncio.run(scenario())


def test_policies_are_keyed_by_retailer_whatever_the_case(fake_mongo):
    async def scenario():
        await mongo.save_policy(RetailerPolicy(retailer="Best Buy", window_days=15, conditions=["a"]))
        await mongo.save_policy(RetailerPolicy(retailer="Best Buy", window_days=30, conditions=["a", "b"]))
        policy = await mongo.get_policy(" best buy")
        assert policy.window_days == 30 and policy.conditions == ["a", "b"] and policy.retailer == "Best Buy"
        assert len(fake_mongo["retailer_policies"].docs) == 1
        assert await mongo.get_policy("Unknown") is None

    asyncio.run(scenario())


def test_indexes_match_the_data_model(fake_mongo):
    assert asyncio.run(mongo_indexes.ensure_indexes()) == 8
    assert fake_mongo["retailer_policies"].indexes == [((("retailer", 1),), True)]
    assert ((("user_id", 1), ("time", -1)), False) in fake_mongo["agent_events"].indexes


def test_seed_resets_the_demo_user_and_leaves_everyone_else(fake_mongo):
    async def scenario():
        await mongo.upsert_purchase(_purchase("theirs", 0, user="someone-else"))
        await mongo.upsert_purchase(_purchase("stale", 0, user="demo-user"))
        counts = await seed.seed("demo-user")
        assert counts == {"purchases": 6, "claims": 4, "events": counts["events"], "price_points": 0}
        again = await seed.seed("demo-user")  # running it twice doesn't duplicate anything
        assert again == counts

        ids = {p.id for p in await mongo.list_purchases("demo-user")}
        assert ids == {"p1", "p2", "p3", "p4", "p5", "p6"}
        assert [p.id for p in await mongo.list_purchases("someone-else")] == ["theirs"]
        assert len(await mongo.list_events("demo-user", 500)) == counts["events"]
        assert (await fake_mongo["users"].find_one({"_id": "demo-user"}))["name"] == "Demo User"

    asyncio.run(scenario())
