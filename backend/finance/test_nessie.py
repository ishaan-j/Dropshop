"""Run: cd backend && python -m pytest finance/test_nessie.py  (offline; Nessie's HTTP API is faked)."""

import asyncio
import json

import httpx
import pytest

from app.config import get_settings
from finance import nessie


@pytest.fixture
def fake_nessie(monkeypatch):
    """Route the client's HTTP calls to an in-memory Nessie. Yields the list of requests it saw."""
    monkeypatch.setenv("NESSIE_API_KEY", "test-key")
    monkeypatch.setenv("NESSIE_BASE_URL", "https://nessie.test")
    get_settings.cache_clear()
    seen: list[httpx.Request] = []
    deposits: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.url.params["key"] == "test-key"
        path, body = request.url.path, json.loads(request.content or b"{}")
        if request.method == "POST" and path == "/customers":
            return httpx.Response(201, json={"code": 201, "objectCreated": {"_id": "cust1", **body}})
        if request.method == "POST" and path == "/customers/cust1/accounts":
            return httpx.Response(201, json={"code": 201, "objectCreated": {"_id": "acct1", **body}})
        if request.method == "POST" and path == "/accounts/acct1/deposits":
            created = {"_id": f"dep{len(deposits) + 1}", "type": "deposit", **body}
            deposits.append(created)
            return httpx.Response(201, json={"code": 201, "message": "Created deposit", "objectCreated": created})
        if request.method == "GET" and path == "/accounts/acct1/deposits":
            return httpx.Response(200, json=deposits)
        if request.method == "POST" and path == "/accounts/acct1/purchases":
            return httpx.Response(201, json={"code": 201, "objectCreated": {"_id": "pur1", **body}})
        return httpx.Response(404, json={"code": 404, "message": "Invalid ID"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(nessie.httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs))
    yield seen
    get_settings.cache_clear()


def test_refund_is_a_deposit_in_dollars_and_can_be_read_back(fake_nessie):
    async def scenario():
        deposit = await nessie.simulate_refund("acct1", 1950, "PRICE ADJUSTMENT Target")
        assert deposit["_id"] == "dep1" and deposit["amount"] == 19.5  # cents in, dollars on the wire
        assert deposit["description"] == "PRICE ADJUSTMENT Target" and deposit["medium"] == "balance"
        assert [d["_id"] for d in await nessie.list_deposits("acct1")] == ["dep1"]

    asyncio.run(scenario())


def test_customer_account_and_purchase_creation(fake_nessie):
    async def scenario():
        ids = await nessie.create_demo_customer_and_account(balance_cents=500_000)
        assert ids == {"customer_id": "cust1", "account_id": "acct1"}
        account_body = json.loads(fake_nessie[1].content)
        assert account_body["type"] == "Checking" and account_body["balance"] == 5000
        purchase = await nessie.create_purchase("acct1", "merch1", 39999, "Best Buy Sony WH-1000XM6")
        assert purchase["amount"] == 399.99 and purchase["merchant_id"] == "merch1"

    asyncio.run(scenario())


def test_errors_name_the_call_but_never_the_key(fake_nessie):
    async def scenario():
        with pytest.raises(nessie.NessieError) as error:
            await nessie.list_deposits("missing-account")
        assert "404" in str(error.value) and "/accounts/missing-account/deposits" in str(error.value)
        assert "test-key" not in str(error.value)

    asyncio.run(scenario())


def test_missing_key_fails_before_any_request(monkeypatch):
    monkeypatch.setenv("NESSIE_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(nessie.NessieError, match="NESSIE_API_KEY"):
        asyncio.run(nessie.list_purchases("acct1"))
    get_settings.cache_clear()
