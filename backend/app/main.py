import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import finance_gateway, jobs, scheduler
from app.config import get_settings
from app.routers import activity, automations, claims, demo, health, policies, prices, purchases, savings
from app.store import init_store
from app.workers import tasks

logger = logging.getLogger("dropshot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    store = await init_store()
    ticker = None
    if store.name == "memory":
        finance_gateway.reset_simulation(store.seed)
    # This process runs the periodic jobs when no worker can: in-memory state is invisible to a
    # worker, and without Redis there is no worker to hand them to.
    if settings.scheduler_enabled and (store.name == "memory" or not await jobs.queue_available()):
        ticker = asyncio.create_task(scheduler.run_forever(), name="scheduler")
    logger.info("Dropshot API ready: store=%s jobs=%s mock_mode=%s", store.name, jobs.mode(), settings.mock_mode)
    try:
        yield
    finally:
        if ticker:
            ticker.cancel()
            with suppress(asyncio.CancelledError):
                await ticker
        await jobs.close()
        if hasattr(store, "close"):
            await store.close()  # database connections


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Dropshot API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(NotImplementedError)
    async def not_implemented(request: Request, exc: NotImplementedError) -> JSONResponse:
        # A Layer 4 / Layer 5 function that hasn't been written yet.
        detail = str(exc) or (
            "This needs a backend layer that isn't implemented yet. Set DATA_BACKEND=memory to use demo data."
        )
        return JSONResponse(status_code=501, content={"detail": detail})

    for r in (health, purchases, prices, policies, claims, activity, savings, demo, automations):
        app.include_router(r.router)

    # Claim-bot screenshots, linked from AgentEvent.screenshot_url.
    tasks.SCREENSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    app.mount("/screenshots", StaticFiles(directory=tasks.SCREENSHOT_ROOT), name="screenshots")
    return app


app = create_app()
