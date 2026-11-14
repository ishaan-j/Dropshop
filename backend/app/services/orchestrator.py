"""Runs the four DropShop agents and persists their events.

Sentient OS is not this orchestrator. When a user opts in, the receipt agent
can read order-like notes from the Sentient OS knowledge folder. That read is
labeled as such. Agent runs recorded here are DropShop runs.
"""

from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timezone

from agents import claim_bot, claim_writer, eligibility, policy_reader, receipt_extractor
from agents.policy_reader import PolicyNotFound
from agents.sentient import knowledge_available, read_order_notes
from app.models import (
    AgentEvent,
    AgentName,
    AgentRun,
    Claim,
    DataOrigin,
    Purchase,
    ReceiptRecord,
    Refund,
    ScenarioResult,
    UserApproval,
)
from app.services.catalog import PRODUCTS, demo_emails, order_number
from app.services.rules import (
    adjustment_deadline,
    automation_permitted,
    can_transition,
    claim_reuse,
    duplicate_key,
    latest_market_point,
    price_difference_cents,
    submission_matches,
)
from data.repository import PersistenceError, repo
from finance import nessie
from integrations import gmail

_locks: dict[str, asyncio.Lock] = {}


class WorkflowError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    return prefix + secrets.token_hex(8)


def _lock(key: str) -> asyncio.Lock:
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    return _locks[key]


async def _emit(
    user_id: str,
    kind: str,
    message: str,
    *,
    agent: AgentName,
    run_id: str,
    origin: DataOrigin,
    purchase_id: str | None = None,
    claim_id: str | None = None,
    screenshot_url: str | None = None,
) -> AgentEvent:
    event = AgentEvent(
        id=_id("evt_"),
        user_id=user_id,
        time=_now(),
        kind=kind,  # type: ignore[arg-type]
        message=message,
        agent=agent,
        run_id=run_id,
        purchase_id=purchase_id,
        claim_id=claim_id,
        screenshot_url=screenshot_url,
        data_origin=origin,
    )
    return await repo.log_event(event)


async def _start(user_id: str, agent: AgentName, task: str, origin: DataOrigin) -> AgentRun:
    run = AgentRun(
        id=_id("run_"),
        user_id=user_id,
        agent=agent,
        status="running",
        task=task,
        started_at=_now(),
        data_origin=origin,
    )
    await repo.save_run(run)
    await _emit(user_id, "agent_started", task, agent=agent, run_id=run.id, origin=origin)
    return run


async def _finish(run: AgentRun, summary: str, *, error: str | None = None) -> AgentRun:
    run.status = "error" if error else "completed"
    run.finished_at = _now()
    run.result_summary = summary
    run.error = error
    return await repo.save_run(run)


