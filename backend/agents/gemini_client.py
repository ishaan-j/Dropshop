"""Thin wrapper around the Gemini API so every agent shares one client + structured-output helper."""

from __future__ import annotations

import asyncio
import logging
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

    Mock fallback: when MOCK_MODE is on or no API key is set, returns `mock` (a model or a
    factory) instead of calling the network. If the live call fails and `mock` was provided,
    falls back to it so the demo never dies on an API hiccup.
    """
    if _use_mock():
        return _resolve_mock(mock, schema)

    from google.genai import types

    contents: list = [prompt]
    for img in images or []:
        contents.append(types.Part.from_bytes(data=img, mime_type=image_mime_type))

    try:
        # The SDK retries overloaded (503) calls silently, so cap the total wait.
        resp = await asyncio.wait_for(
            _client().aio.models.generate_content(
                model=get_settings().gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=temperature,
                ),
            ),
            timeout=get_settings().gemini_timeout_seconds,
        )
        parsed = getattr(resp, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        return schema.model_validate_json(resp.text)
    except Exception as exc:
        if mock is None:
            raise
        logger.warning(
            "Gemini call failed (%s: %s); using MOCK for %s",
            type(exc).__name__, (str(exc) or "timed out")[:160], schema.__name__,
        )
        return _resolve_mock(mock, schema)
