"""The demo flow through the HTTP API: seed → scan → price drop → claim → approve → refund → vault."""

import time
from datetime import datetime, timedelta, timezone

from agents import claim_bot

NOW = datetime.now(timezone.utc)


def test_seed_state_is_consistent(api):
    health = api.get("/health").json()
    assert health["status"] == "ok" and health["store"] == "memory" and health["jobs"] == "inline"

    purchases = api.get("/purchases").json()
    assert len(purchases) == 6
    dates = [p["purchased_at"] for p in purchases]
    assert dates == sorted(dates, reverse=True)  # newest first

    claims = api.get("/claims").json()
    assert claims[0]["id"] == "c1" and claims[0]["status"] == "awaiting_approval"

    # Savings are computed from the claims, so they have to agree with them.
    won = [c for c in claims if c["status"] == "refund_received"]
    savings = api.get("/savings").json()
    assert savings["total_recovered_cents"] == sum(c["refund_cents"] for c in won) == 8250
    assert savings["vault_balance_cents"] == 8250 and savings["claims_won"] == 3
    assert savings["pending_cents"] == 5000 and savings["vault_address"]

    history = api.get("/prices/bestbuy:6505727?days=30").json()
    assert history[0]["price_cents"] == 39999 and history[-1]["price_cents"] == 34999
    assert len(history) <= 31 and [p["time"] for p in history] == sorted(p["time"] for p in history)

    assert api.get("/purchases/p1").json()["product_name"].startswith("Sony")
    assert api.get("/purchases/nope").status_code == 404
    assert api.get("/activity?limit=2").json()[0]["kind"] == "claim_drafted"
    assert api.get("/activity?limit=0").status_code == 422


def test_policy_endpoint_returns_the_policy_in_use(api):
    best_buy = api.get("/policies/Best Buy").json()
    assert best_buy["window_days"] == 15 and best_buy["summary"] and len(best_buy["conditions"]) >= 2
    assert api.get("/policies/best%20buy").json()["retailer"] == "Best Buy"  # case-insensitive
    unknown = api.get("/policies/Shady Shop").json()
    assert unknown["window_days"] is None and unknown["conditions"] == []


def test_scan_adds_only_purchases_it_does_not_already_track(api):
    assert api.post("/purchases/scan").json()["job_id"].startswith("inline-")
    api.drain()
    purchases = api.get("/purchases").json()
    new = [p for p in purchases if p["id"] not in {"p1", "p2", "p3", "p4", "p5", "p6"}]
    # Four receipts hold five items; Sony, Ninja and Anker are already tracked.
    assert sorted(p["product_name"] for p in new) == ["Apple AirPods Pro 3 Wireless Earbuds", "Hefty Trash Bags 40ct"]
    airpods = next(p for p in new if "AirPods" in p["product_name"])
    assert airpods["status"] == "monitoring" and airpods["source"] == "email"
    assert airpods["product_id"] == "bestbuy:apple-airpods-pro-3-wireless-earbuds"
    assert airpods["nessie_purchase_id"] == "sim-card-airpods"  # confirmed against a card charge
    assert airpods["adjustment_window_ends"] > airpods["purchased_at"]  # Best Buy: 15 days
    assert api.get(f"/prices/{airpods['product_id']}").json()[-1]["price_cents"] == 24999
    found = [e for e in api.get("/activity").json() if e["kind"] == "purchase_found"]
    assert "AirPods" in found[0]["message"] or "AirPods" in found[1]["message"]

    api.post("/purchases/scan")
    api.drain()
    assert len(api.get("/purchases").json()) == len(purchases)  # second scan finds nothing new
    assert "nothing new" in api.get("/activity?limit=1").json()[0]["message"]


def test_price_drop_on_cue_drafts_a_claim(api):
    drop = api.post("/demo/price-drop").json()
    assert drop["purchase_id"] == "p2"  # the most expensive purchase being monitored
    assert (drop["old_price_cents"], drop["new_price_cents"]) == (12999, 11049)
    api.drain()

    purchase = api.purchase("p2")
    assert purchase["status"] == "claim_pending" and purchase["current_price_cents"] == 11049
    claim = api.get("/claims").json()[0]  # newest first
    assert claim["purchase_id"] == "p2" and claim["status"] == "awaiting_approval"
    assert claim["refund_cents"] == 12999 - 11049 and "$19.50" in claim["explanation"]
    assert api.kinds(3) == ["claim_drafted", "eligibility_checked", "price_drop"]
    assert api.get("/prices/target:89012345").json()[-1]["price_cents"] == 11049
    assert api.get("/savings").json()["pending_cents"] == 5000 + 1950

    # Polling again at the same price must not draft a second claim.
    api.post("/demo/jobs/poll_prices")
    api.drain()
    assert len([c for c in api.get("/claims").json() if c["purchase_id"] == "p2"]) == 1


