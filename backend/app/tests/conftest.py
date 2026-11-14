"""Layer 2 tests. Run from backend/:  python -m pytest app

Hermetic: every test runs in mock mode against the in-memory store, whatever is in your .env.
The claim bot fills a local HTML form, so the tests that submit a claim need Chromium
(`playwright install chromium`) but no network and no frontend.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import finance_gateway, jobs, store
from app.config import get_settings
from app.workers import tasks

CLAIM_FORM = Path(__file__).resolve().parents[2] / "agents" / "fixtures" / "mock_claim_form.html"


@pytest.fixture(autouse=True)
def demo_env(monkeypatch, tmp_path):
    env = {
        "MOCK_MODE": "true",
        "DATA_BACKEND": "auto",
        "DEMO_MODE": "true",
        "DEMO_REFUND_DELAY_SECONDS": "0",
        "SCHEDULER_ENABLED": "false",
        "SENTIENT_OS_ENABLED": "false",
        "PLAYWRIGHT_HEADLESS": "true",
        "RETAILER_CLAIM_URL": CLAIM_FORM.as_uri(),
        "API_BASE_URL": "http://testserver",
        "REDIS_URL": "redis://127.0.0.1:6399",  # nothing listens here
        "NESSIE_ACCOUNT_ID": "test-account",
        "NESSIE_API_KEY": "test-key",  # never the real key from .env
        "SOLANA_KEYPAIR_PATH": str(tmp_path / "no-keypair.json"),  # never the real devnet wallet
        "SOLANA_PROGRAM_ID": "",
        "AUTOMATION_TOKEN": "",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(tasks, "SCREENSHOT_ROOT", tmp_path / "screenshots")
    monkeypatch.setattr(jobs, "_pool", None)
    monkeypatch.setattr(jobs, "_redis_down_until", 0.0)
    get_settings.cache_clear()
    store.set_store(None)
    finance_gateway.reset_fallbacks()
    finance_gateway.reset_simulation()
    tasks._evaluating.clear()
    tasks._vault_failures.clear()
    yield
    store.set_store(None)
    get_settings.cache_clear()


class Api:
    """A running app plus helpers to wait for its background jobs and reach its store."""

    def __init__(self, client: TestClient):
        self.client = client
        self.get, self.post = client.get, client.post

    def drain(self) -> None:
        self.client.portal.call(jobs.drain)

    def call(self, fn, *args):
        """Run an async function on the app's event loop."""
        return self.client.portal.call(fn, *args)

    @property
    def store(self):
        return store.get_store()

    def purchase(self, purchase_id: str) -> dict:
        return self.get(f"/purchases/{purchase_id}").json()

    def claim(self, claim_id: str) -> dict:
        return next(c for c in self.get("/claims").json() if c["id"] == claim_id)

    def kinds(self, limit: int = 200) -> list[str]:
        return [e["kind"] for e in self.get(f"/activity?limit={limit}").json()]


@pytest.fixture
def api():
    from app.main import create_app

    with TestClient(create_app()) as client:
        yield Api(client)
