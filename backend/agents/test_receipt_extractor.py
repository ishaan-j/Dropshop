"""Run: cd backend && python -m pytest agents/test_receipt_extractor.py  (offline, uses the mock parser)."""

import asyncio
from pathlib import Path

import pytest

from agents.receipt_extractor import extract

FIXTURES = Path(__file__).parent / "fixtures"

# fixture -> (retailer, order_number, [(product, cents)])
EXPECTED = {
    "bestbuy_receipt.txt": ("Best Buy", "BBY01-80612", [("Sony WH-1000XM6", 39999)]),
    "bestbuy_airpods_receipt.txt": ("Best Buy", "BBY01-80733", [("Apple AirPods Pro 3", 24999)]),
    "target_receipt.txt": (
        "Target", "912-0045-7731", [("Ninja Air Fryer 6qt", 12999), ("Hefty Trash Bags 40ct", 949)]
    ),
    "amazon_receipt.txt": ("Amazon", "112-7348291-5502611", [("Anker 737 Power Bank", 8999)]),
}


@pytest.mark.parametrize("name", EXPECTED)
def test_extract_fixture(name, monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    from app.config import get_settings

    get_settings.cache_clear()
    retailer, order, items = EXPECTED[name]
    r = asyncio.run(extract((FIXTURES / name).read_text(encoding="utf-8")))
    assert r.retailer == retailer
    assert r.order_number == order
    assert r.purchased_at is not None
    assert len(r.items) == len(items)
    for got, (name_part, cents) in zip(r.items, items):
        assert name_part in got.product_name
        assert got.price_paid_cents == cents
