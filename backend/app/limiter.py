from __future__ import annotations

import time

_hits: dict[str, list[float]] = {}


def allow(key: str, limit: int, window: float = 60) -> bool:
    now = time.time()
    recent = [stamp for stamp in _hits.get(key, []) if now - stamp < window]
    if len(recent) >= limit:
        _hits[key] = recent
        return False
    recent.append(now)
    _hits[key] = recent
    return True
