"""Run: cd backend && python -m pytest agents/test_claim_writer_and_bot.py (offline; bot test needs `playwright install chromium`)."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents import claim_bot, claim_writer
from app.config import get_settings
from app.models import Claim, EligibilityResult, Purchase

FORM = Path(__file__).parent / "fixtures" / "mock_claim_form.html"
NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)

purchase = Purchase(
    id="p1", user_id="u", retailer="Best Buy", product_id="bestbuy:1",
    product_name="Sony WH-1000XM6 Headphones", price_paid_cents=39999,
    purchased_at=NOW, order_number="BBY01-80612",
)
result = EligibilityResult(eligible=True, refund_cents=5000, reason="ok", policy_excerpt="15-day policy")
claim = Claim(id="c1", user_id="u", purchase_id="p1", retailer="Best Buy", refund_cents=5000, created_at=NOW)


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    get_settings.cache_clear()


def test_explain_and_message_offline():
    e = asyncio.run(claim_writer.explain(purchase, result))
    m = asyncio.run(claim_writer.form_message(purchase, result))
    assert "$50.00" in e and "Best Buy" in e
    assert "BBY01-80612" in m and "$399.99" in m and "$349.99" in m


def test_ineligible_rejected():
    with pytest.raises(ValueError):
        asyncio.run(claim_writer.explain(purchase, EligibilityResult(eligible=False, reason="no")))


def test_bot_submits_against_form(tmp_path):
    shots = asyncio.run(
        claim_bot.submit(claim, purchase, "please refund", claim_url=FORM.as_uri(), screenshot_dir=tmp_path)
    )
    assert [Path(s).name for s in shots] == ["01_form_loaded.png", "02_form_filled.png", "03_confirmation.png"]
    assert all(Path(s).stat().st_size > 0 for s in shots)


def test_bot_failure_keeps_screenshots(tmp_path):
    bad = tmp_path / "blank.html"
    bad.write_text("<html><body>nope</body></html>")
    claim_bot.CONFIRMATION_TIMEOUT_MS = 1000
    with pytest.raises(claim_bot.ClaimSubmissionError) as ei:
        asyncio.run(claim_bot.submit(claim, purchase, "x", claim_url=bad.as_uri(), screenshot_dir=tmp_path / "s"))
    assert ei.value.screenshots
