"""Thin wrapper around the Gemini API so every agent shares one client + structured-output helper."""

from pydantic import BaseModel

from app.config import get_settings

settings = get_settings()


def generate_structured(prompt: str, schema: type[BaseModel], *, images: list[bytes] | None = None) -> BaseModel:
    """Call Gemini and parse the response into `schema` (use JSON mode / response_schema).

    TODO(L3):
      from google import genai
      client = genai.Client(api_key=settings.gemini_api_key)
      resp = client.models.generate_content(
          model=settings.gemini_model,
          contents=[...],
          config={"response_mime_type": "application/json", "response_schema": schema},
      )
      return schema.model_validate_json(resp.text)
    """
    raise NotImplementedError
