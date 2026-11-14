"""Turn a raw receipt (email HTML/text or a photo) into structured purchases."""

from app.models import ExtractedReceipt


async def extract(raw_text: str | None = None, image: bytes | None = None) -> ExtractedReceipt:
    """TODO(L3): prompt Gemini with prompts/receipt_extraction.md → ExtractedReceipt."""
    raise NotImplementedError
