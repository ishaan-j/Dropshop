# API contract (Frontend ↔ Backend)

Base URL: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). Interactive docs: `/docs`.
Hackathon scope: one hardcoded user (`DEMO_USER_ID`), no auth.
Shapes come from `backend/app/models.py` and are mirrored in `frontend/src/types/index.ts`. **Change both together.**
Money is always **integer cents** (`*_cents`). Times are ISO-8601 UTC.

| Method | Path | Returns | Notes |
|---|---|---|---|
| GET | `/health` | `{status, mock_mode, store, jobs, bank, vault, gemini, grok}` | Liveness check for deploys, plus which backends are live or simulated (`BackendStatus` in the frontend) |
| GET | `/purchases` | `Purchase[]` | Purchases being monitored, newest first |
| GET | `/purchases/{id}` | `Purchase` | |
| POST | `/purchases` | `Purchase` | Manual add (body: `PurchaseCreate`), the fallback if email discovery fails |
| POST | `/purchases/scan` | `{job_id}` | Enqueue a Sentient OS / email scan for new purchases. Results arrive in `/purchases` and `/activity` |
| GET | `/prices/{product_id}?days=30` | `PricePoint[]` | Daily price history for the chart, oldest first (from Tiger Data) |
| GET | `/claims` | `Claim[]` | All claims, newest first |
| POST | `/claims/{id}/approve` | `Claim` | User approves. Returns the claim as `submitting` and enqueues the Playwright submission. A `failed` claim can be approved again to retry; any other status is returned unchanged |
| POST | `/claims/{id}/reject` | `Claim` | Only from `awaiting_approval` (otherwise 409) |
| GET | `/activity?limit=50` | `AgentEvent[]` | AI activity feed ("Found price drop on…", "Submitting claim…") |
| GET | `/savings` | `SavingsSummary` | Totals computed from the claims, plus the Solana vault balance and address |
| GET | `/policies/{retailer}` | `RetailerPolicy` | The price-adjustment policy in use for a retailer. `window_days: null` when none is known |
| GET | `/screenshots/{claim_id}/{file}.png` | image | Claim-bot screenshots. `AgentEvent.screenshot_url` holds the full URL |
| POST | `/demo/reset` | `{status, purchases, claims}` | Reseed the demo state (in-memory store only) |
| POST | `/demo/price-drop` | `{purchase_id, product_name, old_price_cents, new_price_cents, job_id}` | Drop a monitored product's price now. Optional body: `{purchase_id, percent, new_price_cents}` |
| POST | `/demo/jobs/{name}` | `{job, job_id}` or `{job, result}` | Run `scan_new_purchases`, `poll_prices`, `reconcile_refunds` or `watch_policies` now |

| POST | `/automations/policy-page` | `{retailer, changed, note, window_days, reviewed_by}` | For an outside automation (a Grok Bot routine): review a policy page. Body `{retailer, page_text, source_url?}`, header `Authorization: Bearer <AUTOMATION_TOKEN>` |

`/demo/*` exists only when `DEMO_MODE=true`. `/automations/*` answers 503 until `AUTOMATION_TOKEN` is set.
A 501 means the endpoint needs a backend layer that isn't implemented yet.

`health.bank` is `simulated`, `nessie` or `nessie+simulated`; `health.vault` is `simulated`, `solana` or
`solana+simulated`. The `+simulated` forms mean the live system failed and the simulation is covering.
A vault signature that starts with `sim-` is a simulated entry, not a devnet transaction.

## Status lifecycles

**Purchase.status**: `monitoring` → `drop_detected` → `claim_pending` → `claimed`. It can also go to `expired` when the adjustment window closes. A purchase stays at (or returns to) `drop_detected` when the drop isn't eligible, or its claim was rejected or failed; a new claim is drafted only if the price falls further.

**Claim.status**: `awaiting_approval` → `submitting` → `submitted` → `refund_received`. It can also end as `rejected` (by the user or the retailer) or `failed` (the bot errored).

## Polling vs. push

Everything after a request (scan results, drafted claims, submission, refund, vault record) happens in background jobs, so the frontend polls: once the backend answers `GET /health` it re-reads it every 4 s (`startBackendSync` in `frontend/src/lib/services.ts`). With `NEXT_PUBLIC_DATA_MODE=auto` (the default) the frontend uses the backend whenever it's running and its in-browser demo data otherwise. Upgrade to SSE/WebSocket only if there's time.
