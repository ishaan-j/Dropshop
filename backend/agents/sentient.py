"""Sentient OS integration: discover purchases from the user's on-device context.

Heads-up: Sentient OS is an on-device Mac app (open source, AGPL-3.0) that reads mail/messages/files
locally overnight. It is not a hosted API. Before building, confirm with the sponsor what counts as an
integration (e.g. reading its local Markdown knowledge base, or contributing a Dropshot hook upstream).

Always keep the fallback path working: sample receipt emails in fixtures/ (or Gmail) → receipt_extractor.
"""

from app.config import get_settings

settings = get_settings()


async def fetch_recent_receipts(since_iso: str) -> list[str]:
    """Return raw receipt texts found since `since_iso`.

    TODO(L3): if settings.sentient_os_enabled → read from Sentient OS; else → load fixture receipts.
    """
    raise NotImplementedError