async def run_receipt_agent(user_id: str, *, demo: bool = False) -> AgentRun:
    origin: DataOrigin = "demo" if demo else "live"
    run = await _start(
        user_id,
        "receipt",
        "Read demo sample emails." if demo else "Look for order confirmations.",
        origin,
    )
    try:
        sources = await _sources(user_id, demo=demo, run_id=run.id, origin=origin)
    except WorkflowError as exc:
        await _emit(user_id, "error", exc.message, agent="receipt", run_id=run.id, origin=origin)
        await _finish(run, exc.message, error=exc.message)
        raise
    created = 0
    skipped = 0
    for source in sources:
        receipt = ReceiptRecord(
            id=_id("rcp_"),
            user_id=user_id,
            source=source["source"],
            data_origin=source["origin"],
            external_id=source.get("external_id"),
            subject=source.get("subject"),
            body_text=source["body"],
            created_at=_now(),
        )
        await repo.save_receipt(receipt)
        await _emit(
            user_id,
            "email_discovered",
            f"Discovered a {source['label']} ({source.get('subject') or 'no subject'}).",
            agent="receipt",
            run_id=run.id,
            origin=source["origin"],
        )
        extracted = await receipt_extractor.extract(source["body"])
        for item in extracted.items:
            if item.missing_fields:
                skipped += 1
                await _emit(
                    user_id,
                    "error",
                    "Left a message unstored as a purchase. Missing: " + ", ".join(item.missing_fields) + ".",
                    agent="receipt",
                    run_id=run.id,
                    origin=source["origin"],
                )
                continue
            key = duplicate_key(
                item.retailer or "",
                item.product_name or "",
                item.order_number,
                item.price_paid_cents or 0,
                item.purchased_at or _now(),
            )
            if await _duplicate(user_id, key):
                skipped += 1
                await _emit(
                    user_id,
                    "decision",
                    f"Skipped a duplicate purchase for {item.product_name}.",
                    agent="receipt",
                    run_id=run.id,
                    origin=source["origin"],
                )
                continue
            purchase = await _purchase_from_item(user_id, item, source)
            await repo.save_purchase(purchase)
            created += 1
            await _emit(
                user_id,
                "purchase_found",
                f"Stored {purchase.product_name} from {purchase.retailer} "
                f"using the {extracted.extractor} extractor. Origin: {purchase.data_origin}.",
                agent="receipt",
                run_id=run.id,
                origin=purchase.data_origin,
                purchase_id=purchase.id,
            )
        if not extracted.items:
            skipped += 1
            await _emit(
                user_id,
                "decision",
                "No purchase extracted. " + " ".join(extracted.warnings),
                agent="receipt",
                run_id=run.id,
                origin=source["origin"],
            )
    summary = f"Stored {created} purchase(s). Skipped {skipped}."
    await _finish(run, summary)
    return run


async def _sources(user_id: str, *, demo: bool, run_id: str, origin: DataOrigin) -> list[dict]:
    if demo:
        return [
            {
                "source": "demo_sample",
                "origin": "demo",
                "label": "demo sample email, not Gmail",
                "subject": email["subject"],
                "body": email["body"],
                "external_id": email["product_id"],
            }
            for email in demo_emails(user_id)
        ]
    found: list[dict] = []
    prefs = await repo.get_preferences(user_id)
    if prefs.sentient_read_enabled:
        if not knowledge_available():
            await _emit(
                user_id,
                "error",
                "Sentient OS knowledge folder was not found, so no notes were read.",
                agent="receipt",
                run_id=run_id,
                origin="live",
            )
        else:
            for note in read_order_notes():
                found.append(
                    {
                        "source": "sentient_knowledge",
                        "origin": "live",
                        "label": "Sentient OS knowledge note",
                        "subject": note["path"],
                        "body": note["text"],
                        "external_id": note["path"],
                    }
                )
    view = await gmail.connection_view(user_id)
    if view["connected"]:
        try:
            messages = await gmail.list_order_messages(user_id)
        except gmail.GmailError as exc:
            raise WorkflowError(str(exc), 502) from exc
        for message in messages:
            found.append(
                {
                    "source": "gmail",
                    "origin": "live",
                    "label": "Gmail message",
                    "subject": message["subject"],
                    "body": message["text"],
                    "external_id": message["id"],
                }
            )
    if not found:
        raise WorkflowError(
            "Gmail is not connected and Sentient OS reading is off. "
            "Use the labeled demo scenario, or connect a source in Settings.",
            409,
        )
    return found


async def _duplicate(user_id: str, key: tuple[str, ...]) -> bool:
    for purchase in await repo.list_purchases(user_id):
        existing = duplicate_key(
            purchase.retailer,
            purchase.product_name,
            purchase.order_number,
            purchase.price_paid_cents,
            purchase.purchased_at,
        )
        if existing == key:
            return True
    return False


