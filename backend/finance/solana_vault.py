"""Python client for the Dropshot savings vault on Solana devnet.

Interface the rest of the backend relies on (keep these signatures stable):
`get_vault_address`, `record_recovery`, `get_vault_balance_cents`.

Two on-chain backends behind that interface:

  program  SOLANA_PROGRAM_ID is set: the Anchor program in /solana. One `Vault` account (PDA,
           seeds ["vault", owner]) holds `total_recovered_cents`; `record_recovery` adds to it.
  ledger   No program id: no custom program needed. Each recovery is one transaction that moves
           devnet SOL from the backend wallet into the user's vault account (1 cent = 1,000
           lamports) and carries a memo `dropshot:recovery:v1:<claim_id>:<cents>`. The balance is
           the sum of those memos, read back from the chain.

Both produce a real signature for `https://explorer.solana.com/tx/<sig>?cluster=devnet`.
The backend wallet is the keypair at SOLANA_KEYPAIR_PATH. Create and fund it with
`python -m finance.solana_setup` (from backend/).

This module is the live client only and raises `VaultError` when it can't do its job. The
simulated fallback lives in `app/finance_gateway.py`.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.system_program import ID as SYSTEM_PROGRAM_ID
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction

from app.config import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
MEMO_PROGRAM_ID = Pubkey.from_string("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr")
LAMPORTS_PER_SOL = 1_000_000_000
LAMPORTS_PER_CENT = 1_000  # ledger mode: $50.00 moves 0.005 devnet SOL into the vault
MEMO_PREFIX = "dropshot:recovery:v1"
_MEMO_RE = re.compile(rf"{MEMO_PREFIX}:(?P<claim>[^:\s]+):(?P<cents>\d+)")
RPC_TIMEOUT = 30
HISTORY_LIMIT = 1000  # signatures read back per balance query (plenty for a demo vault)


class VaultError(RuntimeError):
    """The vault can't be reached or used (no keypair, no funds, RPC error)."""


# --- Wallet and addresses ---------------------------------------------------------------------


def keypair_path() -> Path:
    path = Path(get_settings().solana_keypair_path).expanduser()
    return path if path.is_absolute() else REPO_ROOT / path  # .env paths are relative to the repo root


def load_keypair() -> Keypair:
    path = keypair_path()
    if not path.is_file():
        raise VaultError(f"No Solana keypair at {path}. Create one with `python -m finance.solana_setup`.")
    return Keypair.from_bytes(bytes(json.loads(path.read_text())))


def program_id() -> Pubkey | None:
    value = get_settings().solana_program_id.strip()
    return Pubkey.from_string(value) if value else None


def mode() -> str:
    return "program" if program_id() else "ledger"


def _vault_pubkey(authority: Pubkey, user_id: str) -> Pubkey:
    program = program_id()
    if program:
        # One vault per owner. The backend wallet acts as the demo user's owner key.
        return Pubkey.find_program_address([b"vault", bytes(authority)], program)[0]
    seed = "vault-" + hashlib.sha256(user_id.encode()).hexdigest()[:26]  # seeds are 32 chars at most
    return Pubkey.create_with_seed(authority, seed, SYSTEM_PROGRAM_ID)


def explorer_url(signature: str) -> str:
    return f"https://explorer.solana.com/tx/{signature}?cluster=devnet"


def _client() -> AsyncClient:
    return AsyncClient(get_settings().solana_rpc_url, timeout=RPC_TIMEOUT)


async def _send(client: AsyncClient, signer: Keypair, instructions: list[Instruction]) -> str:
    blockhash = (await client.get_latest_blockhash()).value.blockhash
    message = Message.new_with_blockhash(instructions, signer.pubkey(), blockhash)
    try:
        signature = (await client.send_transaction(Transaction([signer], message, blockhash))).value
        await client.confirm_transaction(signature, commitment=Confirmed)
    except Exception as exc:
        text = str(exc) or type(exc).__name__
        unfunded = ("insufficient", "debit an account", "may not be used to pay", "accountnotfound")
        if any(marker in text.lower() for marker in unfunded):
            raise VaultError(
                f"The backend wallet {signer.pubkey()} has no devnet SOL. Fund it with "
                "`python -m finance.solana_setup` or https://faucet.solana.com."
            ) from exc
        raise VaultError(f"Solana transaction failed: {text[:200]}") from exc
    return str(signature)


# --- Ledger mode (memo + transfer) --------------------------------------------------------------


def _memo_instruction(signer: Pubkey, text: str) -> Instruction:
    return Instruction(MEMO_PROGRAM_ID, text.encode(), [AccountMeta(signer, is_signer=True, is_writable=False)])


def parse_memo(memo: str | None) -> tuple[str, int] | None:
    """`(claim_id, cents)` from a recovery memo, or None. The RPC prefixes memos with "[len] "."""
    found = _MEMO_RE.search(memo or "")
    return (found["claim"], int(found["cents"])) if found else None


