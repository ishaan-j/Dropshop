# Layer 5: Solana savings vault

**Owner:** _TBD_ (same as `backend/finance/`) · **Stack:** Solana devnet, Anchor (Rust)

The vault records every recovered refund on Solana devnet. The backend talks to it through
`backend/finance/solana_vault.py`, which has two modes:

| Mode | When | What goes on chain |
|---|---|---|
| **ledger** | `SOLANA_PROGRAM_ID` is empty (default) | One transaction per recovery: devnet SOL moves from the backend wallet into the user's vault account (1 cent = 1,000 lamports) with a memo `dropshot:recovery:v1:<claim>:<cents>`. The balance is the sum of those memos. No custom program. |
| **program** | `SOLANA_PROGRAM_ID` is set | The Anchor program in `savings_vault/`: a `Vault` PDA holds `total_recovered_cents`, and `record_recovery` adds to it. |

Either way each recovery has an Explorer link: `https://explorer.solana.com/tx/<sig>?cluster=devnet`.

## Status
- [x] Python client, both modes, with tests (`backend/finance/test_solana_vault.py`)
- [x] Ledger transaction simulated successfully against devnet's System and Memo programs
- [ ] **Fund the backend wallet.** Devnet's RPC faucet is closed, so it needs the web faucet (below). Until then nothing real has been sent.
- [ ] **Build and deploy the Anchor program.** The source in `savings_vault/` has never been compiled: it was written on a machine without Rust, the Solana CLI or Anchor.

## Set up the backend wallet (needed for both modes)
From `backend/`:
```bash
python -m finance.solana_setup     # creates solana/dev-keypair.json (gitignored), prints the wallet address
```
Paste the printed wallet address into https://faucet.solana.com (devnet), then run the command again
to confirm the balance. 0.1 SOL covers hundreds of demo recoveries. Then set `MOCK_MODE=false`.

## Deploy the Anchor program (optional upgrade from ledger mode)
No local toolchain needed:
1. Open https://beta.solpg.io, create an Anchor project, and replace `lib.rs` with
   `savings_vault/programs/savings_vault/src/lib.rs`.
2. Build, then Deploy to devnet (the Playground wallet needs about 2 devnet SOL).
3. Put the program id it shows into `.env` as `SOLANA_PROGRAM_ID`. The backend creates its vault on first use.

With the toolchain (Solana CLI + Anchor 0.31; on Windows use WSL):
```bash
cd solana/savings_vault
anchor keys sync && anchor build && anchor deploy --provider.cluster devnet
```

## Program design
**Account `Vault`** (PDA, seeds `["vault", owner]`): `owner: Pubkey, total_recovered_cents: u64, claims_recorded: u32, bump: u8`

| Instruction | Who signs | Does |
|---|---|---|
| `initialize_vault` | owner | Creates the Vault PDA |
| `record_recovery(claim_id: String, amount_cents: u64)` | owner | Adds to `total_recovered_cents`, emits `RecoveryRecorded` |

The backend wallet is the owner: it stands in for the single demo user. Known limits: `record_recovery`
doesn't reject a claim id it has already seen (the ledger mode does), and there is no `deposit` / `withdraw` yet.
