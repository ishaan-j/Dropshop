"""Background jobs. Layer 2 owns orchestration; the heavy lifting lives in agents/, data/, finance/.

Each job: load state (store) → call agents / finance → persist results (store) → log an AgentEvent.
Jobs run on the arq worker, or inline in the API process (see `app/jobs.py`). Every job takes the
arq `ctx` dict first and never raises for an expected failure: it records an "error" event instead.

Pipeline:
  scan_new_purchases   receipts → purchases
  poll_prices          record prices, detect drops            → evaluate_purchase
  evaluate_purchase    policy + eligibility → draft a claim   (waits for the user's approval)
  submit_claim         Playwright bot files the claim         → issue_demo_refund (demo mode)
  issue_demo_refund    the demo store pays: a bank deposit    → reconcile_refunds
  reconcile_refunds    match deposits to claims, record the recovery in the Solana vault
  watch_policies       Grok checks retailer policy pages for changes (nightly)
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agents import claim_bot, claim_writer, eligibility, grok_bot, policy_reader, receipt_extractor, sentient
from app import finance_gateway, jobs, price_feed
from app.config import get_settings
from app.finance_gateway import BankTxn
from app.models import (
    AgentEvent,
    AgentEventKind,
    Claim,
    EligibilityResult,
    Purchase,
    PurchaseCreate,
    PurchaseSource,
    RetailerPolicy,
)
from app.store import get_store

logger = logging.getLogger(__name__)

SCREENSHOT_ROOT = Path(__file__).resolve().parents[2] / "artifacts" / "claim_screenshots"
SCAN_LOOKBACK_DAYS = 30
OPEN_CLAIM = {"awaiting_approval", "submitting", "submitted"}

_evaluating: set[str] = set()  # purchases with an evaluation in flight in this process
_vault_failures: dict[str, int] = {}  # claim id -> failed attempts to record it on Solana
VAULT_ATTEMPTS = 3  # then the record is simulated so the claim can finish


# --- Helpers --------------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


async def log_event(
    kind: AgentEventKind,
    message: str,
    *,
    purchase: Purchase | None = None,
    claim: Claim | None = None,
    screenshot_url: str | None = None,
    user_id: str | None = None,
) -> None:
    owner = user_id or (purchase and purchase.user_id) or (claim and claim.user_id) or get_settings().demo_user_id
    await get_store().log_event(
        AgentEvent(
            id=f"e-{uuid.uuid4().hex[:10]}", user_id=owner, time=_now(), kind=kind, message=message,
            purchase_id=purchase.id if purchase else (claim.purchase_id if claim else None),
            claim_id=claim.id if claim else None, screenshot_url=screenshot_url,
        )
    )


async def policy_for(retailer: str) -> RetailerPolicy:
    """The retailer's policy: the stored copy if we have one, otherwise read and store it."""
    store = get_store()
    policy = await store.get_policy(retailer)
    if policy is None:
        policy = await policy_reader.get_policy(retailer)
        await store.save_policy(policy)
    return policy


