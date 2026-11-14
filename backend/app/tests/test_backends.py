"""The seams around Layer 2: the database store, the arq queue, the bank and the vault, Grok."""

import asyncio
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from agents import grok_bot
from app import finance_gateway, jobs, store
from app.config import get_settings
from app.finance_gateway import BankTxn
from app.models import Claim, Purchase, PurchaseCreate
from app.workers import tasks
from app.workers.worker import WorkerSettings

NOW = datetime.now(timezone.utc)


class SharedStore(store.MemoryStore):
    """Stands in for the database: same data, but reports itself as shared with a worker."""

    name = "db"


def use_env(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


# --- Store selection and the Layer 4 adapter --------------------------------------------------


def test_unimplemented_layer4_falls_back_to_memory_unless_db_is_forced(api, monkeypatch):
    from app.main import create_app
    from fastapi.testclient import TestClient

    use_env(monkeypatch, MOCK_MODE="false", GEMINI_API_KEY="")
    with TestClient(create_app()) as client:  # auto: Layer 4 raises NotImplementedError → demo data
        assert client.get("/health").json()["store"] == "memory"
        assert len(client.get("/purchases").json()) == 6

    use_env(monkeypatch, DATA_BACKEND="db")
    with TestClient(create_app()) as client:  # forced: say what's missing instead of faking it
        assert client.get("/health").json()["store"] == "db"
        for path in ("/purchases", "/claims", "/activity", "/savings", "/prices/x"):
            assert client.get(path).status_code == 501, path
        assert client.post("/demo/reset").status_code == 409


def test_db_store_passes_through_to_layer4(monkeypatch):
    from data import mongo, timescale

    purchases, claims, events, prices = {}, {}, [], []

    async def upsert_purchase(p):
        purchases[p.id] = p
        return p

    async def save_claim(c):
        claims[c.id] = c
        return c

    async def list_claims(user_id):
        return list(claims.values())

    async def get_purchase(purchase_id):
        return purchases.get(purchase_id)

    async def log_event(e):
        events.append(e)

    async def insert_price(product_id, retailer, price_cents, *, time=None, in_stock=None, source="poller"):
        prices.append((product_id, price_cents, source))

    for name, fn in [("upsert_purchase", upsert_purchase), ("save_claim", save_claim), ("list_claims", list_claims),
                     ("get_purchase", get_purchase), ("log_event", log_event)]:
        monkeypatch.setattr(mongo, name, fn)
    monkeypatch.setattr(timescale, "insert_price", insert_price)

    async def scenario():
        db = store.DbStore()
        purchase = Purchase(id="p9", user_id="demo-user", retailer="Target", product_id="target:x", product_name="X",
                            price_paid_cents=1000, purchased_at=NOW)
        claim = Claim(id="c9", user_id="demo-user", purchase_id="p9", retailer="Target", refund_cents=100, created_at=NOW)
        await db.save_purchase(purchase)
        await db.save_claim(claim)
        await db.insert_price("target:x", "Target", 900, source="demo")
        assert (await db.get_purchase("p9")).product_name == "X"
        assert (await db.get_claim("c9")).refund_cents == 100  # found by listing: Layer 4 has no get_claim yet
        assert await db.get_claim("missing") is None
        assert prices == [("target:x", 900, "demo")]
        with pytest.raises(NotImplementedError):
            await db.list_purchases("demo-user")  # still a Layer 4 stub

    asyncio.run(scenario())


# --- Job queue ----------------------------------------------------------------------------------


def test_worker_registers_every_job():
    names = {fn.__name__ for fn in WorkerSettings.functions}
    assert names == {"scan_new_purchases", "poll_prices", "evaluate_purchase", "submit_claim",
                     "issue_demo_refund", "reconcile_refunds", "watch_policies"}
    assert len(WorkerSettings.cron_jobs) == 4


def test_jobs_run_inline_when_redis_is_down():
    async def scenario():
        store.set_store(SharedStore())  # state is "in the database", so arq is preferred
        job_id = await jobs.enqueue("scan_new_purchases", "demo-user")
        assert job_id.startswith("inline-") and jobs.mode() == "inline"  # nothing listens on REDIS_URL
        await jobs.drain()
        assert len(await store.get_store().list_purchases("demo-user")) == 8

    asyncio.run(scenario())


def test_jobs_go_through_arq_and_the_worker_runs_the_pipeline(monkeypatch):
    fakeredis = pytest.importorskip("fakeredis")
    import arq.worker
    import redis.asyncio as aredis
    from arq.connections import ArqRedis

    async def no_redis_info(*args, **kwargs):  # fakeredis has no INFO command
        return None

    monkeypatch.setattr(arq.worker, "log_redis_info", no_redis_info)

    async def scenario():
        from app.main import create_app

        shared = SharedStore()
        store.set_store(shared)
        finance_gateway.reset_simulation(shared.seed)
        pool = ArqRedis(
            connection_pool=aredis.ConnectionPool(connection_class=fakeredis.FakeAsyncRedisConnection, server=fakeredis.FakeServer())
        )
        monkeypatch.setattr(jobs, "_pool", pool)
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            assert (await client.get("/health")).json()["jobs"] == "arq"
            assert (await client.post("/claims/c1/approve")).json()["status"] == "submitting"
            scan = (await client.post("/purchases/scan")).json()
            assert not scan["job_id"].startswith("inline-")
            queued = sorted(job.function for job in await pool.queued_jobs())
            assert queued == ["scan_new_purchases", "submit_claim"]
            assert (await shared.get_claim("c1")).status == "submitting"  # nothing ran in the API process

            worker = arq.worker.Worker(
                functions=WorkerSettings.functions, cron_jobs=WorkerSettings.cron_jobs, redis_pool=pool,
                burst=True, poll_delay=0.05,
            )
            await worker.main()  # submit_claim → issue_demo_refund → reconcile_refunds, plus the scan
            assert worker.jobs_failed == 0

            claim = (await client.get("/claims")).json()
            c1 = next(c for c in claim if c["id"] == "c1")
            assert c1["status"] == "refund_received" and c1["solana_tx_signature"]
            assert len((await client.get("/purchases")).json()) == 8
        monkeypatch.setattr(jobs, "_pool", None)
        await pool.aclose()

    asyncio.run(scenario())


# --- Bank and vault ---------------------------------------------------------------------------


def test_bank_uses_nessie_when_live_and_the_simulator_covers_an_outage(monkeypatch):
    from finance import nessie

    use_env(monkeypatch, MOCK_MODE="false")

    async def scenario():
        assert finance_gateway.modes()["bank"] == "nessie"

        async def list_deposits(account_id):
            assert account_id == "test-account"
            return [{"_id": "d1", "amount": 19.5, "description": "PRICE ADJUSTMENT", "transaction_date": "2026-11-14"}]

        async def simulate_refund(account_id, amount_cents, description):
            return {"_id": "d2", "amount": amount_cents / 100, "description": description}

        monkeypatch.setattr(nessie, "list_deposits", list_deposits)
        monkeypatch.setattr(nessie, "simulate_refund", simulate_refund)
        assert await finance_gateway.deposits() == [BankTxn("d1", 1950, "PRICE ADJUSTMENT", date(2026, 11, 14))]
        assert await finance_gateway.issue_refund(5000, "refund") == BankTxn("d2", 5000, "refund", None)
        assert finance_gateway.modes()["bank"] == "nessie"

        async def down(*args):
            raise httpx.ConnectError("nessie is down")

        monkeypatch.setattr(nessie, "list_deposits", down)
        monkeypatch.setattr(nessie, "simulate_refund", down)
        monkeypatch.setattr(nessie, "list_purchases", down)
        refund = await finance_gateway.issue_refund(1234, "PRICE ADJUSTMENT Target")  # the simulator covers
        assert refund.id.startswith("sim-dep-") and finance_gateway.modes()["bank"] == "nessie+simulated"
        assert await finance_gateway.deposits() == [refund]  # still visible, so the claim reconciles
        assert await finance_gateway.card_purchases() == []  # never confirm against made-up charges

    asyncio.run(scenario())


def test_vault_uses_solana_when_live_and_reports_failures(monkeypatch):
    from finance import solana_vault

    use_env(monkeypatch, MOCK_MODE="false")
    claim = Claim(id="c9", user_id="demo-user", purchase_id="p9", retailer="Target", refund_cents=700,
                  created_at=NOW, solana_tx_signature="sim-x")

    async def scenario():
        async def record(user_id, claim_id, amount_cents):
            return "5LiveSignature"

        async def balance(user_id):
            return 4200

        monkeypatch.setattr(solana_vault, "record_recovery", record)
        monkeypatch.setattr(solana_vault, "get_vault_balance_cents", balance)
        assert await finance_gateway.record_recovery("demo-user", "c9", 700) == "5LiveSignature"
        assert await finance_gateway.vault_balance_cents("demo-user", [claim]) == 4200  # from the chain
        assert finance_gateway.modes()["vault"] == "solana"

        async def down(*args):
            raise solana_vault.VaultError("devnet RPC down")

        monkeypatch.setattr(solana_vault, "record_recovery", down)
        with pytest.raises(solana_vault.VaultError):  # the caller decides when to give up
            await finance_gateway.record_recovery("demo-user", "c9", 700)

        finance_gateway.mark_vault_down()
        signature = await finance_gateway.record_recovery("demo-user", "c9", 700)
        assert signature.startswith("sim-") and finance_gateway.modes()["vault"] == "solana+simulated"
        assert signature == await finance_gateway.record_recovery("demo-user", "c9", 700)  # deterministic

    asyncio.run(scenario())


def test_mock_mode_vault_is_derived_from_claims():
    recorded = Claim(id="c9", user_id="demo-user", purchase_id="p9", retailer="Target", refund_cents=700,
                     created_at=NOW, solana_tx_signature="sim-x")
    pending = recorded.model_copy(update={"id": "c10", "solana_tx_signature": None})

    async def scenario():
        assert (await finance_gateway.record_recovery("demo-user", "c9", 700)).startswith("sim-")
        assert await finance_gateway.vault_balance_cents("demo-user", [recorded, pending]) == 700
        assert finance_gateway.modes() == {"bank": "simulated", "vault": "simulated"}

    asyncio.run(scenario())


def test_refund_matching_rules():
    purchase = Purchase(id="p1", user_id="u", retailer="Best Buy", product_id="x", product_name="X",
                        price_paid_cents=39999, purchased_at=NOW, order_number="BBY01-80612")
    claim = Claim(id="c1", user_id="u", purchase_id="p1", retailer="Best Buy", refund_cents=5000,
                  created_at=NOW, submitted_at=NOW, status="submitted")
    today = NOW.date()
    wrong_amount = BankTxn("d1", 4999, "PRICE ADJUSTMENT", today)
    too_old = BankTxn("d2", 5000, "PRICE ADJUSTMENT", today - timedelta(days=5))
    plain = BankTxn("d3", 5000, "DEPOSIT", today)
    referenced = BankTxn("d4", 5000, "PRICE ADJUSTMENT Best Buy BBY01-80612", today)
    match = tasks._match_deposit
    assert match(claim, purchase, [wrong_amount, too_old], set()) is None
    assert match(claim, purchase, [plain, referenced], set()) == referenced  # the order number wins
    assert match(claim, purchase, [plain, referenced], {"d4"}) == plain  # d4 already paid another claim
    assert match(claim, purchase, [plain], {"d3"}) is None

    # Nessie keeps whole dollars: a $37.50 refund comes back as $37. It still matches when the
    # deposit names the claim, but not on the amount alone, and not for a claim with a longer id.
    odd = claim.model_copy(update={"refund_cents": 3750})
    named = BankTxn("d5", 3700, "PRICE ADJUSTMENT Best Buy BBY01-80612 (claim c1)", today)
    unnamed = BankTxn("d6", 3700, "DEPOSIT", today)
    assert match(odd, purchase, [unnamed, named], set()) == named
    assert match(odd, purchase, [unnamed], set()) is None
    other = odd.model_copy(update={"id": "c12"})
    no_order = purchase.model_copy(update={"order_number": None})
    assert match(other, no_order, [named], set()) is None  # "c1" in the text is not claim c12


def test_card_charge_confirms_a_purchase_despite_dropped_cents():
    async def scenario():
        _fresh_memory_store()
        item = PurchaseCreate(retailer="Best Buy", product_name="Camera", price_paid_cents=24999, purchased_at=NOW)
        charges = [BankTxn("n1", 24900, "Best Buy Camera", NOW.date()), BankTxn("n2", 30000, "Other", NOW.date())]
        purchase = await tasks.register_purchase(item, user_id="demo-user", source="email", card_charges=charges)
        assert purchase.nessie_purchase_id == "n1"

    asyncio.run(scenario())


def _fresh_memory_store():
    memory = store.MemoryStore()
    store.set_store(memory)
    finance_gateway.reset_simulation(memory.seed)
    return memory


def test_vault_failure_is_retried_on_the_next_run(monkeypatch):
    calls = []

    async def flaky(user_id, claim_id, amount_cents):
        calls.append(claim_id)
        if len(calls) == 1:
            raise ConnectionError("devnet RPC hiccup")
        return "5RealSignature"

    monkeypatch.setattr(finance_gateway, "record_recovery", flaky)

    async def scenario():
        memory = _fresh_memory_store()
        claim = await memory.get_claim("c1")
        await memory.save_claim(claim.model_copy(update={"status": "submitted", "submitted_at": NOW}))
        await finance_gateway.issue_refund(5000, "PRICE ADJUSTMENT Best Buy (claim c1)")

        assert await tasks.reconcile_refunds({}) == 1
        claim = await memory.get_claim("c1")
        assert claim.status == "refund_received" and claim.solana_tx_signature is None
        assert (await memory.list_events("demo-user", 1))[0].kind == "refund_received"

        assert await tasks.reconcile_refunds({}) == 0  # nothing new to match, but the vault is retried
        assert (await memory.get_claim("c1")).solana_tx_signature == "5RealSignature"
        latest = (await memory.list_events("demo-user", 1))[0]
        assert latest.kind == "vault_recorded" and "simulated" not in latest.message

    asyncio.run(scenario())


def test_vault_record_is_simulated_after_solana_keeps_failing(monkeypatch):
    use_env(monkeypatch, MOCK_MODE="false", GEMINI_API_KEY="")  # live vault, but the test wallet doesn't exist

    async def scenario():
        memory = _fresh_memory_store()
        claim = await memory.get_claim("c1")
        await memory.save_claim(claim.model_copy(update={"status": "refund_received", "refund_received_at": NOW}))

        for _ in range(tasks.VAULT_ATTEMPTS - 1):
            await tasks.reconcile_refunds({})
            assert (await memory.get_claim("c1")).solana_tx_signature is None  # still trying Solana
        await tasks.reconcile_refunds({})
        assert (await memory.get_claim("c1")).solana_tx_signature.startswith("sim-")
        latest = (await memory.list_events("demo-user", 1))[0]
        assert latest.kind == "vault_recorded" and "This entry is simulated" in latest.message
        assert "wallet isn't set up" in latest.message  # the test wallet doesn't exist
        assert finance_gateway.modes()["vault"] == "solana+simulated"

    asyncio.run(scenario())


# --- Grok policy watch ---------------------------------------------------------------------------


def test_policy_watch_stores_changes_and_new_purchases_use_them(monkeypatch):
    async def watch(stored, **kwargs):
        if stored.retailer != "Best Buy":
            return grok_bot.PolicyWatchResult(retailer=stored.retailer, changed=False, note="Same.", policy=stored)
        shorter = stored.model_copy(update={"window_days": 7})
        return grok_bot.PolicyWatchResult(
            retailer="Best Buy", changed=True, note="Window cut from 15 to 7 days.", policy=shorter
        )

    monkeypatch.setattr(grok_bot, "watch_policy", watch)

    async def scenario():
        memory = store.MemoryStore()
        store.set_store(memory)
        result = await tasks.watch_policies({})
        assert result["changed"] == ["Best Buy"] and result["reviewed"] == 2  # Best Buy and Target are active
        assert (await memory.get_policy("best buy")).window_days == 7
        event = (await memory.list_events("demo-user", 1))[0]
        assert event.kind == "eligibility_checked" and "Window cut from 15 to 7 days" in event.message

        item = PurchaseCreate(retailer="Best Buy", product_name="New TV", price_paid_cents=50000, purchased_at=NOW)
        purchase = await tasks.register_purchase(item, user_id="demo-user", source="manual")
        assert purchase.adjustment_window_ends - purchase.purchased_at == timedelta(days=7)

    asyncio.run(scenario())


def test_policy_watch_is_quiet_when_grok_is_off(api):
    result = api.post("/demo/jobs/watch_policies").json()["result"]
    assert result["reviewed"] == 0 and result["changed"] == []
    assert "Grok disabled" in result["notes"][0]
    assert len(api.get("/activity").json()) == 9  # nothing added to the feed


# --- Live price feed -----------------------------------------------------------------------------


def test_live_price_from_the_product_page_drives_drop_detection(monkeypatch):
    from agents import price_reader

    use_env(monkeypatch, MOCK_MODE="false", GEMINI_API_KEY="", XAI_API_KEY="")
    page_price = {"https://shop.test/tv": 44999, "https://shop.test/odd": 999}
    asked = []

    async def fetch(url, **kwargs):
        asked.append(url)
        return page_price.get(url)

    monkeypatch.setattr(price_reader, "fetch_price_cents", fetch)

    async def scenario():
        memory = _fresh_memory_store()
        tv = await tasks.register_purchase(
            PurchaseCreate(retailer="Best Buy", product_name="New TV", price_paid_cents=50000, purchased_at=NOW,
                           product_url="https://shop.test/tv"),
            user_id="demo-user", source="manual",
        )
        odd = await tasks.register_purchase(
            PurchaseCreate(retailer="Target", product_name="Blender", price_paid_cents=9000, purchased_at=NOW,
                           product_url="https://shop.test/odd"),
            user_id="demo-user", source="manual",
        )
        assert await tasks.poll_prices({}) == 1  # only the TV: the page says $449.99, we paid $500.00
        await jobs.drain()
        assert set(asked) == {"https://shop.test/tv", "https://shop.test/odd"}  # purchases without a URL aren't fetched
        tv = await memory.get_purchase(tv.id)
        assert tv.status == "claim_pending" and tv.current_price_cents == 44999
        claim = next(c for c in await memory.list_claims("demo-user") if c.purchase_id == tv.id)
        assert claim.refund_cents == 5001
        # $9.99 for a $90.00 blender is a different product, not a drop: ignored, last price held.
        assert (await memory.get_purchase(odd.id)).current_price_cents == 9000

    asyncio.run(scenario())


def test_mock_mode_never_fetches_product_pages(monkeypatch):
    from agents import price_reader
    from app import price_feed

    async def fetch(url, **kwargs):
        raise AssertionError("mock mode must not call out")

    monkeypatch.setattr(price_reader, "fetch_price_cents", fetch)
    purchase = Purchase(id="p", user_id="demo-user", retailer="Target", product_id="target:x", product_name="X",
                        price_paid_cents=1000, purchased_at=NOW, product_url="https://shop.test/x")
    assert asyncio.run(price_feed.current_price_cents(purchase, store.MemoryStore())) == 1000


# --- Automation endpoint (for a Grok Bot routine) --------------------------------------------------


def test_policy_page_automation_needs_the_token_and_stores_changes(api, monkeypatch):
    page = {"retailer": "Best Buy", "page_text": "Best Buy adjusts the price if the same item drops within 7 days of purchase."}
    assert api.post("/automations/policy-page", json=page).status_code == 503  # no token configured: off

    use_env(monkeypatch, AUTOMATION_TOKEN="s3cret")
    assert api.post("/automations/policy-page", json=page).status_code == 401
    wrong = {"Authorization": "Bearer nope"}
    assert api.post("/automations/policy-page", json=page, headers=wrong).status_code == 401

    async def watch(stored, *, page_text=None, **kwargs):
        assert "within 7 days" in page_text
        shorter = stored.model_copy(update={"window_days": 7})
        return grok_bot.PolicyWatchResult(retailer=stored.retailer, changed=True, note="Window cut to 7 days.", policy=shorter)

    monkeypatch.setattr(grok_bot, "watch_policy", watch)
    ok = api.post("/automations/policy-page", json=page, headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200 and ok.json()["changed"] is True and ok.json()["window_days"] == 7
    assert api.get("/policies/Best Buy").json()["window_days"] == 7  # eligibility now uses the new window
    assert "Grok Bot policy watch" in api.get("/activity?limit=1").json()[0]["message"]
    too_short = {"retailer": "Best Buy", "page_text": "hi"}
    assert api.post("/automations/policy-page", json=too_short, headers={"Authorization": "Bearer s3cret"}).status_code == 422