def test_approve_files_the_claim_then_refund_and_vault_follow(api):
    before = api.get("/savings").json()
    approved = api.post("/claims/c1/approve").json()
    assert approved["status"] == "submitting"
    api.drain()

    claim = api.claim("c1")
    assert claim["status"] == "refund_received"
    assert claim["submitted_at"] and claim["refund_received_at"]
    assert claim["nessie_deposit_id"].startswith("sim-dep-") and claim["solana_tx_signature"].startswith("sim-")
    assert api.purchase("p1")["status"] == "claimed"

    assert api.kinds(4) == ["vault_recorded", "refund_received", "claim_submitted", "claim_submitting"]
    submitted = next(e for e in api.get("/activity").json() if e["kind"] == "claim_submitted")
    assert submitted["screenshot_url"] == "http://testserver/screenshots/c1/03_confirmation.png"
    shot = api.get("/screenshots/c1/03_confirmation.png")
    assert shot.status_code == 200 and shot.headers["content-type"] == "image/png"

    after = api.get("/savings").json()
    assert after["total_recovered_cents"] == before["total_recovered_cents"] + 5000
    assert after["vault_balance_cents"] == before["vault_balance_cents"] + 5000
    assert after["pending_cents"] == 0 and after["claims_won"] == before["claims_won"] + 1

    # Approving again changes nothing and files nothing.
    assert api.post("/claims/c1/approve").json()["status"] == "refund_received"
    api.drain()
    assert api.kinds().count("claim_submitting") == 1
    assert api.post("/claims/nope/approve").status_code == 404


def test_failed_submission_is_reported_and_can_be_retried(api, monkeypatch, tmp_path):
    from app.config import get_settings

    working_form = get_settings().retailer_claim_url
    blank = tmp_path / "blank.html"
    blank.write_text("<html><body>Down for maintenance</body></html>")
    monkeypatch.setenv("RETAILER_CLAIM_URL", blank.as_uri())
    monkeypatch.setattr(claim_bot, "CONFIRMATION_TIMEOUT_MS", 1000)
    get_settings.cache_clear()
    api.post("/claims/c1/approve")
    api.drain()
    assert api.claim("c1")["status"] == "failed"
    assert api.purchase("p1")["status"] == "drop_detected"
    error = api.get("/activity?limit=1").json()[0]
    assert error["kind"] == "error" and "Couldn't submit the Best Buy claim" in error["message"]
    assert error["screenshot_url"].endswith(".png")

    # The retailer's page is back: approving a failed claim tries again.
    monkeypatch.setenv("RETAILER_CLAIM_URL", working_form)
    get_settings.cache_clear()
    assert api.post("/claims/c1/approve").json()["status"] == "submitting"
    api.drain()
    assert api.claim("c1")["status"] == "refund_received"
    assert api.purchase("p1")["status"] == "claimed"


def test_bot_crash_with_no_message_still_fails_the_claim(api, monkeypatch):
    async def crash(*args, **kwargs):
        raise NotImplementedError  # what Playwright raises when the event loop can't start a browser

    monkeypatch.setattr(claim_bot, "submit", crash)
    api.post("/claims/c1/approve")
    api.drain()
    assert api.claim("c1")["status"] == "failed"  # not left in "submitting"
    assert "NotImplementedError" in api.get("/activity?limit=1").json()[0]["message"]


