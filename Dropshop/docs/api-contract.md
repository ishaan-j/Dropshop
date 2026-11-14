# API contract (Frontend ↔ Backend)

Base URL: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). Interactive docs: `/docs`.
Hackathon scope: one hardcoded user (`DEMO_USER_ID`), no auth.
Shapes come from `backend/app/models.py` and are mirrored in `frontend/src/types/index.ts`. **Change both together.**
Money is always **integer cents** (`*_cents`). Times are ISO-8601 UTC.

| Method | Path | Returns | Notes |
|---|---|---|---|
| GET | `/health` | `{status}` | Liveness check for deploys |
| GET | `/purchases` | `Purchase[]` | Purchases being monitored, newest first |
| GET | `/purchases/{id}` | `Purchase` | |
| POST | `/purchases` | `Purchase` | Manual add (body: `PurchaseCreate`), the fallback if email discovery fails |
| POST | `/purchases/scan` | `{job_id}` | Enqueue a Sentient OS / email scan for new purchases |
| GET | `/prices/{product_id}?days=30` | `PricePoint[]` | Price history for the chart (from Tiger Data) |
| GET | `/claims` | `Claim[]` | All claims, newest first |
| POST | `/claims/{id}/approve` | `Claim` | User approves, which enqueues the Playwright submission |
| POST | `/claims/{id}/reject` | `Claim` | |
| GET | `/activity?limit=50` | `AgentEvent[]` | AI activity feed ("Found price drop on…", "Submitting claim…") |
| GET | `/savings` | `SavingsSummary` | Totals plus the Solana vault balance and address |

## Status lifecycles

**Purchase.status**: `monitoring` → `drop_detected` → `claim_pending` → `claimed`. It can also go to `expired` when the adjustment window closes.

**Claim.status**: `awaiting_approval` → `submitting` → `submitted` → `refund_received`. It can also end as `rejected` (by the user or the retailer) or `failed` (the bot errored).

## Polling vs. push

Start with polling `/activity` and `/claims` every ~3s on the dashboard. Upgrade to SSE/WebSocket only if there's time.
