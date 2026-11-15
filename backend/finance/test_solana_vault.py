"""Run: cd backend && python -m pytest finance/test_solana_vault.py  (offline; the RPC is faked)."""

import asyncio
import struct
from types import SimpleNamespace

import pytest
from solders.hash import Hash
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.system_program import ID as SYSTEM_PROGRAM_ID

from app.config import get_settings
from finance import solana_vault as vault

RENT_EXEMPT = 890_880


class FakeRpc:
    """The handful of RPC calls the vault client makes, backed by plain Python state."""

    def __init__(self, history=None, vault_lamports=0, account=None):
        self.history = history or []  # newest first, like the real RPC
        self.vault_lamports = vault_lamports
        self.account = account
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_signatures_for_address(self, address, limit=None, commitment=None):
        return SimpleNamespace(value=self.history)

    async def get_balance(self, address, commitment=None):
        return SimpleNamespace(value=self.vault_lamports)

    async def get_minimum_balance_for_rent_exemption(self, size):
        return SimpleNamespace(value=RENT_EXEMPT)

    async def get_account_info(self, address, commitment=None):
        return SimpleNamespace(value=self.account)

    async def get_latest_blockhash(self):
        return SimpleNamespace(value=SimpleNamespace(blockhash=Hash.default()))

    async def send_transaction(self, transaction):
        self.sent.append(transaction)
        return SimpleNamespace(value=transaction.signatures[0])

    async def confirm_transaction(self, signature, commitment=None):
        return None


def entry(memo, signature=None, err=None):
    return SimpleNamespace(memo=memo, signature=signature or Signature.default(), err=err)


@pytest.fixture
def wallet(monkeypatch):
    monkeypatch.setenv("SOLANA_PROGRAM_ID", "")
    get_settings.cache_clear()
    keypair = Keypair()
    monkeypatch.setattr(vault, "load_keypair", lambda: keypair)
    yield keypair
    get_settings.cache_clear()


def use_rpc(monkeypatch, rpc):
    monkeypatch.setattr(vault, "_client", lambda: rpc)
    return rpc


def test_memo_parsing():
    assert vault.parse_memo("[32] dropshot:recovery:v1:c-test:5000") == ("c-test", 5000)
    assert vault.parse_memo("dropshot:recovery:v1:c1:949") == ("c1", 949)
    assert vault.parse_memo("[5] hello") is None and vault.parse_memo(None) is None


def test_vault_address_is_stable_per_user(wallet):
    mine = asyncio.run(vault.get_vault_address("demo-user"))
    assert mine == asyncio.run(vault.get_vault_address("demo-user"))
    assert mine != asyncio.run(vault.get_vault_address("someone-else"))
    assert vault.mode() == "ledger"


def test_ledger_record_moves_sol_and_writes_the_memo(wallet, monkeypatch):
    rpc = use_rpc(monkeypatch, FakeRpc(vault_lamports=0))
    signature = asyncio.run(vault.record_recovery("demo-user", "c1", 5000))
    assert len(rpc.sent) == 1 and signature == str(rpc.sent[0].signatures[0])
    transfer_ix, memo_ix = rpc.sent[0].message.instructions
    keys = rpc.sent[0].message.account_keys
    assert keys[transfer_ix.program_id_index] == SYSTEM_PROGRAM_ID
    lamports = struct.unpack_from("<Q", bytes(transfer_ix.data), 4)[0]
    assert lamports == 5000 * vault.LAMPORTS_PER_CENT + RENT_EXEMPT  # a new vault also gets the rent minimum
    assert keys[memo_ix.program_id_index] == vault.MEMO_PROGRAM_ID
    assert bytes(memo_ix.data).decode() == "dropshot:recovery:v1:c1:5000"

    rpc = use_rpc(monkeypatch, FakeRpc(vault_lamports=RENT_EXEMPT))
    asyncio.run(vault.record_recovery("demo-user", "c2", 949))
    lamports = struct.unpack_from("<Q", bytes(rpc.sent[0].message.instructions[0].data), 4)[0]
    assert lamports == 949 * vault.LAMPORTS_PER_CENT  # an existing vault only gets the refund


