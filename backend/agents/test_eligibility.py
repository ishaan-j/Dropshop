"""Run: cd backend && python -m pytest agents/test_eligibility.py  (offline, MOCK_MODE)."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from agents.eligibility import check
from agents.policy_reader import get_policy
from app.config import get_settings
from app.models import Purchase

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    get_settings.cache_clear()


def purchase(retailer="Best Buy", paid=39999, days_ago=6, window_ends=None):
    return Purchase(
        id="p", user_id="u", retailer=retailer, product_id="x", product_name="Thing",
        price_paid_cents=paid, purchased_at=NOW - timedelta(days=days_ago),
        adjustment_window_ends=window_ends,
    )


def run(p, price):
    policy = asyncio.run(get_policy(p.retailer))
    return asyncio.run(check(p, price, policy, now=NOW))


def test_eligible_drop_inside_window():
    r = run(purchase(), 34999)
    assert r.eligible and r.refund_cents == 5000


def test_price_not_lower():
    assert not run(purchase(), 39999).eligible
    assert not run(purchase(), 41000).eligible


def test_outside_window():
    r = run(purchase(retailer="Amazon", paid=8999, days_ago=20), 7999)
    assert not r.eligible and r.refund_cents == 0 and "window" in r.reason


def test_stored_window_end_wins():
    p = purchase(days_ago=30, window_ends=NOW + timedelta(days=1))
    assert run(p, 30000).eligible


def test_unknown_retailer():
    r = run(purchase(retailer="Shady Shop"), 100)
    assert not r.eligible and "no known" in r.reason
