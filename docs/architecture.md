# Architecture

## Layer boundaries (who calls whom)

```
frontend (L1) ──HTTP──▶ backend/app (L2: routers + workers)
                              │
          ┌───────────────────┼────────────────────┬──────────────────┐
          ▼                   ▼                    ▼                  ▼
  backend/agents (L3)   backend/data (L4)   backend/finance (L5)   solana/ (L5)
  Gemini, Sentient,     Mongo + Timescale   Nessie client,         Anchor program
  Playwright bot        repositories        Solana client ───────▶ (devnet)
```

Rules:

- **Only L2 orchestrates.** Routers and workers call into agents, data and finance. Those three packages never import each other, and they never import `app.routers`.
- **Agents are pure-ish.** They take Pydantic models in and return Pydantic models out, and they don't write to the database. L2 persists the results.
- **Every external call has a mock.** Check `settings.mock_mode` (or a per-integration flag) and return canned data, so the demo survives flaky Wi-Fi.

## Background jobs (Redis + arq), in `backend/app/workers/`

| Job | Trigger | Does |
|---|---|---|
| `scan_new_purchases` | nightly cron + `POST /purchases/scan` | Sentient OS / email → `agents.receipt_extractor` → match to Nessie transaction → save purchase |
| `poll_prices` | hourly cron (every minute in demo mode) | Fetch the current price for each `monitoring` purchase → write to Timescale → detect drops |
| `evaluate_purchase` | enqueued on drop | `agents.policy_reader` + `agents.eligibility` → if eligible, `agents.claim_writer` drafts a claim (`awaiting_approval`) |
| `submit_claim` | `POST /claims/{id}/approve` | `agents.claim_bot` (Playwright) submits on the retailer site, with screenshots logged to the activity feed |
| `reconcile_refunds` | every few minutes | Watch Nessie deposits for the refund → mark `refund_received` → record in the Solana vault |

## Demo script (aim for 3 minutes)

1. Dashboard shows the monitored purchases and the savings so far.
2. Trigger `/purchases/scan`. A new purchase appears, discovered from a receipt.
3. Hero product: the price chart shows a drop (seeded) and the activity feed says "Eligible: $40 back".
4. Click **Approve**. Show the bot filling in the claim form live (on our own **mock retailer page** so anti-bot measures can't break the demo).
5. The refund deposit appears via Nessie, the Solana vault balance ticks up, and the Explorer link proves it's on-chain.

## Known risks

- **Retailer anti-bot**: real sites will block Playwright. Demo against a mock retailer page and describe real retailers as next steps.
- **Sentient OS** is an on-device Mac app (open source, AGPL-3.0), not a cloud API. Confirm with the sponsor what counts as an integration, and keep a Gmail/sample-receipt fallback.
- **Nessie** can be slow or down. Cache the seeded accounts and have a mock fallback.
