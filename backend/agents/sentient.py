"""Sentient OS integration.

Sentient OS keeps knowledge in ordinary Markdown at ~/Sentient OS - Knowledge Base/
(https://github.com/Sentient-OS-Labs/sentient-os). There is no cloud orchestration
SDK in that documentation. DropShop only reads that folder after the user opts in,
and only notes that look like orders. It does not pretend a local agent run is a
Sentient OS execution.
"""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings

ORDER_HINTS = ("order number:", "product id:", "order date:")


def knowledge_dir() -> Path:
    settings = get_settings()
    raw = settings.sentient_knowledge_dir.strip() or str(Path.home() / "Sentient OS - Knowledge Base")
    return Path(raw).expanduser()


def knowledge_available() -> bool:
    path = knowledge_dir()
    return path.is_dir()


def read_order_notes(limit: int = 20) -> list[dict]:
    root = knowledge_dir()
    if not root.is_dir():
        return []
    notes = []
    for path in sorted(root.rglob("*.md")):
        if path.name.lower() == "writingstyle.md":
            continue
        if len(notes) >= limit:
            break
        try:
            if path.stat().st_size > 20_000:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lowered = text.lower()
        if not any(hint in lowered for hint in ORDER_HINTS):
            continue
        notes.append({"path": str(path.relative_to(root)), "text": text[:20_000]})
    return notes