async def _purchase_from_item(user_id: str, item, source: dict) -> Purchase:
    facts = policy_reader.product_facts(item.product_id)
    now = _now()
    product_id = item.product_id or _slug(item.retailer or "item", item.product_name or "product")
    source_name = {"demo_sample": "demo_sample", "sentient_knowledge": "sentient", "gmail": "email"}.get(
        source["source"], "manual"
    )
    purchase = Purchase(
        id=_id("pur_"),
        user_id=user_id,
        retailer=item.retailer,
        product_name=item.product_name,
        product_url=item.product_url,
        product_id=product_id,
        price_paid_cents=item.price_paid_cents,
        purchased_at=item.purchased_at,
        order_number=item.order_number,
        source=source_name,  # type: ignore[arg-type]
        data_origin=source["origin"],
        final_sale=bool(facts and facts["final_sale"]),
        created_at=now,
        updated_at=now,
    )
    if purchase.retailer == "Harbor & Co":
        policy = await policy_reader.get_policy(purchase.retailer)
        if policy.window_days is not None:
            purchase.adjustment_window_ends = adjustment_deadline(purchase.purchased_at, policy.window_days)
            purchase.policy_url = policy.policy_url
    return purchase


def _slug(retailer: str, name: str) -> str:
    def part(value: str) -> str:
        return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")

    return f"{part(retailer)}:{part(name)}"[:80]


async def run_price_agent(user_id: str) -> AgentRun:
    purchases = await repo.list_purchases(user_id)
    origin: DataOrigin = "demo" if purchases and all(item.data_origin == "demo" for item in purchases) else "live"
    if any(item.data_origin == "demo" for item in purchases):
        origin = "demo"
    run = await _start(user_id, "price", "Check authorized price sources.", origin)
    checked = 0
    drops = 0
    for purchase in purchases:
        if purchase.status in {"claimed", "expired"}:
            continue
        facts = policy_reader.product_facts(purchase.product_id)
        point_origin: DataOrigin = "demo" if facts else purchase.data_origin
        if not facts:
            await repo.record_monitoring(
                {
                    "time": _now(),
                    "user_id": user_id,
                    "product_id": purchase.product_id,
                    "purchase_id": purchase.id,
                    "status": "no_source",
                    "detail": "No authorized price source for this product.",
                    "data_origin": purchase.data_origin,
                }
            )
            await _emit(
                user_id,
                "price_checked",
                f"No authorized price source for {purchase.product_name}. No price was invented.",
                agent="price",
                run_id=run.id,
                origin=purchase.data_origin,
                purchase_id=purchase.id,
            )
            continue
        checked += 1
        await _emit(
            user_id,
            "tool_invoked",
            f"Read the Harbor & Co demo catalog for {purchase.product_id}. This is not a live retailer price.",
            agent="price",
            run_id=run.id,
            origin="demo",
            purchase_id=purchase.id,
        )
        history = await repo.price_history(user_id, purchase.product_id, days=120)
        if not any(point.source == "purchase_record" for point in history):
            await repo.insert_price(
                _price_row(
                    purchase,
                    purchase.price_paid_cents,
                    "purchase_record",
                    "from_receipt",
                    purchase.purchased_at,
                )
            )
        await repo.insert_price(
            _price_row(purchase, facts["current_cents"], "demo_catalog", "recorded", _now())
        )
        await repo.record_monitoring(
            {
                "time": _now(),
                "user_id": user_id,
                "product_id": purchase.product_id,
                "purchase_id": purchase.id,
                "status": "observed",
                "detail": "demo_catalog",
                "data_origin": "demo",
            }
        )
        fresh = await repo.price_history(user_id, purchase.product_id, days=120)
        market = latest_market_point([point.model_dump() for point in fresh])
        purchase.current_price_cents = market["price_cents"] if market else None
        purchase.price_source = market["source"] if market else None
        purchase.price_observed_at = market["time"] if market else None
        purchase.final_sale = bool(facts["final_sale"])
        purchase.updated_at = _now()
        difference = price_difference_cents(purchase.price_paid_cents, purchase.current_price_cents or purchase.price_paid_cents)
        if difference > 0 and purchase.status == "monitoring":
            purchase.status = "drop_detected"
            drops += 1
            await repo.record_price_change(
                {
                    "time": _now(),
                    "user_id": user_id,
                    "product_id": purchase.product_id,
                    "purchase_id": purchase.id,
                    "retailer": purchase.retailer,
                    "previous_price_cents": purchase.price_paid_cents,
                    "new_price_cents": purchase.current_price_cents,
                    "delta_cents": -difference,
                    "source": "demo_catalog",
                    "data_origin": "demo",
                }
            )
            await _emit(
                user_id,
                "price_drop",
                f"Demo catalog price for {purchase.product_name} is lower by ${difference / 100:.2f}.",
                agent="price",
                run_id=run.id,
                origin="demo",
                purchase_id=purchase.id,
            )
        else:
            await _emit(
                user_id,
                "price_checked",
                f"Recorded a demo catalog price for {purchase.product_name}.",
                agent="price",
                run_id=run.id,
                origin=point_origin,
                purchase_id=purchase.id,
            )
        await repo.save_purchase(purchase)
    summary = f"Checked {checked} catalog product(s). Drops newly marked: {drops}."
    await _finish(run, summary)
    return run


