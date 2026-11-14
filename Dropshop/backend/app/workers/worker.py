"""Run with:  arq app.workers.worker.WorkerSettings   (from backend/)"""

from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings
from app.workers import tasks

settings = get_settings()


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [
        tasks.scan_new_purchases,
        tasks.poll_prices,
        tasks.evaluate_purchase,
        tasks.submit_claim,
        tasks.reconcile_refunds,
    ]
    cron_jobs = [
        cron(tasks.poll_prices, minute={0}),            # hourly; TODO: every minute in demo mode
        cron(tasks.reconcile_refunds, minute=set(range(0, 60, 5))),
        # TODO: nightly scan_new_purchases for each user (needs user_id arg → wrap in a small job)
    ]