def test_form_that_refuses_a_field_fails_the_claim_at_once_and_says_which(api):
    body = {"retailer": "Best Buy", "product_name": "Gift with no receipt", "price_paid_cents": 20000,
            "purchased_at": NOW.isoformat()}  # no order number, and the store's form requires one
    purchase = api.post("/purchases", json=body).json()
    api.post("/demo/price-drop", json={"purchase_id": purchase["id"]})
    api.drain()
    claim = api.get("/claims").json()[0]
    assert claim["purchase_id"] == purchase["id"]
    started = time.monotonic()
    api.post(f"/claims/{claim['id']}/approve")
    api.drain()
    assert time.monotonic() - started < 8  # no 10-second wait for a confirmation that can't come
    assert api.claim(claim["id"])["status"] == "failed"
    message = api.get("/activity?limit=1").json()[0]["message"]
    assert "the form rejected a field (Order number" in message


def test_reject_stops_the_claim_until_the_price_falls_further(api):
    api.post("/demo/price-drop", json={"purchase_id": "p2", "new_price_cents": 11999})
    api.drain()
    claim = api.get("/claims").json()[0]
    assert api.post(f"/claims/{claim['id']}/reject").json()["status"] == "rejected"
    assert api.purchase("p2")["status"] == "drop_detected"
    assert api.post(f"/claims/{claim['id']}/approve").json()["status"] == "rejected"  # no way back in

    api.post("/demo/jobs/poll_prices")  # same price: nothing new
    api.drain()
    assert len([c for c in api.get("/claims").json() if c["purchase_id"] == "p2"]) == 1

    api.post("/demo/price-drop", json={"purchase_id": "p2", "new_price_cents": 9999})  # falls further
    api.drain()
    latest = api.get("/claims").json()[0]
    assert latest["purchase_id"] == "p2" and latest["status"] == "awaiting_approval" and latest["refund_cents"] == 3000

    assert api.post("/claims/c2/reject").status_code == 409  # already refunded


def test_drop_at_a_retailer_without_a_policy_is_not_claimed(api):
    body = {
        "retailer": "Shady Shop", "product_name": "Mystery Gadget", "price_paid_cents": 5000,
        "purchased_at": (NOW - timedelta(days=1)).isoformat(),
    }
    created = api.post("/purchases", json=body)
    assert created.status_code == 200
    purchase = created.json()
    assert purchase["source"] == "manual" and purchase["status"] == "monitoring"
    assert purchase["product_id"] == "shadyshop:mystery-gadget" and purchase["adjustment_window_ends"] is None
    assert api.post("/purchases", json={**body, "price_paid_cents": 0}).status_code == 422

    api.post("/demo/price-drop", json={"purchase_id": purchase["id"], "percent": 20})
    api.drain()
    assert api.purchase(purchase["id"])["status"] == "drop_detected"
    assert not [c for c in api.get("/claims").json() if c["purchase_id"] == purchase["id"]]
    event = api.get("/activity?limit=1").json()[0]
    assert event["kind"] == "eligibility_checked" and event["message"].startswith("Not eligible")


def test_closed_window_expires_the_purchase(api):
    purchase = api.call(api.store.get_purchase, "p2")
    api.call(api.store.save_purchase, purchase.model_copy(update={"adjustment_window_ends": NOW - timedelta(hours=1)}))
    api.post("/demo/jobs/poll_prices")
    api.drain()
    assert api.purchase("p2")["status"] == "expired"
    assert api.post("/demo/price-drop", json={"purchase_id": "p2"}).status_code == 409


def test_reset_restores_the_seed_and_cancels_pending_jobs(api, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("DEMO_REFUND_DELAY_SECONDS", "60")  # the refund is queued but not paid yet
    get_settings.cache_clear()
    api.post("/purchases/scan")
    api.post("/demo/price-drop")
    api.post("/claims/c1/approve")
    deadline = time.monotonic() + 30
    while api.claim("c1")["status"] != "submitted" and time.monotonic() < deadline:
        time.sleep(0.1)
    assert api.claim("c1")["status"] == "submitted"

    reset = api.post("/demo/reset").json()
    assert reset == {"status": "reset", "purchases": 6, "claims": 4}
    api.drain()  # returns at once: the queued refund was cancelled, not left to hit the new state
    assert api.claim("c1")["status"] == "awaiting_approval"
    assert api.purchase("p2")["status"] == "monitoring"
    assert len(api.get("/activity").json()) == 9
    assert api.get("/savings").json()["total_recovered_cents"] == 8250


def test_demo_endpoints_can_be_switched_off(api, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    assert api.post("/demo/reset").status_code == 404
    assert api.post("/demo/price-drop").status_code == 404
    assert api.get("/purchases").status_code == 200