def _price_row(purchase: Purchase, cents: int, source: str, status: str, when: datetime) -> dict:
    return {
        "time": when,
        "product_id": purchase.product_id,
        "retailer": purchase.retailer,
        "price_cents": cents,
        "in_stock": True,
        "source": source,
        "currency": "USD",
        "product_url": purchase.product_url,
        "availability": "demo_catalog" if source == "demo_catalog" else "receipt",
        "collection_status": status,
        "data_origin": "demo" if source in {"demo_catalog", "purchase_record"} and purchase.data_origin == "demo" else purchase.data_origin,
        "user_id": purchase.user_id,
        "purchase_id": purchase.id,
    }


async def run_eligibility_agent(user_id: str) -> AgentRun:
    purchases = await repo.list_purchases(user_id)
    run = await _start(user_id, "eligibility", "Evaluate retailer rules against verified prices.", "demo")
    for purchase in purchases:
        try:
            policy = await policy_reader.get_policy(purchase.retailer)
            await repo.save_policy(policy)
        except PolicyNotFound as exc:
            purchase.eligibility = "needs_review"
            purchase.eligibility_reason = str(exc)
            purchase.updated_at = _now()
            await repo.save_purchase(purchase)
            await _emit(
                user_id,
                "eligibility_checked",
                str(exc),
                agent="eligibility",
                run_id=run.id,
                origin=purchase.data_origin,
                purchase_id=purchase.id,
            )
            continue
        result = await eligibility.check(purchase, purchase.current_price_cents, policy)
        if result.needs_review:
            purchase.eligibility = "needs_review"
        elif result.eligible:
            purchase.eligibility = "eligible"
        else:
            purchase.eligibility = "ineligible"
        purchase.eligibility_reason = result.reason
        purchase.eligibility_evidence = result.evidence
        purchase.policy_url = policy.policy_url
        if policy.window_days is not None:
            purchase.adjustment_window_ends = adjustment_deadline(purchase.purchased_at, policy.window_days)
            if purchase.adjustment_window_ends < _now() and purchase.status not in {"claimed"}:
                purchase.status = "expired"
        purchase.updated_at = _now()
        await repo.save_purchase(purchase)
        await _emit(
            user_id,
            "decision",
            f"{purchase.product_name}: {purchase.eligibility}. {result.reason}",
            agent="eligibility",
            run_id=run.id,
            origin=purchase.data_origin,
            purchase_id=purchase.id,
        )
    await _finish(run, f"Evaluated {len(purchases)} purchase(s).")
    return run


