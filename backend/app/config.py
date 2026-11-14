from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All config comes from the repo-root .env (see .env.example)."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    mock_mode: bool = True
    demo_user_id: str = "demo-user"
    session_secret: str = ""
    token_encryption_key: str = ""

    redis_url: str = "redis://localhost:6379"
    cors_origins: str = "http://localhost:3000"
    public_base_url: str = "http://localhost:8000"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    sentient_os_enabled: bool = False
    sentient_knowledge_dir: str = ""
    playwright_headless: bool = True

    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:8000/integrations/gmail/callback"

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "dropshot"
    timescale_url: str = "postgresql://postgres:password@localhost:5432/dropshot"

    nessie_api_key: str = ""
    nessie_base_url: str = "https://api.nessieisreal.com"
    nessie_account_id: str = ""
    nessie_customer_id: str = ""

    solana_rpc_url: str = "https://api.devnet.solana.com"
    solana_program_id: str = ""
    solana_keypair_path: str = ""
    solana_vault_address: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