async def _ledger_entries(client: AsyncClient, vault: Pubkey) -> dict[str, tuple[int, str]]:
    """claim_id -> (cents, signature) for every successful recovery recorded on the vault."""
    history = (await client.get_signatures_for_address(vault, limit=HISTORY_LIMIT, commitment=Confirmed)).value
    entries: dict[str, tuple[int, str]] = {}
    for item in reversed(history):  # oldest first, so a claim's first record wins
        parsed = parse_memo(item.memo) if item.err is None else None
        if parsed and parsed[0] not in entries:
            entries[parsed[0]] = (parsed[1], str(item.signature))
    return entries


async def _ledger_record(client: AsyncClient, signer: Keypair, vault: Pubkey, claim_id: str, amount_cents: int) -> str:
    existing = (await _ledger_entries(client, vault)).get(claim_id)
    if existing:
        return existing[1]  # already on chain: a retry must not record it twice
    lamports = amount_cents * LAMPORTS_PER_CENT
    if (await client.get_balance(vault, commitment=Confirmed)).value == 0:
        # A new account has to hold the rent-exempt minimum or the transfer is rejected.
        lamports += (await client.get_minimum_balance_for_rent_exemption(0)).value
    safe_claim = re.sub(r"[:\s]", "-", claim_id)
    return await _send(
        client, signer,
        [
            transfer(TransferParams(from_pubkey=signer.pubkey(), to_pubkey=vault, lamports=lamports)),
            _memo_instruction(signer.pubkey(), f"{MEMO_PREFIX}:{safe_claim}:{amount_cents}"),
        ],
    )


# --- Program mode (Anchor program in /solana) ---------------------------------------------------


def _discriminator(namespace: str, name: str) -> bytes:
    return hashlib.sha256(f"{namespace}:{name}".encode()).digest()[:8]


def initialize_vault_instruction(program: Pubkey, vault: Pubkey, owner: Pubkey) -> Instruction:
    return Instruction(
        program, _discriminator("global", "initialize_vault"),
        [
            AccountMeta(vault, is_signer=False, is_writable=True),
            AccountMeta(owner, is_signer=True, is_writable=True),
            AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
        ],
    )


def record_recovery_instruction(program: Pubkey, vault: Pubkey, owner: Pubkey, claim_id: str, amount_cents: int) -> Instruction:
    claim = claim_id.encode()
    data = _discriminator("global", "record_recovery") + struct.pack("<I", len(claim)) + claim + struct.pack("<Q", amount_cents)
    return Instruction(
        program, data,
        [AccountMeta(vault, is_signer=False, is_writable=True), AccountMeta(owner, is_signer=True, is_writable=False)],
    )


def parse_vault_account(data: bytes) -> dict:
    """Decode the Anchor `Vault` account: discriminator, owner, total_recovered_cents, claims_recorded, bump."""
    if len(data) < 8 + 32 + 8 + 4 + 1 or data[:8] != _discriminator("account", "Vault"):
        raise VaultError("That account isn't a Dropshot Vault")
    total, claims, bump = struct.unpack_from("<QIB", data, 40)
    return {"owner": str(Pubkey.from_bytes(data[8:40])), "total_recovered_cents": total, "claims_recorded": claims, "bump": bump}


async def _program_record(client: AsyncClient, signer: Keypair, vault: Pubkey, claim_id: str, amount_cents: int) -> str:
    program = program_id()
    instructions = []
    if (await client.get_account_info(vault, commitment=Confirmed)).value is None:
        instructions.append(initialize_vault_instruction(program, vault, signer.pubkey()))
    instructions.append(record_recovery_instruction(program, vault, signer.pubkey(), claim_id, amount_cents))
    return await _send(client, signer, instructions)


# --- Public interface -----------------------------------------------------------------------------


async def get_vault_address(user_id: str) -> str:
    """The user's vault account (a PDA of the program, or a seed-derived account in ledger mode)."""
    return str(_vault_pubkey(load_keypair().pubkey(), user_id))


async def record_recovery(user_id: str, claim_id: str, amount_cents: int) -> str:
    """Record a recovered amount on chain. Returns the transaction signature."""
    if amount_cents <= 0:
        raise VaultError("amount_cents must be positive")
    signer = load_keypair()
    vault = _vault_pubkey(signer.pubkey(), user_id)
    async with _client() as client:
        try:
            if program_id():
                return await _program_record(client, signer, vault, claim_id, amount_cents)
            return await _ledger_record(client, signer, vault, claim_id, amount_cents)
        except VaultError:
            raise
        except Exception as exc:
            raise VaultError(f"Solana RPC error: {str(exc)[:200] or type(exc).__name__}") from exc


async def get_vault_balance_cents(user_id: str) -> int:
    """Total recovered cents recorded in the vault, read from the chain."""
    vault = _vault_pubkey(load_keypair().pubkey(), user_id)
    async with _client() as client:
        try:
            if program_id():
                account = (await client.get_account_info(vault, commitment=Confirmed)).value
                return parse_vault_account(bytes(account.data))["total_recovered_cents"] if account else 0
            return sum(cents for cents, _ in (await _ledger_entries(client, vault)).values())
        except VaultError:
            raise
        except Exception as exc:
            raise VaultError(f"Solana RPC error: {str(exc)[:200] or type(exc).__name__}") from exc
