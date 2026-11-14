"""Python client for the Dropshot savings-vault Anchor program on Solana devnet (program lives in /solana).

Interface the rest of the backend relies on. Keep these signatures stable.
"""

from app.config import get_settings

settings = get_settings()


async def get_vault_address(user_id: str) -> str:
    """TODO(L5): derive the vault PDA for this user (seeds: ['vault', owner_pubkey])."""
    raise NotImplementedError


async def record_recovery(user_id: str, claim_id: str, amount_cents: int) -> str:
    """TODO(L5): call the program's `record_recovery` instruction. Returns the tx signature
    (shown in the UI with a Solana Explorer devnet link)."""
    raise NotImplementedError


async def get_vault_balance_cents(user_id: str) -> int:
    """TODO(L5): read the vault account's total_recovered_cents."""
    raise NotImplementedError
