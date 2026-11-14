from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All config comes from the repo-root .env (see .env.example)."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    # General
    mock_mode: bool = True
    demo_user_id: str = "demo-user"

    # Layer 2
    redis_url: str = "redis://localhost:6379"
    cors_origins: str = "http://localhost:3000"

    # Layer 3
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    sentient_os_enabled: bool = False
    playwright_headless: bool = True

    # Layer 4
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "dropshot"
    timescale_url: str = "postgresql://postgres:password@localhost:5432/dropshot"

    # Layer 5
    nessie_api_key: str = ""
    nessie_base_url: str = "http://api.nessieisreal.com"
    nessie_account_id: str = ""
    solana_rpc_url: str = "https://api.devnet.solana.com"
    solana_program_id: str = ""
    solana_keypair_path: str = "./solana/dev-keypair.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
