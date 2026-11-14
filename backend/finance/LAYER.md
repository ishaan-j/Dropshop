# Layer 5: Financial integration (Python side)

**Owner:** _TBD_ · **Stack:** Capital One Nessie, Solana (`solana` / `solders` Python SDKs)
The on-chain program lives in [`/solana`](../../solana/LAYER.md) and has the same owner.

## You own
- `nessie.py`: sandbox customer/account setup, purchases (to confirm charges), deposits (to detect refunds)
- `solana_vault.py`: Python client that calls the vault program (`record_recovery`, balance, address)

## Setup
- Get a Nessie API key at http://api.nessieisreal.com and put it in `.env` as `NESSIE_API_KEY`
- Solana devnet: `solana config set --url devnet`, `solana-keygen new -o solana/dev-keypair.json`, `solana airdrop 2`

## First tasks
- [ ] `nessie.create_demo_customer_and_account` plus seeded purchases (pair with L4 on `seed.py`)
- [ ] `nessie.simulate_refund` + `list_deposits` (the "refund landed" demo moment)
- [ ] Mock fallbacks for every Nessie call
- [ ] `solana_vault.record_recovery` returning a real devnet tx signature, linked from the UI
