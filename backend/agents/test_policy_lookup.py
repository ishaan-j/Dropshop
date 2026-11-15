"""Run: cd backend && python -m pytest agents/test_policy_lookup.py (offline)."""

import asyncio

from agents.policy_reader import combine_policy_findings, get_policy, is_unset_policy, parse_policy_json
from app.config import get_settings
from app.models import RetailerPolicy


def _policy(days, url="https://example.com/policy"):
    return RetailerPolicy(
        retailer="Shop", policy_url=url, window_days=days, conditions=["Same item."], summary="Adjusts within the window."
    )


def test_parse_policy_json_accepts_fenced_json():
    text = '```json\n{"window_days": "14", "policy_url": "https://shop.example/help", "conditions": "nope", "summary": "14 days."}\n```'
    policy = parse_policy_json("Shop", text)
    assert policy is not None
    assert policy.window_days == 14 and policy.conditions == [] and policy.policy_url.startswith("https://")


def test_a_published_window_from_either_bot_is_kept():
    found = combine_policy_findings("Shop", [("Gemini", _policy(30)), ("Grok", None)], failures=0)
    assert found.window_days == 30 and found.policy_url == "https://example.com/policy"
    assert any("Gemini" in note for note in found.conditions)


def test_disagreement_uses_the_shorter_window():
    found = combine_policy_findings(
        "Shop", [("Gemini", _policy(30)), ("Grok", _policy(14, "https://shop.example/adjust"))], failures=0
    )
    assert found.window_days == 14
    assert any("30-day" in note for note in found.conditions)


def test_a_window_without_a_page_is_ignored():
    invented = _policy(30, url="")
    found = combine_policy_findings("Shop", [("Gemini", invented), ("Grok", None)], failures=0)
    assert found.window_days is None
    assert not is_unset_policy(found)
    assert "no published" in found.summary


def test_total_failure_stays_retryable():
    found = combine_policy_findings("Shop", [], failures=2)
    assert is_unset_policy(found)


def test_a_window_written_only_in_the_summary_still_counts():
    from agents.policy_reader import stated_window_days

    policy = RetailerPolicy(
        retailer="Apple",
        policy_url="https://www.apple.com/legal/sales-support/sales-policies/retail_us.html",
        window_days=None,
        conditions=["Request the refund within 14 calendar days of the price change."],
        summary="Apple credits the difference when it lowers the price within 14 calendar days of receipt.",
    )
    assert stated_window_days(policy) == 14


def test_mock_mode_does_not_look_up_an_unknown_retailer(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    get_settings.cache_clear()
    policy = asyncio.run(get_policy("Shady Shop"))
    get_settings.cache_clear()
    assert is_unset_policy(policy)
