"""Sentient OS integration: discover purchases from the user's on-device context.

Sentient OS is an on-device Mac app (open source, AGPL-3.0; Apple silicon, macOS 15.4+) that reads
mail, messages and files locally overnight. It is not a hosted API. Per its README, what it learns
is "a folder of ordinary Markdown files at `~/Sentient OS - Knowledge Base/`" and "local tools can
read the Markdown folder directly", which is what this module does (SENTIENT_KNOWLEDGE_DIR).

Not yet verified on a real Mac: the notes are summaries ("connected notes about your people,
projects, plans and preferences"), not raw receipts, and the README doesn't describe file names or
frontmatter. So this picks up any recent note that mentions an order or receipt and lets Gemini
extract the purchases; the offline parser only understands receipt-shaped text. Still confirm
with the sponsor that reading the knowledge base counts as the integration.

Always keep the fallback path working: sample receipt emails in fixtures/ → receipt_extractor.
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
_MAX_RECEIPT_BYTES = 1_000_000


def _fixture_receipts() -> list[str]:
    return [p.read_text(encoding="utf-8") for p in sorted(FIXTURES_DIR.glob(_RECEIPT_GLOB))]


def _extra_watch_dirs() -> list[Path]:
    dirs = []
    for part in get_settings().receipt_watch_dirs.split(","):
        part = part.strip()
        if part:
            dirs.append(Path(part).expanduser())
    return dirs


def _receipts_in(root: Path, since: datetime) -> list[str]:
    """Receipt-looking .md/.txt/.eml files under `root` modified since `since`."""
    if not root.is_dir():
        return []
    texts = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in _SENTIENT_SUFFIXES or not path.is_file():
            continue
        try:
            stat = path.stat()
            if stat.st_size > _MAX_RECEIPT_BYTES:
                continue
            modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if modified < since:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if text.lstrip().startswith("{\\rtf"):  # TextEdit's .md files are RTF, not receipt text
            continue
        if any(h in text[:2000].lower() for h in _RECEIPT_HINTS):
            texts.append(text)
    return texts


def _sentient_receipts(since: datetime) -> list[str]:
    """Receipt files in the Sentient OS knowledge base, plus Desktop and Downloads."""
    root = Path(get_settings().sentient_knowledge_dir).expanduser()
    if not root.is_dir():
        raise FileNotFoundError(f"Sentient knowledge dir not found: {root}")
    texts = _receipts_in(root, since)
    seen = {root.resolve()}
    for extra in _extra_watch_dirs():
        try:
            key = extra.resolve()
        except OSError:
            key = extra
        if key in seen:
            continue
        seen.add(key)
        texts.extend(_receipts_in(extra, since))
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