def _words(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def product_id_for(item: PurchaseCreate) -> str:
    """Stable Tiger Data key: retailer plus the SKU from the URL, or a slug of the name."""
    retailer = re.sub(r"[^a-z0-9]", "", item.retailer.lower()) or "store"
    sku = re.search(r"(B0[A-Z0-9]{8}|\d{6,})", item.product_url or "")
    return f"{retailer}:{sku.group(1) if sku else '-'.join(_words(item.product_name).split()[:6])}"


def _amount_matches(bank_cents: int, expected_cents: int) -> bool:
    """Bank amount equals ours, exactly or with the cents dropped (Nessie keeps whole dollars)."""
    return bank_cents == expected_cents or bank_cents == expected_cents // 100 * 100


def _same_purchase(item: PurchaseCreate, existing: Purchase) -> bool:
    """Is this receipt line already tracked? Receipts and stored names rarely match exactly."""
    if _words(item.retailer) != _words(existing.retailer):
        return False
    a, b = _words(item.product_name), _words(existing.product_name)
    names_overlap = bool(a and b) and (a in b or b in a)
    same_price = item.price_paid_cents == existing.price_paid_cents
    if item.order_number and existing.order_number:
        return item.order_number == existing.order_number and (same_price or names_overlap)
    return same_price and names_overlap


async def register_purchase(
    item: PurchaseCreate,
    *,
    user_id: str,
    source: PurchaseSource,
    card_charges: list[BankTxn] | None = None,
    taken_charge_ids: set[str] | None = None,
) -> Purchase:
    """Turn a receipt line (or a manual entry) into a monitored purchase and save it."""
    store, now = get_store(), _now()
    purchased_at = _utc(item.purchased_at)
    policy = await policy_for(item.retailer)
    window_ends = purchased_at + timedelta(days=policy.window_days) if policy.window_days is not None else None
    charge = next(
        (
            c for c in card_charges or []
            if c.id not in (taken_charge_ids or set()) and _amount_matches(c.amount_cents, item.price_paid_cents)
        ),
        None,
    )
    product_id = product_id_for(item)
    latest = await store.latest_price(product_id)
    purchase = Purchase(
        **item.model_dump(exclude={"purchased_at"}),
        purchased_at=purchased_at,
        id=f"p-{uuid.uuid4().hex[:8]}",
        user_id=user_id,
        product_id=product_id,
        source=source,
        nessie_purchase_id=charge.id if charge else None,
        adjustment_window_ends=window_ends,
        current_price_cents=latest.price_cents if latest else item.price_paid_cents,
        status="expired" if window_ends and now > window_ends else "monitoring",
    )
    await store.save_purchase(purchase)
    if latest is None:  # start the price chart at what was paid
        if purchased_at < now:
            await store.insert_price(product_id, item.retailer, item.price_paid_cents, time=purchased_at, source="seed")
        await store.insert_price(product_id, item.retailer, item.price_paid_cents, time=now, source="seed")
    return purchase


def _shot_url(path: str | None) -> str | None:
    """Public URL of a bot screenshot (served by the API under /screenshots)."""
    if not path:
        return None
    try:
        relative = Path(path).resolve().relative_to(SCREENSHOT_ROOT)
    except ValueError:
        return None
    return f"{get_settings().api_base_url.rstrip('/')}/screenshots/{relative.as_posix()}"


# --- Jobs -----------------------------------------------------------------------------------


async def scan_new_purchases(ctx: dict, user_id: str | None = None) -> int:
    """Receipts (Sentient OS, or the fixture fallback) → new monitored purchases. Returns how many."""
    settings, store = get_settings(), get_store()
    user_id = user_id or settings.demo_user_id
    source: PurchaseSource = "sentient" if settings.sentient_os_enabled and not settings.mock_mode else "email"
    since = (_now() - timedelta(days=SCAN_LOOKBACK_DAYS)).isoformat()
    try:
        receipts = await sentient.fetch_recent_receipts(since)
    except Exception as exc:
        logger.exception("Receipt scan failed")
        await log_event("error", f"Couldn't scan for receipts ({type(exc).__name__}).", user_id=user_id)
        return 0

    existing = await store.list_purchases(user_id)
    try:
        charges = await finance_gateway.card_purchases()
    except Exception as exc:  # the bank is optional here: it only confirms a purchase
        logger.warning("Couldn't load card charges to confirm purchases (%s)", type(exc).__name__)
        charges = []
    taken = {p.nessie_purchase_id for p in existing if p.nessie_purchase_id}

    found = 0
    for raw in receipts:
        try:
            receipt = await receipt_extractor.extract(raw)
        except Exception:
            logger.exception("Skipping a receipt that failed extraction")
            continue
        for item in receipt.items:
            if any(_same_purchase(item, p) for p in existing):
                continue
            purchase = await register_purchase(
                item, user_id=user_id, source=source, card_charges=charges, taken_charge_ids=taken
            )
            existing.append(purchase)
            if purchase.nessie_purchase_id:
                taken.add(purchase.nessie_purchase_id)
            where = "through Sentient OS" if source == "sentient" else "in your email"
            confirmed = " Confirmed against your card." if purchase.nessie_purchase_id else ""
            await log_event(
                "purchase_found",
                f"Found a new purchase {where}: {purchase.product_name} "
                f"({money(purchase.price_paid_cents)}, {purchase.retailer}).{confirmed}",
                purchase=purchase,
            )
            found += 1
    if not found:
        await log_event(
            "purchase_found",
            f"Scanned {len(receipts)} receipt{'s' if len(receipts) != 1 else ''}: nothing new, "
            "every purchase is already tracked.",
            user_id=user_id,
        )
    return found


async def poll_prices(ctx: dict) -> int:
    """Record the current price of each monitored purchase and detect drops. Returns new drops."""
    settings, store = get_settings(), get_store()
    watching = [p for p in await store.list_purchases(settings.demo_user_id) if p.status in ("monitoring", "drop_detected")]
    now, checked, drops = _now(), 0, 0
    for purchase in watching:
        if purchase.adjustment_window_ends and now > purchase.adjustment_window_ends:
            await store.save_purchase(purchase.model_copy(update={"status": "expired"}))
            await log_event(
                "price_checked",
                f"{purchase.retailer}'s price-adjustment window for {purchase.product_name} closed. Stopped monitoring.",
                purchase=purchase,
            )
            continue
        try:
            price = await price_feed.current_price_cents(purchase, store)
            await store.insert_price(purchase.product_id, purchase.retailer, price, source="poller")
        except Exception:
            logger.exception("Price check failed for %s", purchase.product_id)
            continue
        checked += 1
        last_seen = purchase.current_price_cents if purchase.current_price_cents is not None else purchase.price_paid_cents
        # A purchase already evaluated at this price (status drop_detected) only counts again if it falls further.
        new_drop = price < purchase.price_paid_cents and (purchase.status == "monitoring" or price < last_seen)
        if new_drop:
            await store.save_purchase(purchase.model_copy(update={"status": "drop_detected", "current_price_cents": price}))
            await log_event(
                "price_drop",
                f"Price drop: {purchase.product_name} fell from {money(purchase.price_paid_cents)} "
                f"to {money(price)} at {purchase.retailer}.",
                purchase=purchase,
            )
            await jobs.enqueue("evaluate_purchase", purchase.id)
            drops += 1
            continue
        status = "monitoring" if price >= purchase.price_paid_cents else purchase.status
        if price != purchase.current_price_cents or status != purchase.status:
            await store.save_purchase(purchase.model_copy(update={"status": status, "current_price_cents": price}))
    if checked and not drops:
        latest = await store.list_events(settings.demo_user_id, 1)
        quiet_check_is_latest = bool(latest) and latest[0].kind == "price_checked" and latest[0].purchase_id is None
        if not quiet_check_is_latest:  # one line in the feed, not one per poll
            await log_event(
                "price_checked", f"Checked prices on {checked} tracked purchase{'s' if checked != 1 else ''}. No new drops."
            )
    return drops


async def evaluate_purchase(ctx: dict, purchase_id: str) -> str | None:
    """Policy + eligibility for a detected drop. Drafts a claim when eligible. Returns the claim id."""
    if purchase_id in _evaluating:
        return None
    _evaluating.add(purchase_id)
    try:
        return await _evaluate(purchase_id)
    finally:
        _evaluating.discard(purchase_id)


async def _evaluate(purchase_id: str) -> str | None:
    store = get_store()
    purchase = await store.get_purchase(purchase_id)
    if purchase is None:
        return None
    current = purchase.current_price_cents
    if current is None:
        latest = await store.latest_price(purchase.product_id)
        if latest is None:
            return None
        current = latest.price_cents
    try:
        policy = await policy_for(purchase.retailer)
        result = await eligibility.check(purchase, current, policy)
    except Exception as exc:
        logger.exception("Eligibility check failed for %s", purchase_id)
        await log_event("error", f"Couldn't check eligibility for {purchase.product_name} ({type(exc).__name__}).", purchase=purchase)
        return None
    if not result.eligible:
        # Status stays drop_detected, so the poller only re-evaluates if the price falls further.
        await log_event("eligibility_checked", f"Not eligible: {purchase.product_name}. {result.reason}", purchase=purchase)
        return None

    window = f"{policy.window_days}-day " if policy.window_days is not None else ""
    await log_event(
        "eligibility_checked",
        f"Eligible: {money(result.refund_cents)} back on {purchase.product_name}, "
        f"inside {purchase.retailer}'s {window}price-adjustment window.",
        purchase=purchase,
    )
    try:
        explanation = await claim_writer.explain(purchase, result)
    except Exception:
        logger.exception("Couldn't write the claim explanation; using the eligibility reason")
        explanation = result.reason

    claims = await store.list_claims(purchase.user_id)
    if any(c.purchase_id == purchase.id and c.status in OPEN_CLAIM for c in claims):
        return None  # a claim for this purchase is already in progress
    claim = Claim(
        id=f"c-{uuid.uuid4().hex[:8]}", user_id=purchase.user_id, purchase_id=purchase.id,
        retailer=purchase.retailer, refund_cents=result.refund_cents, status="awaiting_approval",
        explanation=explanation, created_at=_now(),
    )
    await store.save_claim(claim)
    fresh = await store.get_purchase(purchase.id) or purchase
    await store.save_purchase(fresh.model_copy(update={"status": "claim_pending"}))
    await log_event(
        "claim_drafted",
        f"Drafted a {money(claim.refund_cents)} price-adjustment claim for {purchase.product_name}. "
        "Waiting for your approval.",
        purchase=purchase, claim=claim,
    )
    return claim.id


async def submit_claim(ctx: dict, claim_id: str) -> bool:
    """After approval: write the claim message, have the Playwright bot file it. Returns success."""
    settings, store = get_settings(), get_store()
    claim = await store.get_claim(claim_id)
    purchase = await store.get_purchase(claim.purchase_id) if claim else None
    if claim is None or purchase is None:
        logger.error("submit_claim: claim %s or its purchase is missing", claim_id)
        return False
    if claim.status != "submitting":  # only POST /claims/{id}/approve puts a claim here
        return False

    await log_event(
        "claim_submitting", f"Submitting your {money(claim.refund_cents)} claim to {claim.retailer}.",
        purchase=purchase, claim=claim,
    )
    try:
        approved = EligibilityResult(eligible=True, refund_cents=claim.refund_cents, reason=claim.explanation, confidence=1.0)
        message = await claim_writer.form_message(purchase, approved)
        shots = await claim_bot.submit(claim, purchase, message, screenshot_dir=SCREENSHOT_ROOT / claim.id)
    except Exception as exc:
        logger.exception("Claim %s failed", claim_id)
        shots = getattr(exc, "screenshots", None) or []
        reason = (str(exc).strip().splitlines() or [type(exc).__name__])[0][:160]
        if "ERR_CONNECTION_REFUSED" in str(exc):
            reason = f"the claim page at {settings.retailer_claim_url} isn't reachable. Is the frontend running?"
        await store.save_claim(claim.model_copy(update={"status": "failed"}))
        await store.save_purchase(purchase.model_copy(update={"status": "drop_detected"}))
        await log_event(
            "error", f"Couldn't submit the {claim.retailer} claim: {reason}",
            purchase=purchase, claim=claim, screenshot_url=_shot_url(shots[-1] if shots else None),
        )
        return False

    await store.save_claim(claim.model_copy(update={"status": "submitted", "submitted_at": _now()}))
    await log_event(
        "claim_submitted",
        f"Submitted your {money(claim.refund_cents)} claim to {claim.retailer}. Watching your bank for the refund.",
        purchase=purchase, claim=claim, screenshot_url=_shot_url(shots[-1] if shots else None),
    )
    if settings.demo_mode and settings.demo_refund_delay_seconds >= 0:
        # Our demo store has no payments backend, so the "retailer" pays here.
        await jobs.enqueue("issue_demo_refund", claim.id, defer_seconds=settings.demo_refund_delay_seconds)
    return True


async def issue_demo_refund(ctx: dict, claim_id: str) -> bool:
    """Demo only: the demo store refunds a submitted claim as a deposit on the bank account."""
    store = get_store()
    claim = await store.get_claim(claim_id)
    if claim is None or claim.status != "submitted":
        return False
    purchase = await store.get_purchase(claim.purchase_id)
    order = f" {purchase.order_number}" if purchase and purchase.order_number else ""
    try:
        await finance_gateway.issue_refund(claim.refund_cents, f"PRICE ADJUSTMENT {claim.retailer}{order} (claim {claim.id})")
    except Exception as exc:
        logger.exception("Demo refund failed for claim %s", claim_id)
        await log_event("error", f"The demo refund for {claim.retailer} didn't go through ({type(exc).__name__}).", claim=claim)
        return False
    await jobs.enqueue("reconcile_refunds")
    return True


def _match_deposit(claim: Claim, purchase: Purchase | None, deposits: list[BankTxn], used: set[str]) -> BankTxn | None:
    """The refund for a claim: an unclaimed deposit made since it was submitted, either naming the
    claim (or its order number) or of exactly the refund amount."""
    # One day of slack: the bank may date transactions in local time while we use UTC.
    since = claim.submitted_at.date() - timedelta(days=1) if claim.submitted_at else None
    recent = [d for d in deposits if d.id and d.id not in used and (since is None or d.date is None or d.date >= since)]
    references = [r.lower() for r in (claim.id, purchase.order_number if purchase else None) if r]
    for deposit in recent:
        # A deposit that names the claim only has to agree on the dollars: Nessie drops the cents.
        if _amount_matches(deposit.amount_cents, claim.refund_cents) and any(
            re.search(rf"(?<![\w-]){re.escape(ref)}(?![\w-])", deposit.description.lower()) for ref in references
        ):
            return deposit
    return next((d for d in recent if d.amount_cents == claim.refund_cents), None)


async def reconcile_refunds(ctx: dict) -> int:
    """Match bank deposits to submitted claims, then record each recovery in the Solana vault."""
    settings, store = get_settings(), get_store()
    claims = await store.list_claims(settings.demo_user_id)
    submitted = sorted((c for c in claims if c.status == "submitted"), key=lambda c: c.created_at)
    to_vault = [c for c in claims if c.status == "refund_received" and not c.solana_tx_signature]
    matched = 0

    if submitted:
        try:
            deposits = await finance_gateway.deposits()
        except Exception as exc:
            logger.warning("Couldn't read bank deposits (%s); will retry", type(exc).__name__)
            deposits = []
        used = {c.nessie_deposit_id for c in claims if c.nessie_deposit_id}
        for claim in submitted:
            purchase = await store.get_purchase(claim.purchase_id)
            deposit = _match_deposit(claim, purchase, deposits, used)
            if deposit is None:
                continue
            used.add(deposit.id)
            claim = claim.model_copy(
                update={"status": "refund_received", "refund_received_at": _now(), "nessie_deposit_id": deposit.id}
            )
            await store.save_claim(claim)
            if purchase:
                await store.save_purchase(purchase.model_copy(update={"status": "claimed"}))
            await log_event(
                "refund_received",
                f"Refund received: {money(claim.refund_cents)} from {claim.retailer} landed in your bank account.",
                purchase=purchase, claim=claim,
            )
            to_vault.append(claim)
            matched += 1

    for claim in to_vault:
        why_simulated = "Solana devnet wasn't reachable"
        try:
            signature = await finance_gateway.record_recovery(claim.user_id, claim.id, claim.refund_cents)
        except Exception as exc:
            if "no devnet SOL" in str(exc) or "No Solana keypair" in str(exc):
                why_simulated = "the backend's devnet wallet isn't set up or has no test SOL"
            attempts = _vault_failures.get(claim.id, 0) + 1
            _vault_failures[claim.id] = attempts
            logger.warning(
                "Vault record failed for claim %s, attempt %d (%s: %s)",
                claim.id, attempts, type(exc).__name__, str(exc)[:160],
            )
            if attempts < VAULT_ATTEMPTS:
                continue  # try again on the next run
            finance_gateway.mark_vault_down()  # simulate for a while, for this claim and the next ones
            signature = await finance_gateway.record_recovery(claim.user_id, claim.id, claim.refund_cents)
        _vault_failures.pop(claim.id, None)
        await store.save_claim(claim.model_copy(update={"solana_tx_signature": signature}))
        simulated = signature.startswith("sim-") and not settings.mock_mode
        note = f" This entry is simulated: {why_simulated}." if simulated else ""
        await log_event(
            "vault_recorded", f"Recorded {money(claim.refund_cents)} in your Solana savings vault.{note}", claim=claim
        )
    return matched


async def watch_policies(ctx: dict) -> dict:
    """Grok Bot: check each active retailer's policy page for changes and store what changed."""
    settings, store = get_settings(), get_store()
    purchases = await store.list_purchases(settings.demo_user_id)
    retailers = sorted({p.retailer for p in purchases if p.status not in ("expired", "claimed")})
    reviewed, changed, notes = 0, [], []
    for retailer in retailers:
        stored = await policy_for(retailer)
        if not stored.policy_url:
            continue
        result = await grok_bot.watch_policy(stored)  # never raises
        notes.append(f"{retailer}: {result.note}")
        if result.reviewed_by == "grok":
            reviewed += 1
        if result.changed:
            changed.append(retailer)
            await store.save_policy(result.policy)
            await log_event(
                "eligibility_checked",
                f"Grok policy watch: {retailer}'s price-adjustment policy changed. {result.note}",
                user_id=settings.demo_user_id,
            )
    if reviewed and not changed:
        await log_event(
            "eligibility_checked",
            f"Grok policy watch checked {reviewed} retailer polic{'ies' if reviewed != 1 else 'y'}: no changes.",
            user_id=settings.demo_user_id,
        )
    return {"retailers": retailers, "reviewed": reviewed, "changed": changed, "notes": notes}
