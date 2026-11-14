"""Gemini structured output. The API key stays on the server.

SDK usage follows the Google Gen AI Python SDK:
https://googleapis.github.io/python-genai/
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.security import safe_detail


class GeminiNotConfigured(RuntimeError):
    pass


class GeminiCallError(RuntimeError):
    pass


def configured() -> bool:
    return bool(get_settings().gemini_api_key.strip())


def _generate(prompt: str, schema: type[BaseModel]) -> BaseModel:
    settings = get_settings()
    if not settings.gemini_api_key.strip():
        raise GeminiNotConfigured("Gemini API key is not configured.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise GeminiCallError("The google-genai package is not installed.") from exc
    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0,
            ),
        )
    except Exception as exc:  # noqa: BLE001 — surface a redacted provider error
        raise GeminiCallError(safe_detail(exc)) from exc
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, schema):
        return parsed
    text = getattr(response, "text", None) or ""
    if not text:
        raise GeminiCallError("Gemini returned an empty response.")
    try:
        return schema.model_validate_json(text)
    except ValidationError as exc:
        raise GeminiCallError("Gemini JSON did not match the schema.") from exc


async def generate_structured(prompt: str, schema: type[BaseModel]) -> BaseModel:
    return await asyncio.to_thread(_generate, prompt, schema)
