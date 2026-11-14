"""Enqueue background jobs (the functions in `app/workers/tasks.py`).

Two ways a job runs:
  arq     pushed to Redis and executed by the worker process (`arq app.workers.worker.WorkerSettings`).
  inline  run as an asyncio task inside this process.

Jobs run inline when state is in memory (a separate worker process couldn't see it) and as a
fallback when Redis can't be reached, so the app keeps working without Redis or a worker.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from app.config import get_settings
from app.store import get_store

logger = logging.getLogger(__name__)

_inline_tasks: set[asyncio.Task] = set()
_pool = None  # arq connection pool, created on first use
_redis_down_until = 0.0  # after a failed connect, don't retry for a while
REDIS_RETRY_SECONDS = 30.0


def mode() -> str:
    """How jobs run right now: "inline" or "arq"."""
    if get_store().name == "memory":
        return "inline"
    return "inline" if (_pool is None and time.monotonic() < _redis_down_until) else "arq"


async def _arq_pool():
    global _pool, _redis_down_until
    if _pool is not None:
        return _pool
    if time.monotonic() < _redis_down_until:
        return None
    from arq import create_pool
    from arq.connections import RedisSettings

    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    redis_settings.conn_retries = 0  # fail fast; we have a fallback
    try:
        _pool = await create_pool(redis_settings)
    except Exception as exc:
        _redis_down_until = time.monotonic() + REDIS_RETRY_SECONDS
        logger.warning("Redis unreachable (%s); running jobs inline for now", type(exc).__name__)
        return None
    return _pool


async def enqueue(job: str, *args, defer_seconds: float = 0) -> str:
    """Queue `tasks.<job>(ctx, *args)`, optionally after a delay. Returns a job id."""
    if get_store().name != "memory":
        pool = await _arq_pool()
        if pool is not None:
            try:
                queued = await pool.enqueue_job(job, *args, _defer_by=defer_seconds or None)
                if queued is not None:
                    return queued.job_id
            except Exception as exc:
                logger.warning("Couldn't enqueue %s on Redis (%s); running it inline", job, type(exc).__name__)
    return _start_inline(job, args, defer_seconds)


def _start_inline(job: str, args: tuple, defer_seconds: float) -> str:
    job_id = f"inline-{uuid.uuid4().hex[:10]}"
    task = asyncio.create_task(_run_inline(job, args, defer_seconds), name=f"{job}:{job_id}")
    _inline_tasks.add(task)
    task.add_done_callback(_inline_tasks.discard)
    return job_id


async def _run_inline(job: str, args: tuple, defer_seconds: float) -> None:
    from app.workers import tasks  # imported late: tasks imports this module

    if defer_seconds > 0:
        await asyncio.sleep(defer_seconds)
    try:
        await getattr(tasks, job)({"inline": True}, *args)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Inline job %s%r failed", job, args)


async def drain(timeout: float = 120.0) -> None:
    """Wait until every inline job, and any job those jobs start, has finished."""
    deadline = time.monotonic() + timeout
    while True:
        pending = [t for t in _inline_tasks if not t.done()]
        if not pending:
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"{len(pending)} background job(s) still running after {timeout}s")
        await asyncio.wait(pending, timeout=remaining)


async def cancel_all() -> None:
    """Stop inline jobs (demo reset, shutdown) so they can't write into a fresh state."""
    pending = [t for t in _inline_tasks if not t.done()]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    _inline_tasks.clear()


async def close() -> None:
    global _pool
    await cancel_all()
    if _pool is not None:
        await _pool.aclose()
        _pool = None
