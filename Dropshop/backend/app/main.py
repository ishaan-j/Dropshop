from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import activity, claims, health, prices, purchases, savings

settings = get_settings()

app = FastAPI(title="Dropshot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (health, purchases, prices, claims, activity, savings):
    app.include_router(r.router)
