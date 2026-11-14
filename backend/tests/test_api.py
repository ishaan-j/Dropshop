from fastapi.testclient import TestClient

from app.main import app
from data.repository import repo


def _client():
    repo.reset_memory()
    return TestClient(app)


def _auth(client: TestClient) -> dict:
    response = client.post("/auth/session", json={"display_name": "Tester"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_health_and_unauthenticated_data_is_rejected():
    with _client() as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/purchases").status_code == 401


def test_demo_scenario_is_labeled_and_not_all_eligible():
    with _client() as client:
        headers = _auth(client)
        response = client.post("/demo/scenario", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["data_origin"] == "demo"
        assert "not your Gmail" in body["note"]
        by_name = {row["product_name"]: row for row in body["purchases"]}
        assert by_name["Linen Weekender Bag"]["eligibility"] == "eligible"
        assert by_name["Linen Weekender Bag"]["data_origin"] == "demo"
        assert by_name["Linen Weekender Bag"]["price_source"] == "demo_catalog"
        assert by_name["Wool Scarf"]["eligibility"] == "ineligible"
        assert by_name["Ceramic Table Lamp"]["status"] == "expired"
        assert len(body["claims"]) == 1
        claim = body["claims"][0]
        assert claim["status"] == "awaiting_approval"
        assert "not a promise" in claim["explanation"]
        assert client.get("/purchases", headers=_auth(client)).json() == []


def test_scan_does_not_silently_load_sample_mail():
    with _client() as client:
        response = client.post("/purchases/scan", headers=_auth(client))
        assert response.status_code == 409
        assert "demo scenario" in response.json()["detail"].lower()


def test_approve_without_browser_does_not_mark_submitted():
    with _client() as client:
        headers = _auth(client)
        claim_id = client.post("/demo/scenario", headers=headers).json()["claims"][0]["id"]
        response = client.post(f"/claims/{claim_id}/approve", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["submitted"] is False
        assert body["claim"]["status"] == "awaiting_approval"
        again = client.post(f"/claims/{claim_id}/approve", headers=headers)
        assert again.json()["submitted"] is False


def test_demo_submission_is_rejected_until_a_claim_is_submitting():
    with _client() as client:
        headers = _auth(client)
        purchase = client.post("/demo/scenario", headers=headers).json()["purchases"]
        bag = next(row for row in purchase if row["product_name"] == "Linen Weekender Bag")
        response = client.post(
            "/demo/retailer/submissions",
            json={
                "order_number": bag["order_number"],
                "product_name": bag["product_name"],
                "price_paid": "128.00",
                "current_price": "99.00",
                "refund_amount": "29.00",
                "message": "please",
            },
        )
        assert response.json()["accepted"] is False


def test_fake_signature_is_not_stored():
    with _client() as client:
        headers = _auth(client)
        response = client.post(
            "/vault/confirm",
            headers=headers,
            json={"signature": "not-a-real-signature", "intended_cents": 0},
        )
        assert response.status_code in {400, 409}
        assert client.get("/vault", headers=headers).json()["allocations"] == []


def test_demo_refund_and_allocation_stay_labeled():
    with _client() as client:
        headers = _auth(client)
        claim = client.post("/demo/scenario", headers=headers).json()["claims"][0]
        denied = client.post(f"/refunds/{claim['id']}/demo", headers=headers)
        assert denied.status_code == 409
        client.app  # keep reference
        # Force the claim into submitted without pretending a browser ran, through the store.
        from app.models import Claim

        stored = repo.claims[claim["id"]]
        stored.status = "submitted"
        repo.claims[claim["id"]] = Claim.model_validate(stored.model_dump())
        refund = client.post(f"/refunds/{claim['id']}/demo", headers=headers)
        assert refund.status_code == 200, refund.text
        assert refund.json()["data_origin"] == "demo"
        assert refund.json()["external_id"] is None
        allocation = client.post("/vault/demo-allocation", headers=headers, json={"amount_cents": 1000})
        assert allocation.status_code == 200, allocation.text
        assert allocation.json()["signature"] is None
        assert allocation.json()["confirmed"] is False
        board = client.get("/dashboard", headers=headers).json()
        assert board["includes_demo_data"] is True
        assert board["total_recovered_cents"] == claim["refund_cents"]
        too_much = client.post("/vault/demo-allocation", headers=headers, json={"amount_cents": 10_000_00})
        assert too_much.status_code == 409


def test_manual_purchase_has_no_invented_price():
    with _client() as client:
        headers = _auth(client)
        response = client.post(
            "/purchases",
            headers=headers,
            json={
                "retailer": "Corner Store",
                "product_name": "Notebook",
                "price_paid_cents": 1200,
                "purchased_at": "2026-11-01T00:00:00Z",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["current_price_cents"] is None
        assert body["eligibility"] == "unknown"
        assert body["source"] == "manual"