async def prepare_claims(user_id: str) -> AgentRun:
    run = await _start(user_id, "claim", "Prepare claims for eligible purchases. Nothing is submitted.", "demo")
    prepared = 0
    for purchase in await repo.list_purchases(user_id):
        if purchase.eligibility != "eligible":
            continue
        existing = await repo.claims_for_purchase(user_id, purchase.id)
        latest = existing[0] if existing else None
        action = claim_reuse(latest.status if latest else None)
        if action == "block":
            await _emit(
                user_id,
                "decision",
                f"Did not open another claim for {purchase.product_name}.",
                agent="claim",
                run_id=run.id,
                origin=purchase.data_origin,
                purchase_id=purchase.id,
                claim_id=latest.id if latest else None,
            )
            continue
        policy = await policy_reader.get_policy(purchase.retailer)
        result = await eligibility.check(purchase, purchase.current_price_cents, policy)
        if not result.eligible:
            continue
        explanation, form_message, missing, source = await claim_writer.compose(purchase, result, policy)
        now = _now()
        if action == "reuse" and latest:
            claim = latest.model_copy(
                update={
                    "status": "awaiting_approval",
                    "refund_cents": result.refund_cents,
                    "explanation": explanation,
                    "explanation_source": source,
                    "manual_packet": form_message,
                    "missing_information": missing,
                    "price_paid_cents": purchase.price_paid_cents,
                    "current_price_cents": purchase.current_price_cents,
                    "submission_note": "Prepared again. Not submitted.",
                }
            )
        else:
            claim = Claim(
                id=_id("clm_"),
                user_id=user_id,
                purchase_id=purchase.id,
                retailer=purchase.retailer,
                product_name=purchase.product_name,
                refund_cents=result.refund_cents,
                price_paid_cents=purchase.price_paid_cents,
                current_price_cents=purchase.current_price_cents,
                status="awaiting_approval",
                explanation=explanation,
                explanation_source=source,  # type: ignore[arg-type]
                data_origin=purchase.data_origin,
                created_at=now,
                policy_url=policy.policy_url,
                evidence=result.evidence,
                missing_information=missing,
                manual_packet=form_message,
                submission_note="Prepared only. Waiting for your approval.",
            )
        await repo.save_claim(claim)
        purchase.status = "claim_pending"
        purchase.updated_at = now
        await repo.save_purchase(purchase)
        prepared += 1
        await _emit(
            user_id,
            "claim_drafted",
            f"Prepared a {purchase.data_origin} claim for {purchase.product_name}. Approval is required before submission.",
            agent="claim",
            run_id=run.id,
            origin=purchase.data_origin,
            purchase_id=purchase.id,
            claim_id=claim.id,
        )
        await _emit(
            user_id,
            "approval_required",
            f"Waiting for approval on {purchase.product_name}.",
            agent="claim",
            run_id=run.id,
            origin=purchase.data_origin,
            purchase_id=purchase.id,
            claim_id=claim.id,
        )
    await _finish(run, f"Prepared {prepared} claim(s). None were submitted.")
    return run


async def approve_claim(user_id: str, claim_id: str) -> tuple[Claim, bool, str]:
    async with _lock(claim_id):
        claim = await repo.get_claim(user_id, claim_id)
        if not claim:
            raise WorkflowError("Claim not found.", 404)
        if claim.status != "awaiting_approval":
            raise WorkflowError(f"This claim is {claim.status} and cannot be approved again.", 409)
        purchase = await repo.get_purchase(user_id, claim.purchase_id)
        if not purchase or purchase.eligibility != "eligible":
            raise WorkflowError("The purchase is no longer eligible, so nothing was submitted.", 409)
        await repo.save_approval(
            UserApproval(
                id=_id("apr_"),
                user_id=user_id,
                claim_id=claim.id,
                action="approve",
                created_at=_now(),
                detail="User approved submission.",
            )
        )
        if not automation_permitted(purchase.retailer):
            note = (
                f"DropShop does not automate {purchase.retailer}. "
                "A manual packet is saved on the claim. Nothing was submitted."
            )
            claim.submission_note = note
            claim.manual_packet = claim.manual_packet or claim.explanation
            await repo.save_claim(claim)
            return claim, False, note
        if not can_transition(claim.status, "submitting"):
            raise WorkflowError("Claim cannot move to submitting.", 409)
        claim.status = "submitting"
        claim.submission_note = "Submitting to the DropShop demo retailer."
        await repo.save_claim(claim)
        try:
            result = await claim_bot.submit(claim, purchase)
        except claim_bot.AutomationUnavailable as exc:
            claim.status = "awaiting_approval"
            note = f"Nothing was submitted. {exc}"
            claim.submission_note = note
            await repo.save_claim(claim)
            await _emit(
                user_id,
                "error",
                note,
                agent="claim",
                run_id=claim.id,
                origin=claim.data_origin,
                purchase_id=purchase.id,
                claim_id=claim.id,
            )
            return claim, False, note
        submission = await repo.get_demo_submission(result["submission_id"])
        if not submission or not submission.get("accepted"):
            claim.status = "awaiting_approval"
            note = "The demo retailer did not keep a matching submission. Nothing was marked submitted."
            claim.submission_note = note
            await repo.save_claim(claim)
            return claim, False, note
        claim.status = "submitted"
        claim.submitted_at = _now()
        claim.demo_submission_id = result["submission_id"]
        claim.screenshots = result["screenshots"]
        claim.submission_note = (
            "Submitted to the DropShop demo retailer only. This was not sent to a live merchant."
        )
        await repo.save_claim(claim)
        purchase.status = "claimed"
        purchase.updated_at = _now()
        await repo.save_purchase(purchase)
        shot = f"/claims/{claim.id}/screenshots/{result['screenshots'][-1]}" if result["screenshots"] else None
        await _emit(
            user_id,
            "claim_submitted",
            claim.submission_note,
            agent="claim",
            run_id=claim.id,
            origin="demo",
            purchase_id=purchase.id,
            claim_id=claim.id,
            screenshot_url=shot,
        )
        return claim, True, claim.submission_note


