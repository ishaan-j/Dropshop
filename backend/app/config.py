from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All config comes from the repo-root .env (see .env.example)."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    # General
    mock_mode: bool = True
    demo_user_id: str = "demo-user"

    # Layer 2
    api_base_url: str = "http://localhost:8000"  # public URL of this API; used for screenshot links
    redis_url: str = "redis://localhost:6379"
    cors_origins: str = "http://localhost:3000"
    # Where app state lives. "auto" = in-memory while MOCK_MODE is on or Layer 4 isn't implemented
    # yet, otherwise Mongo + Timescale through backend/data. "memory" / "db" force one.
    data_backend: Literal["auto", "memory", "db"] = "auto"
    # Demo behaviour: fast job schedules, the /demo endpoints, and the demo store "paying" a refund
    # shortly after a claim is submitted.
    demo_mode: bool = True
    demo_refund_delay_seconds: float = 6.0  # negative = never refund automatically
    scheduler_enabled: bool = True  # in-process job ticker, used when jobs run inside the API

    # Layer 3
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"  # ~1 s per call; the full flash models were overloaded
    # Tried in order if a model fails, and the whole chain is tried twice. Only the flash-lite models
    # answered reliably at the event: the full flash models returned 503s or took 18 s and more.
    gemini_fallback_models: str = "gemini-3.1-flash-lite"
    gemini_attempt_timeout_seconds: float = 4.0  # per attempt; a healthy answer takes about 1 s
    gemini_timeout_seconds: float = 20.0  # whole call; then fall back to the mock so a live demo never hangs
    sentient_os_enabled: bool = False
    sentient_knowledge_dir: str = "~/Sentient OS - Knowledge Base"  # where Sentient OS writes its Markdown notes
    # Also read for receipt files, so a user can drop a .md/.txt/.eml on the Desktop instead of
    # copying it into the knowledge base. Comma-separated, ~ is expanded.
    receipt_watch_dirs: str = "~/Desktop,~/Downloads"
    # Shared secret for POST /automations/*, the endpoints an outside automation (a Grok Bot routine)
    # calls. Empty = those endpoints are switched off.
    automation_token: str = ""
    xai_api_key: str = ""  # Grok Bot (policy watch)
    xai_base_url: str = "https://api.x.ai/v1"
    xai_model: str = "grok-4.7"  # ~2 s per call; the "grok-4" alias took ~17 s
    playwright_headless: bool = True
    retailer_claim_url: str = "http://localhost:3000/demo-store/claim"

    # Layer 4
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "dropshot"
    timescale_url: str = "postgresql://postgres:password@localhost:5432/dropshot"

    # Layer 5
    nessie_api_key: str = ""
    nessie_base_url: str = "https://api.nessieisreal.com"
    nessie_account_id: str = ""
    solana_rpc_url: str = "https://api.devnet.solana.com"
    solana_program_id: str = ""
    solana_keypair_path: str = "./solana/dev-keypair.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
