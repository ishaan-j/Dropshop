"""Background jobs (arq). Layer 2 owns orchestration; the heavy lifting lives in agents/, data/, finance/.

Each job: load state (data) → call agents/finance → persist results (data) → log an AgentEvent.
See docs/architecture.md for the job table.
"""


async def scan_new_purchases(ctx: dict, user_id: str) -> None:
    # TODO(L2):
    # 1. receipts = await agents.sentient.fetch_recent_receipts(since=...)  (fallback: sample receipts)
    # 2. for each: agents.receipt_extractor.extract(receipt) -> ExtractedReceipt
    # 3. match against finance.nessie.list_purchases(...) to confirm the charge
    # 4. data.mongo.upsert_purchase(...) + log "purchase_found" event
    ...


async def poll_prices(ctx: dict) -> None:
    # TODO(L2):
    # for each purchase with status == "monitoring":
    #   price = await services.fetch_current_price(purchase)   # or a simulated feed in demo mode
    #   await data.timescale.insert_price(...)
    #   if price < purchase.price_paid_cents and window open: enqueue evaluate_purchase
    ...


async def evaluate_purchase(ctx: dict, purchase_id: str) -> None:
    # TODO(L2):
    # policy = await agents.policy_reader.get_policy(retailer)
    # result = await agents.eligibility.check(purchase, current_price_cents, policy)
    # if result.eligible: claim = agents.claim_writer.draft(...); save; log "claim_drafted"
    ...


async def submit_claim(ctx: dict, claim_id: str) -> None:
    # TODO(L2): await agents.claim_bot.submit(claim, purchase) -> update status + log events/screenshots
    ...


async def reconcile_refunds(ctx: dict) -> None:
    # TODO(L2):
    # for each "submitted" claim: look for the refund via finance.nessie.list_deposits(...)
    # on match: status=refund_received; sig = await finance.solana_vault.record_recovery(...); log events
    ...
