from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import activity, auth, claims, demo_site, health, integrations, prices, purchases, savings, vault, workflow
from data.repository import repo

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await repo.connect()
    yield
    repo.close()


app = FastAPI(title="DropShop API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (
    health,
    auth,
    purchases,
    prices,
    claims,
    activity,
    savings,
    workflow,
    demo_site,
    integrations,
    vault,
):
    app.include_router(module.router)
