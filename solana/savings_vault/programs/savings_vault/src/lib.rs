//! Dropshot savings vault.
//!
//! One `Vault` account per owner (PDA, seeds ["vault", owner]) keeps a running total of the money
//! Dropshot has recovered for them. The backend calls `record_recovery` once per refunded claim;
//! each call is a devnet transaction the dashboard links to as proof.
//!
//! The Python client is `backend/finance/solana_vault.py`. If you change an instruction's name,
//! arguments or account order, or the `Vault` layout, change the client to match.

use anchor_lang::prelude::*;

// Placeholder. `anchor keys sync` (or Solana Playground's Build) replaces it with your program id.
declare_id!("2ga1tPWuA1xmzRdtp1be6asNA8PFxMHgUPkfsDYarSXz");

const MAX_CLAIM_ID_LEN: usize = 64;

#[program]
pub mod savings_vault {
    use super::*;

    /// Create the owner's vault. Called once, before the first `record_recovery`.
    pub fn initialize_vault(ctx: Context<InitializeVault>) -> Result<()> {
        let vault = &mut ctx.accounts.vault;
        vault.owner = ctx.accounts.owner.key();
        vault.total_recovered_cents = 0;
        vault.claims_recorded = 0;
        vault.bump = ctx.bumps.vault;
        Ok(())
    }

    /// Add one refunded claim to the vault's total.
    pub fn record_recovery(ctx: Context<RecordRecovery>, claim_id: String, amount_cents: u64) -> Result<()> {
        require!(amount_cents > 0, VaultError::ZeroAmount);
        require!(claim_id.len() <= MAX_CLAIM_ID_LEN, VaultError::ClaimIdTooLong);

        let vault = &mut ctx.accounts.vault;
        vault.total_recovered_cents = vault
            .total_recovered_cents
            .checked_add(amount_cents)
            .ok_or(VaultError::Overflow)?;
        vault.claims_recorded = vault.claims_recorded.checked_add(1).ok_or(VaultError::Overflow)?;

        emit!(RecoveryRecorded {
            owner: vault.owner,
            claim_id,
            amount_cents,
            total_recovered_cents: vault.total_recovered_cents,
        });
        Ok(())
    }
}

#[derive(Accounts)]
pub struct InitializeVault<'info> {
    #[account(
        init,
        payer = owner,
        space = 8 + Vault::INIT_SPACE,
        seeds = [b"vault", owner.key().as_ref()],
        bump
    )]
    pub vault: Account<'info, Vault>,
    #[account(mut)]
    pub owner: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct RecordRecovery<'info> {
    #[account(
        mut,
        seeds = [b"vault", owner.key().as_ref()],
        bump = vault.bump,
        has_one = owner
    )]
    pub vault: Account<'info, Vault>,
    pub owner: Signer<'info>,
}

/// Layout read by the Python client: 8-byte discriminator, then these fields in order.
#[account]
#[derive(InitSpace)]
pub struct Vault {
    pub owner: Pubkey,
    pub total_recovered_cents: u64,
    pub claims_recorded: u32,
    pub bump: u8,
}

#[event]
pub struct RecoveryRecorded {
    pub owner: Pubkey,
    pub claim_id: String,
    pub amount_cents: u64,
    pub total_recovered_cents: u64,
}

#[error_code]
pub enum VaultError {
    #[msg("Amount must be greater than zero")]
    ZeroAmount,
    #[msg("Claim id is longer than 64 bytes")]
    ClaimIdTooLong,
    #[msg("Vault total overflowed")]
    Overflow,
}
