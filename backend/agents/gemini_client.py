"""Thin wrapper around the Gemini API so every agent shares one client + structured-output helper."""

from __future__ import annotations

import asyncio
import logging
import time
from functools import lru_cache
from typing import Callable, TypeVar

from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# A mock is either a ready-made model or a zero-arg factory returning one.
Mock = BaseModel | Callable[[], BaseModel]


class GeminiUnavailable(RuntimeError):
    """Gemini can't be called (mock mode / no key) and the caller gave no mock fallback."""


@lru_cache
def _client():
    from google import genai  # imported lazily so mock mode works without the SDK configured

    return genai.Client(api_key=get_settings().gemini_api_key)


def _use_mock() -> bool:
    s = get_settings()
    return s.mock_mode or not s.gemini_api_key


def _resolve_mock(mock: Mock | None, schema: type[T]) -> T:
    if mock is None:
        raise GeminiUnavailable(
            "Gemini is disabled (MOCK_MODE=true or GEMINI_API_KEY unset) and no mock was provided "
            f"for {schema.__name__}."
        )
    result = mock() if callable(mock) else mock
    return schema.model_validate(result.model_dump())


async def generate_structured(
    prompt: str,
    schema: type[T],
    *,
    images: list[bytes] | None = None,
    image_mime_type: str = "image/jpeg",
    mock: Mock | None = None,
    temperature: float = 0.0,
) -> T:
    """Call Gemini and parse the response into `schema` (JSON mode + response_schema).

    Models are tried in order: GEMINI_MODEL, then each of GEMINI_FALLBACK_MODELS. A model that
    errors or takes longer than GEMINI_ATTEMPT_TIMEOUT_SECONDS is skipped, and the whole call
    gives up after GEMINI_TIMEOUT_SECONDS, so one overloaded model can't stall a demo.

    Mock fallback: when MOCK_MODE is on or no API key is set, returns `mock` (a model or a
    factory) instead of calling the network. If every model fails and `mock` was provided,
    falls back to it; without a mock the last error is raised.
    """
    if _use_mock():
        return _resolve_mock(mock, schema)

    from google.genai import types

    settings = get_settings()
    contents: list = [prompt]
    for img in images or []:
        contents.append(types.Part.from_bytes(data=img, mime_type=image_mime_type))
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        temperature=temperature,
        # No silent SDK retries: a failing model should hand over to the next one straight away.
        http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
    )

    deadline = time.monotonic() + settings.gemini_timeout_seconds
    last_error: Exception = TimeoutError("no time left to call Gemini")
    for model in model_chain():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            resp = await asyncio.wait_for(
                _client().aio.models.generate_content(model=model, contents=contents, config=config),
                timeout=min(settings.gemini_attempt_timeout_seconds, remaining),
            )
            parsed = getattr(resp, "parsed", None)
            return parsed if isinstance(parsed, schema) else schema.model_validate_json(resp.text)
        except Exception as exc:
            last_error = exc
            logger.warning("Gemini model %s failed (%s: %s)", model, type(exc).__name__, (str(exc) or "timed out")[:160])

    if mock is None:
        raise last_error
    logger.warning("Every Gemini model failed; using MOCK for %s", schema.__name__)
    return _resolve_mock(mock, schema)


def model_chain() -> list[str]:
    """The primary model followed by the fallbacks, without duplicates."""
    settings = get_settings()
    names = [settings.gemini_model, *settings.gemini_fallback_models.split(",")]
    return list(dict.fromkeys(name.strip() for name in names if name.strip()))
