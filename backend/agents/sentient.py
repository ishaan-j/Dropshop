"""Sentient OS integration: discover purchases from the user's on-device context.

Heads-up: Sentient OS is an on-device Mac app (open source, AGPL-3.0) that reads mail/messages/files
locally overnight. It is not a hosted API. Before building, confirm with the sponsor what counts as an
integration (e.g. reading its local Markdown knowledge base, or contributing a Dropshot hook upstream).

Always keep the fallback path working: sample receipt emails in fixtures/ (or Gmail) → receipt_extractor.

UNCONFIRMED: the Sentient path below assumes its knowledge base is a folder of Markdown/text files
(SENTIENT_KNOWLEDGE_DIR). Adjust once the sponsor confirms the real format.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from agents import receipt_extractor
from app.config import get_settings
from app.models import PurchaseCreate

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
_RECEIPT_GLOB = "*_receipt.txt"
_SENTIENT_SUFFIXES = {".md", ".txt", ".eml"}
_RECEIPT_HINTS = ("order", "receipt", "purchase", "invoice")


def _fixture_receipts() -> list[str]:
    return [p.read_text(encoding="utf-8") for p in sorted(FIXTURES_DIR.glob(_RECEIPT_GLOB))]


def _sentient_receipts(since: datetime) -> list[str]:
    """Receipt-looking files in Sentient OS's local knowledge base modified since `since`."""
    root = Path(get_settings().sentient_knowledge_dir).expanduser()
    if not root.is_dir():
        raise FileNotFoundError(f"Sentient knowledge dir not found: {root}")
    texts = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in _SENTIENT_SUFFIXES or not path.is_file():
            continue
        if datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc) < since:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(h in text[:2000].lower() for h in _RECEIPT_HINTS):
            texts.append(text)
    return texts


def _parse_since(since_iso: str) -> datetime:
    dt = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def fetch_recent_receipts(since_iso: str) -> list[str]:
    """Return raw receipt texts found since `since_iso`.

    Sentient OS enabled → read its local knowledge base; if that fails or the setting is off,
    fall back to the fixture receipts (which ignore `since_iso`, so the demo always has data).
    """
    settings = get_settings()
    if settings.sentient_os_enabled and not settings.mock_mode:
        try:
            return _sentient_receipts(_parse_since(since_iso))
        except Exception:
            logger.exception("Sentient OS read failed; using fixture receipts")
    return _fixture_receipts()


async def discover_purchases(since_iso: str) -> list[PurchaseCreate]:
    """fetch_recent_receipts → receipt_extractor → flat list of purchases (source is set by L2).

    One unparseable receipt is skipped, not fatal.
    """
    purchases: list[PurchaseCreate] = []
    for raw in await fetch_recent_receipts(since_iso):
        try:
            purchases.extend((await receipt_extractor.extract(raw)).items)
        except Exception:
            logger.exception("Skipping a receipt that failed extraction")
    return purchases
