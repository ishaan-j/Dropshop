"""Dashboard numbers are summed from stored records. Nothing is filled in."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from app.config import get_settings
from app.models import (
    AgentSnapshot,
    Dashboard,
    DeadlineItem,
    IntegrationStatus,
    Opportunity,
    SavingsPoint,
    SavingsSummary,
)
from app.services.rules import price_difference_cents
from data.repository import repo
from finance import nessie
from finance.solana_vault import SolanaError, assert_devnet, get_balance_lamports, health
from integrations.gmail import connection_view, oauth_configured

TITLES = {
    "receipt": ("Receipt Agent", "Finds order messages and extracts purchases that the source actually states."),
    "price": ("Price Intelligence Agent", "Reads an authorized price source and records observations."),
    "eligibility": ("Eligibility Agent", "Applies the retailer rule set. A lower price is not automatically a refund."),
    "claim": ("Claim Agent", "Prepares a claim and submits it only after you approve, and only where automation is allowed."),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def build_dashboard(user_id: str) -> Dashboard:
    purchases = await repo.list_purchases(user_id)
    claims = await repo.list_claims(user_id)
    refunds = await repo.list_refunds(user_id)
    events = await repo.list_events(user_id, 8)
    matched = [refund for refund in refunds if refund.status == "matched"]
    matched.sort(key=lambda refund: refund.created_at)
    running = 0
    series: list[SavingsPoint] = []
    for refund in matched:
        running += refund.amount_cents
        series.append(
            SavingsPoint(time=refund.created_at, total_recovered_cents=running, data_origin=refund.data_origin)
        )
    pending = sum(claim.refund_cents for claim in claims if claim.status in {"awaiting_approval", "submitting", "submitted"})
    potential = 0
    drops = 0
    deadlines = []
    for purchase in purchases:
        if purchase.current_price_cents is not None and purchase.current_price_cents < purchase.price_paid_cents:
            drops += 1
        if purchase.eligibility == "eligible" and purchase.current_price_cents is not None:
            potential += price_difference_cents(purchase.price_paid_cents, purchase.current_price_cents)
        if (
            purchase.adjustment_window_ends
            and purchase.adjustment_window_ends >= _now()
            and purchase.status not in {"expired", "claimed"}
        ):
            deadlines.append(
                DeadlineItem(
                    purchase_id=purchase.id,
                    product_name=purchase.product_name,
                    retailer=purchase.retailer,
                    deadline=purchase.adjustment_window_ends,
                    data_origin=purchase.data_origin,
                )
            )
    deadlines.sort(key=lambda item: item.deadline)
    settings = get_settings()
    connection = await repo.get_connection(user_id)
    vault = connection.get("solana_address") or settings.solana_vault_address or None
    lamports = None
    verified = False
    if settings.solana_vault_address and os.getenv("DROP_SKIP_NETWORK") != "1":
        try:
            assert_devnet()
            lamports = await get_balance_lamports(settings.solana_vault_address)
            verified = True
        except SolanaError:
            lamports = None
            verified = False
    includes_demo = any(item.data_origin == "demo" for item in purchases + claims + matched)
    return Dashboard(
        total_recovered_cents=sum(refund.amount_cents for refund in matched),
        pending_refund_cents=pending,
        potential_savings_cents=potential,
        purchases_monitored=sum(1 for purchase in purchases if purchase.status == "monitoring"),
        purchase_count=len(purchases),
        price_drops_detected=drops,
        upcoming_deadlines=deadlines[:6],
        recent_activity=events,
        savings_series=series,
        includes_demo_data=includes_demo,
        persistence=_persistence_label(),
        vault_address=vault,
        vault_balance_lamports=lamports,
        vault_balance_verified=verified,
        integrations=await integration_statuses(user_id),
    )


def _persistence_label() -> str:
    if repo.mongo_mode == "live":
        return "mongodb_atlas"
    if repo.mongo_mode == "sandbox":
        return "mongodb_local"
    return "memory_demo"


async def savings_summary(user_id: str) -> SavingsSummary:
    board = await build_dashboard(user_id)
    claims = await repo.list_claims(user_id)
    return SavingsSummary(
        total_recovered_cents=board.total_recovered_cents,
        pending_cents=board.pending_refund_cents,
        potential_cents=board.potential_savings_cents,
        claims_submitted=sum(1 for claim in claims if claim.status in {"submitted", "refund_received"}),
        claims_won=sum(1 for claim in claims if claim.status == "refund_received"),
        vault_address=board.vault_address,
        vault_balance_lamports=board.vault_balance_lamports,
        vault_balance_verified=board.vault_balance_verified,
        data_note="Recovered totals count matched refund records only. Demo refunds are included when present and labeled.",
    )


async def opportunities(user_id: str) -> list[Opportunity]:
    claims = await repo.list_claims(user_id)
    rows = []
    for purchase in await repo.list_purchases(user_id):
        if purchase.eligibility == "unknown":
            continue
        related = [claim for claim in claims if claim.purchase_id == purchase.id]
        claim = related[0] if related else None
        current = purchase.current_price_cents
        difference = price_difference_cents(purchase.price_paid_cents, current) if current is not None else 0
        rows.append(
            Opportunity(
                purchase_id=purchase.id,
                claim_id=claim.id if claim else None,
                product_name=purchase.product_name,
                retailer=purchase.retailer,
                purchased_at=purchase.purchased_at,
                price_paid_cents=purchase.price_paid_cents,
                current_price_cents=current,
                difference_cents=difference,
                eligibility=purchase.eligibility,
                reason=purchase.eligibility_reason,
                evidence=purchase.eligibility_evidence,
                policy_url=purchase.policy_url,
                deadline=purchase.adjustment_window_ends,
                claim_status=claim.status if claim else None,
                price_source=purchase.price_source,
                data_origin=purchase.data_origin,
                missing_information=claim.missing_information if claim else [],
            )
        )
    return rows


async def agent_snapshots(user_id: str) -> list[AgentSnapshot]:
    runs = await repo.list_runs(user_id, limit=80)
    snapshots = []
    for name, (title, responsibility) in TITLES.items():
        mine = [run for run in runs if run.agent == name]
        latest = mine[0] if mine else None
        status = "idle"
        if latest and latest.status == "running":
            status = "running"
        elif latest and latest.status == "error":
            status = "error"
        snapshots.append(
            AgentSnapshot(
                name=name,  # type: ignore[arg-type]
                title=title,
                responsibility=responsibility,
                status=status,  # type: ignore[arg-type]
                current_task=latest.task if latest and latest.status == "running" else None,
                last_run_at=(latest.finished_at or latest.started_at) if latest else None,
                last_result=latest.result_summary if latest and latest.status == "completed" else None,
                last_error=latest.error if latest else None,
                data_origin=latest.data_origin if latest else None,
            )
        )
    return snapshots


async def integration_statuses(user_id: str) -> list[IntegrationStatus]:
    settings = get_settings()
    now = _now()
    statuses = [
        IntegrationStatus(id="mongodb", name="MongoDB", mode=_mode(repo.mongo_mode), detail=repo.mongo_detail, checked_at=now),
        IntegrationStatus(id="timescale", name="Tiger Data / TimescaleDB", mode=_mode(repo.pg_mode), detail=repo.pg_detail, checked_at=now),
        _gemini_status(now),
        await _gmail_status(user_id, now),
        await _nessie_status(now),
        await _solana_status(now),
        _vault_status(settings.solana_vault_address, now),
        await _sentient_status(user_id, now),
        _playwright_status(now),
    ]
    return statuses


def _mode(value: str):
    if value in {"live", "sandbox", "demo", "not_connected", "error"}:
        return value
    return "not_connected"


def _gemini_status(now: datetime) -> IntegrationStatus:
    if not get_settings().gemini_api_key.strip():
        return IntegrationStatus(
            id="gemini",
            name="Gemini",
            mode="not_connected",
            detail="GEMINI_API_KEY is empty. Extraction uses the deterministic parser for labeled demo emails only.",
            checked_at=now,
        )
    return IntegrationStatus(
        id="gemini",
        name="Gemini",
        mode="not_connected",
        detail="An API key is set, but DropShop has not confirmed a successful call in this view. A later agent run will report success or the error.",
        checked_at=now,
    )


async def _gmail_status(user_id: str, now: datetime) -> IntegrationStatus:
    if not oauth_configured():
        return IntegrationStatus(
            id="gmail",
            name="Gmail",
            mode="not_connected",
            detail="Gmail OAuth client id and secret are not configured. Sample emails are never described as Gmail.",
            checked_at=now,
        )
    view = await connection_view(user_id)
    if not view["connected"]:
        return IntegrationStatus(
            id="gmail",
            name="Gmail",
            mode="not_connected",
            detail="OAuth app is configured. This user has not connected a mailbox.",
            checked_at=now,
        )
    return IntegrationStatus(
        id="gmail",
        name="Gmail",
        mode="live",
        detail=f"Readonly token stored for {view.get('email') or 'a connected account'}.",
        checked_at=now,
    )


async def _nessie_status(now: datetime) -> IntegrationStatus:
    if not nessie.configured():
        return IntegrationStatus(
            id="nessie",
            name="Capital One Nessie",
            mode="not_connected",
            detail="NESSIE_API_KEY is empty. No bank data is shown.",
            checked_at=now,
        )
    if os.getenv("DROP_SKIP_NETWORK") == "1":
        return IntegrationStatus(
            id="nessie",
            name="Capital One Nessie",
            mode="not_connected",
            detail="Network probe skipped in this process.",
            checked_at=now,
        )
    try:
        customers = await nessie.list_customers()
    except nessie.NessieError as exc:
        return IntegrationStatus(id="nessie", name="Capital One Nessie", mode="error", detail=str(exc), checked_at=now)
    return IntegrationStatus(
        id="nessie",
        name="Capital One Nessie",
        mode="sandbox",
        detail=f"Sandbox responded. {len(customers)} customer record(s) visible to this key. Not a real bank account.",
        checked_at=now,
    )


async def _solana_status(now: datetime) -> IntegrationStatus:
    if os.getenv("DROP_SKIP_NETWORK") == "1":
        return IntegrationStatus(
            id="solana",
            name="Solana Devnet",
            mode="not_connected",
            detail="Network probe skipped in this process.",
            checked_at=now,
        )
    try:
        assert_devnet()
        result = await health()
    except SolanaError as exc:
        return IntegrationStatus(id="solana", name="Solana Devnet", mode="error", detail=str(exc), checked_at=now)
    if result != "ok":
        return IntegrationStatus(
            id="solana",
            name="Solana Devnet",
            mode="error",
            detail=f"Devnet getHealth returned {result}.",
            checked_at=now,
        )
    return IntegrationStatus(
        id="solana",
        name="Solana Devnet",
        mode="sandbox",
        detail="Devnet RPC getHealth returned ok. This is testnet SOL, not mainnet.",
        checked_at=now,
    )


def _vault_status(address: str, now: datetime) -> IntegrationStatus:
    if not address.strip():
        return IntegrationStatus(
            id="vault",
            name="Savings vault address",
            mode="not_connected",
            detail="SOLANA_VAULT_ADDRESS is empty. Deposits are disabled until a Devnet address is set. No program is deployed.",
            checked_at=now,
        )
    return IntegrationStatus(
        id="vault",
        name="Savings vault address",
        mode="sandbox",
        detail="A Devnet vault address is configured. Transfers still require your wallet signature.",
        checked_at=now,
    )


async def _sentient_status(user_id: str, now: datetime) -> IntegrationStatus:
    from agents.sentient import knowledge_available, knowledge_dir

    prefs = await repo.get_preferences(user_id)
    if not knowledge_available():
        return IntegrationStatus(
            id="sentient",
            name="Sentient OS",
            mode="not_connected",
            detail=f"Knowledge folder not found at {knowledge_dir()}. Sentient OS is not orchestrating these agents.",
            checked_at=now,
        )
    if not prefs.sentient_read_enabled:
        return IntegrationStatus(
            id="sentient",
            name="Sentient OS",
            mode="not_connected",
            detail="The knowledge folder exists. Reading stays off until you enable it in Settings.",
            checked_at=now,
        )
    return IntegrationStatus(
        id="sentient",
        name="Sentient OS",
        mode="live",
        detail="Opted in to read order-like Markdown notes from the local Sentient OS knowledge folder. DropShop still runs its own agents.",
        checked_at=now,
    )


def _playwright_status(now: datetime) -> IntegrationStatus:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return IntegrationStatus(
            id="playwright",
            name="Playwright",
            mode="not_connected",
            detail="Playwright is not installed. Claim approval will keep the claim unsubmitted and show a manual packet.",
            checked_at=now,
        )
    return IntegrationStatus(
        id="playwright",
        name="Playwright",
        mode="sandbox",
        detail="Playwright is installed and is only allowed to open the DropShop demo retailer form.",
        checked_at=now,
    )
