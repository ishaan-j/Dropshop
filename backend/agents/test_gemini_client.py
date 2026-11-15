"""Run: cd backend && python -m pytest agents/test_gemini_client.py  (offline; the Gemini SDK is faked)."""

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from agents import gemini_client
from app.config import get_settings


class Answer(BaseModel):
    value: int


class FakeGemini:
    """Stands in for the SDK client. `behaviour` maps a model name to a result, an error or a delay,
    or to a list of those: one per call, the last one repeating."""

    def __init__(self, behaviour):
        self.behaviour, self.calls = behaviour, []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self.generate_content))

    async def generate_content(self, *, model, contents, config):
        self.calls.append(model)
        outcome = self.behaviour[model]
        if isinstance(outcome, list):
            outcome = outcome.pop(0) if len(outcome) > 1 else outcome[0]
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, float):
            await asyncio.sleep(outcome)
        return SimpleNamespace(parsed=None, text='{"value": %d}' % (outcome if isinstance(outcome, int) else 0))


@pytest.fixture
def live(monkeypatch):
    env = {
        "MOCK_MODE": "false", "GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "primary",
        "GEMINI_FALLBACK_MODELS": "second, third", "GEMINI_ATTEMPT_TIMEOUT_SECONDS": "0.2", "GEMINI_TIMEOUT_SECONDS": "1",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(gemini_client, "ROUND_PAUSE_SECONDS", 0.0)
    get_settings.cache_clear()

    def install(behaviour):
        fake = FakeGemini(behaviour)
        monkeypatch.setattr(gemini_client, "_client", lambda: fake)
        return fake

    yield install
    get_settings.cache_clear()


def ask(mock=None):
    return asyncio.run(gemini_client.generate_structured("question", Answer, mock=mock))


def test_primary_model_is_used_when_it_works(live):
    fake = live({"primary": 1, "second": 2, "third": 3})
    assert ask().value == 1 and fake.calls == ["primary"]
    assert gemini_client.model_chain() == ["primary", "second", "third"]


def test_failing_and_slow_models_hand_over_to_the_next(live):
    fake = live({"primary": RuntimeError("503 overloaded"), "second": 5.0, "third": 3})  # second is too slow
    assert ask().value == 3 and fake.calls == ["primary", "second", "third"]


def test_all_models_failing_uses_the_mock_or_raises(live):
    fake = live({"primary": RuntimeError("503"), "second": RuntimeError("503"), "third": RuntimeError("quota")})
    assert ask(mock=Answer(value=42)).value == 42
    assert fake.calls == ["primary", "second", "third"] * 2  # the chain is tried twice, then no more
    with pytest.raises(RuntimeError, match="quota"):
        ask()


def test_a_model_that_failed_briefly_is_asked_again(live):
    # What Gemini did at the event: a 503 from one model and a hung request on the other, both passing within seconds.
    fake = live({"primary": [RuntimeError("503 high demand"), 1], "second": 5.0, "third": RuntimeError("503")})
    assert ask().value == 1 and fake.calls == ["primary", "second", "third", "primary"]


def test_a_model_that_rejects_the_request_is_not_asked_again(live):
    class Rejected(Exception):
        code = 404  # like the SDK's ClientError for an unknown model name

    fake = live({"primary": Rejected("no such model"), "second": RuntimeError("503"), "third": RuntimeError("503")})
    assert ask(mock=Answer(value=42)).value == 42
    assert fake.calls == ["primary", "second", "third", "second", "third"]


def test_mock_mode_never_calls_gemini(live, monkeypatch):
    fake = live({"primary": 1})
    monkeypatch.setenv("MOCK_MODE", "true")
    get_settings.cache_clear()
    assert ask(mock=lambda: Answer(value=7)).value == 7 and fake.calls == []
    with pytest.raises(gemini_client.GeminiUnavailable):
        ask()