async def reject_claim(user_id: str, claim_id: str) -> Claim:
    claim = await repo.get_claim(user_id, claim_id)
    if not claim:
        raise WorkflowError("Claim not found.", 404)
    if claim.status != "awaiting_approval":
        raise WorkflowError("Only a claim waiting for approval can be rejected.", 409)
    claim.status = "rejected"
    claim.submission_note = "You rejected this claim. Nothing was submitted."
    await repo.save_claim(claim)
    await repo.save_approval(
        UserApproval(
            id=_id("apr_"),
            user_id=user_id,
            claim_id=claim.id,
            action="reject",
            created_at=_now(),
            detail=claim.submission_note,
        )
    )
    return claim


async def receive_demo_submission(body: dict) -> dict:
    cents = _dollars_to_cents(body.get("refund_amount", ""))
    paid = _dollars_to_cents(body.get("price_paid", ""))
    order_number = (body.get("order_number") or "").strip()
    matches = []
    for claim in await repo.claims_by_status("submitting"):
        purchase = await repo.get_purchase(claim.user_id, claim.purchase_id)
        if not purchase:
            continue
        if submission_matches(claim.status, purchase.order_number, claim.refund_cents, {
            "order_number": order_number,
            "refund_cents": cents,
        }) and paid == purchase.price_paid_cents:
            matches.append((claim, purchase))
    if len(matches) != 1:
        return {"id": None, "accepted": False, "detail": "No single in-progress demo claim matched this form."}
    claim, _purchase = matches[0]
    submission_id = _id("sub_")
    record = {
        "id": submission_id,
        "accepted": True,
        "claim_id": claim.id,
        "user_id": claim.user_id,
        "order_number": order_number,
        "refund_cents": cents,
        "created_at": _now().isoformat(),
    }
    await repo.save_demo_submission(record)
    return {"id": submission_id, "accepted": True, "detail": "Demo retailer stored the form. This is not a live merchant."}


def _dollars_to_cents(raw: str) -> int | None:
    try:
        return int(round(float(raw) * 100))
    except (TypeError, ValueError):
        return None


async def record_demo_refund(user_id: str, claim_id: str) -> Refund:
    claim = await repo.get_claim(user_id, claim_id)
    if not claim:
        raise WorkflowError("Claim not found.", 404)
    if claim.status != "submitted":
        raise WorkflowError("Record a refund only after a claim is submitted.", 409)
    refund = Refund(
        id=_id("ref_"),
        user_id=user_id,
        claim_id=claim.id,
        amount_cents=claim.refund_cents,
        status="matched",
        data_origin="demo",
        source="demo_ledger",
        external_id=None,
        explanation="Recorded in the DropShop demo ledger. No bank and no Nessie deposit was created.",
        created_at=_now(),
    )
    await repo.save_refund(refund)
    claim.status = "refund_received"
    claim.refund_received_at = _now()
    claim.nessie_deposit_id = None
    await repo.save_claim(claim)
    await _emit(
        user_id,
        "refund_received",
        refund.explanation,
        agent="claim",
        run_id=claim.id,
        origin="demo",
        claim_id=claim.id,
        purchase_id=claim.purchase_id,
    )
    return refund


