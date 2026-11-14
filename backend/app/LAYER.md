# Layer 2: Backend

**Owner:** _TBD_ · **Stack:** Python, FastAPI, Redis + arq background workers

## You own
- API endpoints (`routers/`). The contract is in [`docs/api-contract.md`](../../docs/api-contract.md).
- Background jobs and scheduling (`workers/`): overnight scans, price polling, claim submission, refund reconciliation
- **Orchestration.** You're the only layer that calls agents (L3), data (L4) and finance (L5) together.
- Claim lifecycle and the `AgentEvent` log that drives the activity feed

## Setup
See [`backend/README.md`](../README.md). Swagger UI at `http://localhost:8000/docs`.
Tests: `python -m pytest app` from `backend/` (offline; the claim-submission tests need `playwright install chromium`).

## How it fits together
| File | Job |
|---|---|
| `store.py` | Where state lives. `MemoryStore` (demo data in this process) or `DbStore` (Mongo + Tiger Data through `backend/data`). Routers and jobs only talk to the store. |
| `mock_data.py` | The demo seed: purchases, claims, activity, price history, simulated bank ledger. |
| `jobs.py` | `enqueue(job, *args)`. Pushes to arq/Redis, or runs the job inside the API process. |
| `scheduler.py` | In-process timer for the periodic jobs, used when jobs run inside the API. |
| `workers/tasks.py` | The jobs (table below). |
| `workers/worker.py` | arq `WorkerSettings`: job list and cron schedule. |
| `price_feed.py` | Current price of a product: read from its page when the purchase has a `product_url` (live mode), otherwise the last recorded price. |
| `finance_gateway.py` | Bank (Nessie) and Solana vault calls, with a simulated fallback. |
| `routers/` | The REST endpoints, plus `/demo/*` controls and `/automations/*` for an outside automation. |

### Jobs
| Job | Runs | Does |
|---|---|---|
| `scan_new_purchases` | nightly, `POST /purchases/scan` | receipts → `receipt_extractor` → skip purchases already tracked → match a card charge → save |
| `poll_prices` | every minute in demo mode, else hourly | record each monitored price, expire closed windows, detect drops → `evaluate_purchase` |
| `evaluate_purchase` | on a drop | `policy_reader` + `eligibility` → draft a claim (`awaiting_approval`) with `claim_writer` |
| `submit_claim` | `POST /claims/{id}/approve` | `claim_writer` message (drafted by Grok) → `claim_bot` files it, screenshots served under `/screenshots` |
| `issue_demo_refund` | demo mode, a few seconds after submission | the demo store "pays": a deposit on the bank account |
| `reconcile_refunds` | every 5–10 s in demo mode, else every 5 min | match deposits to submitted claims → `refund_received` → record in the Solana vault |
| `watch_policies` | nightly, `POST /demo/jobs/watch_policies` | Grok (xAI API) checks retailer policy pages and stores what changed |

### Which backend is used
`GET /health` reports all of this.
- **State.** `DATA_BACKEND=auto` (default): in-memory while `MOCK_MODE=true`, and also while Layer 4's
  functions still raise `NotImplementedError`. Once Layer 4 lands, `MOCK_MODE=false` uses the database. `db` forces it.
- **Jobs.** With in-memory state the API runs every job itself (a separate worker couldn't see the data), so
  no Redis or worker is needed. With the database, jobs go to Redis and `arq app.workers.worker.WorkerSettings`
  runs them; if Redis is unreachable the API runs them itself.
- **Bank and vault.** Simulated while `MOCK_MODE=true`, otherwise Nessie and Solana devnet. In live mode the
  simulation still covers failures: a refund Nessie won't take is paid by the simulated bank (`nessie+simulated`),
  and after 3 failed vault writes the records are simulated for 5 minutes (`solana+simulated`), with the reason
  in the activity feed.

## Demo controls (`DEMO_MODE=true`)
- `POST /demo/reset`: stop running jobs and reseed (in-memory store only).
- `POST /demo/price-drop`: drop a monitored product's price now. Body is optional: `{purchase_id, percent, new_price_cents}`.
- `POST /demo/jobs/{name}`: run `scan_new_purchases`, `poll_prices`, `reconcile_refunds` or `watch_policies` now.

## Status
- [x] Mock mode works end to end, and its numbers are computed from the seed (savings match the claims)
- [x] arq queue wired: `POST /purchases/scan` and `POST /claims/{id}/approve` enqueue jobs
- [x] `poll_prices` with a simulated feed and an on-cue drop
- [x] `evaluate_purchase` → `submit_claim` → `reconcile_refunds` against the L3/L4/L5 interfaces
- [x] Routers go through the store, so they use `data.mongo` / `data.timescale` as soon as L4 implements them
- [x] `POST /demo/reset`

## Automation endpoint
`POST /automations/policy-page` lets an outside automation (a Grok Bot routine) submit a retailer's policy page
for review. It needs `Authorization: Bearer <AUTOMATION_TOKEN>` and is off while that setting is empty.

## Open items
- **L4**: implement `data/mongo.py` and `data/timescale.py`. Nice to have: `mongo.get_claim(claim_id)` and
  `mongo.get_policy(retailer)` / `save_policy(policy)` for `retailer_policies`. Without them, claims are found by
  listing and retailer policies are cached per process. `data/seed.py` can load `app.mock_data.build_seed()`.
- **Redis and the worker** have only been run against an in-memory fake Redis. They matter once L4 is in.
- **Prices:** the demo purchases have no `product_url`, so they only move through `POST /demo/price-drop`.
  A purchase added with a URL is read from the retailer's page, where the retailer allows it.
