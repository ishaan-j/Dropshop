"""arq worker. Run from backend/:  arq app.workers.worker.WorkerSettings   (needs Redis)

The worker only has work when state lives in the database (DATA_BACKEND=db, or MOCK_MODE=false
once Layer 4 is implemented). With the in-memory store the API process runs every job itself.
"""

import logging

from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings
from app.store import init_store
from app.workers import tasks

logger = logging.getLogger(__name__)
settings = get_settings()


async def startup(ctx: dict) -> None:
    store = await init_store()
    if store.name == "memory":
        logger.warning(
            "This worker's store is in-memory, which the API process can't see. The API runs jobs "
            "inline in this mode, so the worker has nothing to do."
        )


async def nightly_scan(ctx: dict) -> int:
    return await tasks.scan_new_purchases(ctx, settings.demo_user_id)


# Demo mode: prices every minute, refunds every 10 seconds. Otherwise hourly and every 5 minutes.
_poll = cron(tasks.poll_prices, minute=None) if settings.demo_mode else cron(tasks.poll_prices, minute={0})
_reconcile = (
    cron(tasks.reconcile_refunds, minute=None, second=set(range(0, 60, 10)))
    if settings.demo_mode
    else cron(tasks.reconcile_refunds, minute=set(range(0, 60, 5)))
)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    functions = [
        tasks.scan_new_purchases,
        tasks.poll_prices,
        tasks.evaluate_purchase,
        tasks.submit_claim,
        tasks.issue_demo_refund,
        tasks.reconcile_refunds,
        tasks.watch_policies,
    ]
    cron_jobs = [
        _poll,
        _reconcile,
        cron(nightly_scan, hour={8}, minute={0}),  # 08:00 UTC, overnight in the US
        cron(tasks.watch_policies, hour={8}, minute={30}),  # Grok policy watch
    ]
