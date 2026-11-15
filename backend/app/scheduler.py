"""In-process stand-in for the arq cron jobs, used when jobs run inside the API (in-memory store,
or a database store with no Redis to reach a worker through).

Demo mode: reconcile refunds every 5 s and poll prices every minute. Otherwise every 5 minutes
and hourly, like the worker's cron schedule.
"""

from __future__ import annotations

import asyncio
import logging
import time

from app.config import get_settings
from app.workers import tasks

logger = logging.getLogger(__name__)


async def _run(job) -> None:
    try:
        await job({"inline": True})
    except Exception:
        logger.exception("Scheduled job %s failed", job.__name__)


async def run_forever() -> None:
    poll_every, reconcile_every = (60.0, 5.0) if get_settings().demo_mode else (3600.0, 300.0)
    next_poll = time.monotonic() + poll_every
    next_reconcile = time.monotonic() + reconcile_every
    while True:
        await asyncio.sleep(1.0)
        now = time.monotonic()
        if now >= next_reconcile:
            next_reconcile = now + reconcile_every
            await _run(tasks.reconcile_refunds)
        if now >= next_poll:
            next_poll = now + poll_every
            await _run(tasks.poll_prices)


async def _quiet_scan(ctx: dict) -> int:
    ctx = {**ctx, "quiet": True}
    return await tasks.scan_new_purchases(ctx)


async def run_receipt_scans() -> None:
    """Read the knowledge base, Desktop, and Downloads on a timer. No button press required.

    A scan that finds nothing is quiet, so the activity feed is not filled with repeat notices.
    """
    every = 60.0 if get_settings().demo_mode else 900.0
    next_scan = time.monotonic() + 15.0
    while True:
        await asyncio.sleep(1.0)
        now = time.monotonic()
        if now >= next_scan:
            next_scan = now + every
            await _run(_quiet_scan)
