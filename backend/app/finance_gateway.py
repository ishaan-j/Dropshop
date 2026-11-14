"""Layer 2's door to money: the bank (Capital One Nessie) and the Solana savings vault.

Jobs and routers call these functions and never `backend/finance` directly, because each call has
two possible backends:
  live       `finance.nessie` / `finance.solana_vault` (Layer 5), when MOCK_MODE is off.
  simulated  an in-process bank ledger and a vault derived from claims.

MOCK_MODE uses the simulation only. In live mode the simulation is the safety net, so a demo
survives Nessie or the Solana RPC being down:
  - a refund that Nessie won't take is issued to the simulated bank instead, and `deposits()`
    always includes those simulated refunds, so the claim still reconciles;
  - a vault record that fails is raised to the caller. `reconcile_refunds` retries, then calls
    `mark_vault_down()`, after which records get a clearly marked `sim-` signature for a few
    minutes before Solana is tried again.
Every fallback is logged, and `modes()` (shown by GET /health) reports it.

Nessie records are dicts with `_id`, `amount` in dollars (or `amount_cents`), `description`, and
`transaction_date` / `purchase_date` as YYYY-MM-DD.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from app import mock_data
from app.config import get_settings
from app.models import Claim

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BankTxn:
    id: str
    amount_cents: int
    description: str
    date: date | None = None


class _SimulatedBank:
    def __init__(self) -> None:
        self.load(mock_data.build_seed())

    def load(self, seed: mock_data.Seed) -> None:
        self.card_purchases = [BankTxn(**row) for row in seed.card_purchases]
        self.deposits = [BankTxn(**row) for row in seed.deposits]
        self.issued: list[BankTxn] = []  # refunds paid by the simulator since the last reset

    def pay(self, amount_cents: int, description: str) -> BankTxn:
        txn = BankTxn(
            id=f"sim-dep-{uuid.uuid4().hex[:10]}", amount_cents=amount_cents, description=description,
            date=datetime.now(timezone.utc).date(),
        )
        self.deposits.append(txn)
        self.issued.append(txn)
        return txn


_sim_bank = _SimulatedBank()
_bank_fell_back = False  # a live Nessie call failed and the simulator covered for it
_vault_simulated = False  # set once a live vault call turns out to be unimplemented
_vault_down_until = 0.0  # monotonic time until which the vault is treated as unreachable
VAULT_RETRY_SECONDS = 300.0


def reset_simulation(seed: mock_data.Seed | None = None) -> None:
    """Reload the simulated bank (demo reset, app startup)."""
    _sim_bank.load(seed or mock_data.build_seed())


def reset_fallbacks() -> None:
    global _bank_fell_back, _vault_simulated, _vault_down_until
    _bank_fell_back = _vault_simulated = False
    _vault_down_until = 0.0


def mark_vault_down(seconds: float = VAULT_RETRY_SECONDS) -> None:
    """Stop trying Solana for a while; vault records are simulated until then."""
    global _vault_down_until
    _vault_down_until = time.monotonic() + seconds
    logger.warning("Solana vault unreachable; simulating vault records for the next %.0f s", seconds)


def _vault_is_down() -> bool:
    return time.monotonic() < _vault_down_until


def _bank_is_live() -> bool:
    settings = get_settings()
    return not settings.mock_mode and bool(settings.nessie_account_id and settings.nessie_api_key)


def _vault_is_simulated() -> bool:
    return _vault_simulated or _vault_is_down() or get_settings().mock_mode


def modes() -> dict[str, str]:
    bank = "simulated" if not _bank_is_live() else ("nessie+simulated" if _bank_fell_back else "nessie")
    if get_settings().mock_mode or _vault_simulated:
        vault = "simulated"
    else:
        vault = "solana+simulated" if _vault_is_down() else "solana"
    return {"bank": bank, "vault": vault}


def _bank_failed(what: str, exc: Exception) -> None:
    global _bank_fell_back
    _bank_fell_back = True
    logger.warning("Nessie %s failed (%s: %s); the simulated bank is covering", what, type(exc).__name__, str(exc)[:120])


def _vault_unavailable(what: str) -> None:
    global _vault_simulated
    if not _vault_simulated:
        logger.warning("finance.solana_vault.%s isn't implemented yet; using the simulated vault from now on", what)
    _vault_simulated = True


def _parse_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


def _from_nessie(record: dict) -> BankTxn:
    if "amount_cents" in record:
        cents = int(record["amount_cents"])
    else:
        cents = round(float(record.get("amount", 0)) * 100)
    when = record.get("transaction_date") or record.get("purchase_date") or record.get("date")
    return BankTxn(
        id=str(record.get("_id") or record.get("id") or ""),
        amount_cents=cents,
        description=str(record.get("description") or ""),
        date=_parse_date(when),
    )


# --- Bank -----------------------------------------------------------------------------------


async def card_purchases() -> list[BankTxn]:
    """Card charges on the demo account, used to confirm a discovered purchase."""
    if not _bank_is_live():
        return list(_sim_bank.card_purchases)
    from finance import nessie

    try:
        return [_from_nessie(r) for r in await nessie.list_purchases(get_settings().nessie_account_id)]
    except Exception as exc:
        _bank_failed("list_purchases", exc)
        return []  # confirming a purchase is optional; don't confirm against made-up charges


async def deposits() -> list[BankTxn]:
    """Deposits on the demo account. A retailer refund shows up here."""
    if not _bank_is_live():
        return list(_sim_bank.deposits)
    from finance import nessie

    try:
        live = [_from_nessie(r) for r in await nessie.list_deposits(get_settings().nessie_account_id)]
    except Exception as exc:
        _bank_failed("list_deposits", exc)
        live = []
    return live + list(_sim_bank.issued)  # plus any refund the simulator had to cover


async def issue_refund(amount_cents: int, description: str) -> BankTxn:
    """The demo store 'pays' a refund: a deposit lands on the demo account."""
    if _bank_is_live():
        from finance import nessie

        try:
            record = await nessie.simulate_refund(get_settings().nessie_account_id, amount_cents, description)
            record = record.get("objectCreated", record) if isinstance(record, dict) else {}
            txn = _from_nessie(record)
            if not txn.id:
                raise ValueError("Nessie returned no deposit id")
            # Nessie may echo little back; keep what we asked for.
            return BankTxn(txn.id, txn.amount_cents or amount_cents, txn.description or description, txn.date)
        except Exception as exc:
            _bank_failed("simulate_refund", exc)
    return _sim_bank.pay(amount_cents, description)


# --- Solana vault ---------------------------------------------------------------------------


def _sim_signature(claim_id: str, amount_cents: int) -> str:
    digest = hashlib.sha256(f"{claim_id}:{amount_cents}".encode()).hexdigest()[:40]
    return f"sim-{digest}"  # the prefix keeps it from being mistaken for a real devnet signature


async def record_recovery(user_id: str, claim_id: str, amount_cents: int) -> str:
    """Record a recovered amount in the user's vault. Returns the transaction signature."""
    if not _vault_is_simulated():
        from finance import solana_vault

        try:
            return await solana_vault.record_recovery(user_id, claim_id, amount_cents)
        except NotImplementedError:
            _vault_unavailable("record_recovery")
    return _sim_signature(claim_id, amount_cents)


async def vault_address(user_id: str) -> str | None:
    if not (get_settings().mock_mode or _vault_simulated):
        from finance import solana_vault

        try:
            return await solana_vault.get_vault_address(user_id)
        except NotImplementedError:
            _vault_unavailable("get_vault_address")
    return mock_data.VAULT_ADDRESS


async def vault_balance_cents(user_id: str, claims: list[Claim]) -> int:
    """Vault balance. Simulated: the sum of every claim already recorded in the vault."""
    if not (get_settings().mock_mode or _vault_simulated):  # read the chain even while writes are paused
        from finance import solana_vault

        try:
            return await solana_vault.get_vault_balance_cents(user_id)
        except NotImplementedError:
            _vault_unavailable("get_vault_balance_cents")
    return sum(c.refund_cents for c in claims if c.user_id == user_id and c.solana_tx_signature)
