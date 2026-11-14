# Layer 5: Solana savings vault (Anchor program)

**Owner:** _TBD_ (same as `backend/finance/`) · **Stack:** Solana devnet, Anchor (Rust)

## Setup
Install the Solana CLI and Anchor (`avm`). On Windows, use WSL. Then, from this folder:
```bash
anchor init savings_vault     # generates the program workspace here
cd savings_vault
anchor build && anchor deploy --provider.cluster devnet
```
Put the deployed program ID into `.env` as `SOLANA_PROGRAM_ID`.

## Program design (v1, keep it small)

**Account `Vault`** (PDA, seeds `["vault", owner]`):
`owner: Pubkey, total_recovered_cents: u64, claims_recorded: u32, bump: u8`

**Instructions**
| Instruction | Who signs | Does |
|---|---|---|
| `initialize_vault` | owner | Creates the Vault PDA |
| `record_recovery(claim_id: String, amount_cents: u64)` | backend authority | Adds to `total_recovered_cents`, emits a `RecoveryRecorded` event |
| `deposit(lamports)` *(stretch)* | owner | Moves real devnet SOL / USDC into the vault so the "savings" are actual funds |
| `withdraw(lamports)` *(stretch)* | owner | Withdraws from the vault |

Each `record_recovery` produces an Explorer link (`https://explorer.solana.com/tx/<sig>?cluster=devnet`) that we show in the UI as proof.

## First tasks
- [ ] `anchor init`, then `initialize_vault` + `record_recovery` with tests
- [ ] Deploy to devnet and share the program ID + IDL with the team
- [ ] Wire `backend/finance/solana_vault.py` to it
