# Layer 5: Financial integration (Python side)

**Owner:** _TBD_ · **Stack:** Capital One Nessie, Solana (`solana` / `solders` Python SDKs)
The on-chain side lives in [`/solana`](../../solana/LAYER.md) and has the same owner.

## You own
| Module | Job |
|---|---|
| `nessie.py` | Nessie sandbox client: customer and account setup, card purchases, merchants, deposits, the demo refund |
| `nessie_seed.py` | `python -m finance.nessie_seed`: puts the demo purchases' card charges on the account (safe to re-run) |
| `solana_vault.py` | Vault client: `record_recovery`, balance, address. Two modes, see [`/solana/LAYER.md`](../../solana/LAYER.md) |
| `solana_setup.py` | `python -m finance.solana_setup`: creates the devnet wallet and checks its balance |

These modules are the live clients only: they raise when a call fails. The simulated bank and vault, and the
rules for falling back to them, live in `backend/app/finance_gateway.py` (Layer 2), which is what the jobs call.
Tests: `python -m pytest finance` from `backend/` (offline).

## Setup
- **Nessie:** get a key at https://api.nessieisreal.com and set `NESSIE_API_KEY`. Create the demo account with
  `finance.nessie.create_demo_customer_and_account()` and put its id in `NESSIE_ACCOUNT_ID`, then run
  `python -m finance.nessie_seed`. The base URL must be `https://`.
- **Solana:** `python -m finance.solana_setup`, then fund the printed wallet at https://faucet.solana.com (devnet).

## Things to know about Nessie
- It **keeps whole dollars only**: a $399.99 purchase comes back as 399, a $37.50 deposit as 37. Layer 2 matches
  a refund by the claim id in the deposit's description, and a card charge by its whole-dollar amount.
- New purchases and deposits are `pending` until Nessie's batch processes them; matching doesn't wait for that.

## Status
- [x] Nessie client, verified against the live sandbox: account read, purchases and deposits listed and created
- [x] Demo card charges seeded; a scanned purchase is "confirmed against your card" in live mode
- [x] Refund deposit detected and matched to its claim in live mode, including an uneven amount
- [x] Simulated fallbacks for every Nessie and vault call (in Layer 2's gateway)
- [x] Vault client written and unit-tested; its transaction passes a simulation on devnet
- [ ] A real devnet transaction: blocked until the wallet has test SOL (the RPC faucet is closed to scripts)
- [ ] The Anchor program: source only, never compiled or deployed