async def reconcile_nessie(user_id: str, claim_id: str) -> Refund:
    if not nessie.configured():
        raise WorkflowError("Nessie is not connected.", 409)
    settings_account = (await repo.get_connection(user_id)).get("nessie_account_id") or ""
    from app.config import get_settings

    account_id = settings_account or get_settings().nessie_account_id
    if not account_id:
        raise WorkflowError("No Nessie sandbox account id is saved.", 409)
    claim = await repo.get_claim(user_id, claim_id)
    if not claim or claim.status != "submitted":
        raise WorkflowError("Only a submitted claim can be reconciled.", 409)
    try:
        created = await nessie.create_deposit(
            account_id,
            claim.refund_cents,
            f"Sandbox price-adjustment marker dropshop-claim:{claim.id}",
        )
        deposits = await nessie.list_deposits(account_id)
    except nessie.NessieError as exc:
        raise WorkflowError(str(exc), 502) from exc
    used = {refund.external_id for refund in await repo.list_refunds(user_id) if refund.external_id}
    from app.services.rules import explain_unmatched, match_deposit

    matched = match_deposit(claim.refund_cents, claim.id, deposits, used)
    if not matched:
        explanation = explain_unmatched(claim.refund_cents, claim.id, deposits)
        refund = Refund(
            id=_id("ref_"),
            user_id=user_id,
            claim_id=claim.id,
            amount_cents=claim.refund_cents,
            status="unmatched",
            data_origin="sandbox",
            source="nessie",
            external_id=str(created.get("_id") or "") or None,
            explanation=explanation + " The claim was not marked refunded.",
            created_at=_now(),
        )
        await repo.save_refund(refund)
        return refund
    external_id = str(matched.get("_id") or matched.get("id"))
    refund = Refund(
        id=_id("ref_"),
        user_id=user_id,
        claim_id=claim.id,
        amount_cents=claim.refund_cents,
        status="matched",
        data_origin="sandbox",
        source="nessie",
        external_id=external_id,
        explanation=(
            f"Matched Nessie sandbox deposit {external_id}. "
            "This is sandbox data, not a deposit from a retailer into a real bank account."
        ),
        created_at=_now(),
    )
    await repo.save_refund(refund)
    claim.status = "refund_received"
    claim.refund_received_at = _now()
    claim.nessie_deposit_id = external_id
    await repo.save_claim(claim)
    await _emit(
        user_id,
        "refund_received",
        refund.explanation,
        agent="claim",
        run_id=claim.id,
        origin="sandbox",
        claim_id=claim.id,
        purchase_id=claim.purchase_id,
    )
    return refund


async def run_demo_scenario(user_id: str) -> ScenarioResult:
    from app.config import get_settings

    if not get_settings().mock_mode:
        raise WorkflowError("The demo scenario is disabled because MOCK_MODE is false.", 403)
    await repo.delete_demo_for_user(user_id)
    await run_receipt_agent(user_id, demo=True)
    await run_price_agent(user_id)
    await run_eligibility_agent(user_id)
    await prepare_claims(user_id)
    note = (
        "Demo scenario. These are sample emails and Harbor & Co catalog prices, "
        "not your Gmail and not a live retailer. Claims are prepared and not submitted."
    )
    return ScenarioResult(
        note=note,
        purchases=await repo.list_purchases(user_id),
        claims=await repo.list_claims(user_id),
        events=await repo.list_events(user_id, limit=40),
    )


def known_product_ids() -> list[str]:
    return list(PRODUCTS)


def catalog_order(product_id: str, user_id: str) -> str:
    return order_number(product_id, user_id)
