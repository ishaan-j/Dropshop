"""Run: cd backend && python -m pytest agents/test_sentient.py (offline)."""

import asyncio
import os
import time

import pytest

from agents import sentient
from app.config import get_settings


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setenv("SENTIENT_OS_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_fixture_fallback_discovers_all_purchases():
    ps = asyncio.run(sentient.discover_purchases("2026-01-01T00:00:00Z"))
    assert {p.retailer for p in ps} == {"Best Buy", "Target", "Amazon"}
    assert len(ps) == 4  # Target receipt has two items


def test_sentient_reads_recent_receipt_files(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("SENTIENT_OS_ENABLED", "true")
    monkeypatch.setenv("SENTIENT_KNOWLEDGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    src = (sentient.FIXTURES_DIR / "bestbuy_receipt.txt").read_text(encoding="utf-8")
    new, old, other = tmp_path / "new.md", tmp_path / "old.md", tmp_path / "notes.md"
    new.write_text(src); old.write_text(src); other.write_text("grocery list: milk")
    os.utime(old, (time.time() - 10 * 86400,) * 2)
    texts = asyncio.run(sentient.fetch_recent_receipts("2000-01-01T00:00:00Z"))
    assert len(texts) == 2
    since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 86400))
    assert len(asyncio.run(sentient.fetch_recent_receipts(since))) == 1


def test_sentient_failure_falls_back(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("SENTIENT_OS_ENABLED", "true")
    monkeypatch.setenv("SENTIENT_KNOWLEDGE_DIR", "/definitely/not/here")
    get_settings.cache_clear()
    assert len(asyncio.run(sentient.fetch_recent_receipts("2026-01-01T00:00:00Z"))) == 3
