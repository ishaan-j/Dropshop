"""Create and fund the backend's devnet wallet.  Run from backend/:  python -m finance.solana_setup

Does what `solana-keygen new` + `solana airdrop` would, without needing the Solana CLI:
  1. creates the keypair at SOLANA_KEYPAIR_PATH if it doesn't exist (gitignored, devnet only),
  2. asks the devnet faucet for SOL if the wallet is low,
  3. prints the wallet, the demo user's vault address and the balance.

Devnet's RPC faucet is often closed. If the airdrop is refused, paste the wallet address into
https://faucet.solana.com (choose devnet) and run this again to check the balance.
"""

from __future__ import annotations

import asyncio
import json

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair

from app.config import get_settings
from finance import solana_vault

MIN_LAMPORTS = solana_vault.LAMPORTS_PER_SOL // 10  # 0.1 SOL covers hundreds of demo recoveries
AIRDROP_LAMPORTS = solana_vault.LAMPORTS_PER_SOL


def ensure_keypair() -> tuple[Keypair, bool]:
    path = solana_vault.keypair_path()
    if path.is_file():
        return solana_vault.load_keypair(), False
    keypair = Keypair()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(bytes(keypair))))
    return keypair, True


async def main() -> None:
    settings = get_settings()
    keypair, created = ensure_keypair()
    wallet = keypair.pubkey()
    print(f"Wallet:  {wallet}  ({'created' if created else 'existing'}, {solana_vault.keypair_path()})")
    print(f"Vault:   {await solana_vault.get_vault_address(settings.demo_user_id)}  (mode: {solana_vault.mode()})")
    async with AsyncClient(settings.solana_rpc_url, timeout=solana_vault.RPC_TIMEOUT) as client:
        balance = (await client.get_balance(wallet, commitment=Confirmed)).value
        if balance < MIN_LAMPORTS:
            print(f"Balance: {balance / solana_vault.LAMPORTS_PER_SOL:.4f} SOL. Requesting an airdrop...")
            try:
                signature = (await client.request_airdrop(wallet, AIRDROP_LAMPORTS)).value
                await client.confirm_transaction(signature, commitment=Confirmed)
                balance = (await client.get_balance(wallet, commitment=Confirmed)).value
            except Exception as exc:
                print(f"Airdrop refused ({type(exc).__name__}): the devnet RPC faucet is closed or rate limited.")
                print(f"Fund it by hand: https://faucet.solana.com  (devnet, address {wallet})")
        print(f"Balance: {balance / solana_vault.LAMPORTS_PER_SOL:.4f} SOL")
        if balance >= MIN_LAMPORTS:
            print("Ready. Set MOCK_MODE=false to record recoveries on devnet.")


if __name__ == "__main__":
    asyncio.run(main())
