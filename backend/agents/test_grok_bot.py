"""Run: cd backend && python -m pytest agents/test_grok_bot.py (offline; xAI + Gemini mocked)."""

import asyncio
import json

import httpx
import pytest

from agents import grok_bot
from agents.policy_reader import POLICIES
from app.config import get_settings

STORED = POLICIES["best buy"]


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("XAI_API_KEY", "test")
    monkeypatch.setenv("GEMINI_API_KEY", "")  # Gemini falls back to the hardcoded policy
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def client_returning(content: dict | None = None, status=200):
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["authorization"] == "Bearer test"
        body = {"choices": [{"message": {"content": json.dumps(content)}}]}
        return httpx.Response(status, json=body)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def run(client, **kw):
    return asyncio.run(grok_bot.watch_policy(STORED, page_text="page text", client=client, **kw))


def test_disabled_without_key(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    get_settings.cache_clear()
    r = asyncio.run(grok_bot.watch_policy(STORED, page_text="x"))
    assert not r.changed and r.reviewed_by == "none" and r.policy == STORED


def test_no_change(live):
    r = run(client_returning({"changed": False, "summary": "Same 15-day window."}))
    assert not r.changed and r.reviewed_by == "grok" and r.policy == STORED


def test_change_detected(live):
    r = run(client_returning({"changed": True, "summary": "Window cut.", "user_impact": "15 -> 14 days"}))
    assert r.changed and "15 -> 14 days" in r.note and r.policy.retailer == "Best Buy"


def test_api_failure_keeps_stored_policy(live):
    r = run(client_returning({}, status=500))
    assert not r.changed and r.policy == STORED and "failed" in r.note


def test_change_with_failed_reextraction_is_flagged(live, monkeypatch):
    async def boom(*a, **k):
        raise TimeoutError()
    monkeypatch.setattr(grok_bot, "summarize_policy_text", boom)
    r = run(client_returning({"changed": True, "summary": "Window cut."}))
    assert r.changed and r.policy == STORED and "review manually" in r.note