def test_recording_the_same_claim_twice_sends_nothing(wallet, monkeypatch):
    first = Signature.from_bytes(bytes([7] * 64))
    rpc = use_rpc(monkeypatch, FakeRpc(history=[entry("[28] dropshot:recovery:v1:c1:5000", first)], vault_lamports=RENT_EXEMPT))
    assert asyncio.run(vault.record_recovery("demo-user", "c1", 5000)) == str(first)
    assert rpc.sent == []


def test_balance_sums_each_successful_claim_once(wallet, monkeypatch):
    history = [  # newest first
        entry("[5] gm"),
        entry("[28] dropshot:recovery:v1:c3:3000", err={"InstructionError": [0, "Custom"]}),  # failed: ignored
        entry("[28] dropshot:recovery:v1:c1:5000"),  # duplicate of c1: ignored
        entry("[27] dropshot:recovery:v1:c2:949"),
        entry("[28] dropshot:recovery:v1:c1:5000"),
    ]
    use_rpc(monkeypatch, FakeRpc(history=history))
    assert asyncio.run(vault.get_vault_balance_cents("demo-user")) == 5949


def test_unfunded_wallet_gets_a_clear_error(wallet, monkeypatch):
    class Broke(FakeRpc):
        async def send_transaction(self, transaction):
            raise RuntimeError("Transaction simulation failed: This account may not be used to pay transaction fees")

    use_rpc(monkeypatch, Broke())
    with pytest.raises(vault.VaultError, match="no devnet SOL"):
        asyncio.run(vault.record_recovery("demo-user", "c1", 5000))
    with pytest.raises(vault.VaultError, match="positive"):
        asyncio.run(vault.record_recovery("demo-user", "c1", 0))


def test_missing_keypair_says_how_to_create_one(monkeypatch, tmp_path):
    monkeypatch.setenv("SOLANA_KEYPAIR_PATH", str(tmp_path / "nope.json"))
    get_settings.cache_clear()
    with pytest.raises(vault.VaultError, match="finance.solana_setup"):
        vault.load_keypair()
    get_settings.cache_clear()


# --- Program mode: encoding only. It has not been run against a deployed program. ---------------


def test_anchor_discriminators_and_instruction_layout():
    # Known answer: Anchor's discriminator for a global `initialize` instruction.
    assert vault._discriminator("global", "initialize") == bytes([175, 175, 109, 31, 13, 152, 155, 237])
    program, pda, owner = Keypair().pubkey(), Keypair().pubkey(), Keypair().pubkey()
    ix = vault.record_recovery_instruction(program, pda, owner, "c-1", 5000)
    data = bytes(ix.data)
    assert data[:8] == vault._discriminator("global", "record_recovery")
    assert data[8:12] == struct.pack("<I", 3) and data[12:15] == b"c-1"  # borsh string
    assert data[15:] == struct.pack("<Q", 5000)
    assert [(a.pubkey, a.is_signer, a.is_writable) for a in ix.accounts] == [(pda, False, True), (owner, True, False)]
    init = vault.initialize_vault_instruction(program, pda, owner)
    assert [a.pubkey for a in init.accounts] == [pda, owner, SYSTEM_PROGRAM_ID]


def test_program_mode_reads_the_vault_account(wallet, monkeypatch):
    program = Keypair().pubkey()
    monkeypatch.setenv("SOLANA_PROGRAM_ID", str(program))
    get_settings.cache_clear()
    assert vault.mode() == "program"
    expected = Pubkey.find_program_address([b"vault", bytes(wallet.pubkey())], program)[0]
    assert asyncio.run(vault.get_vault_address("demo-user")) == str(expected)

    data = vault._discriminator("account", "Vault") + bytes(wallet.pubkey()) + struct.pack("<QIB", 13250, 4, 254)
    assert vault.parse_vault_account(data)["total_recovered_cents"] == 13250
    use_rpc(monkeypatch, FakeRpc(account=SimpleNamespace(data=data)))
    assert asyncio.run(vault.get_vault_balance_cents("demo-user")) == 13250
    use_rpc(monkeypatch, FakeRpc(account=None))
    assert asyncio.run(vault.get_vault_balance_cents("demo-user")) == 0  # vault not created yet

    rpc = use_rpc(monkeypatch, FakeRpc(account=None))
    asyncio.run(vault.record_recovery("demo-user", "c1", 5000))
    assert len(rpc.sent[0].message.instructions) == 2  # initialize_vault, then record_recovery
    with pytest.raises(vault.VaultError):
        vault.parse_vault_account(b"\x00" * 60)
