# API contract

Base URL: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). Interactive docs: `/docs`.

Money is integer cents. Times are ISO-8601 UTC. Records include `data_origin`: `demo`, `live`, or `sandbox`.

Send `Authorization: Bearer <token>` from `POST /auth/session`. The browser stores that token in `sessionStorage`.

| Method | Path | Notes |
|---|---|---|
| GET | `/health`, `/ready` | Public liveness |
| POST | `/auth/session` | Creates a user id and token |
| GET | `/dashboard` | Totals from stored records |
| GET | `/purchases`, `/purchases/{id}` | This user's purchases |
| POST | `/purchases` | Manual add. No price is invented. |
| POST | `/purchases/scan` | Gmail or opted-in Sentient notes. 409 if neither is available. |
| POST | `/demo/scenario` | Labeled Harbor & Co demo. Refused when `MOCK_MODE=false`. |
| GET | `/prices/{product_id}?days=` | Observations for this user |
| GET | `/opportunities` | Eligibility decisions |
| GET | `/claims` | |
| POST | `/claims/{id}/approve` | Returns `{claim, submitted, note}`. Does not mark submitted if the browser did not finish. |
| POST | `/claims/{id}/reject` | |
| GET | `/activity?limit=` | Stored agent events |
| GET | `/agents`, `/agents/runs` | Snapshots from stored runs |
| POST | `/agents/{receipt,price,eligibility}/run` | Runs that agent |
| POST | `/agents/claims/prepare` | Drafts claims. Does not submit. |
| GET | `/agents/stream?token=` | Server-sent events |
| GET | `/savings` | Recovered totals. Vault lamports are null until Devnet verifies them. |
| GET | `/integrations` | Mode and detail per service |
| GET/PUT | `/preferences` | Notification flags are stored. Delivery stays `not_connected`. |
| GET | `/integrations/gmail/start` | OAuth URL, or 409 |
| POST | `/integrations/gmail/disconnect` | Revokes when Google accepts it |
| POST | `/integrations/nessie/sandbox-account` | Creates sandbox customer and account |
| GET | `/integrations/nessie/transactions` | Sandbox purchases and deposits |
| POST | `/refunds/{id}/demo` | Demo ledger only |
| POST | `/refunds/{id}/nessie` | Creates a sandbox deposit, then matches it by marker |
| GET/POST | `/vault`, `/vault/wallet`, `/vault/confirm`, `/vault/demo-allocation` | Devnet verify vs labeled earmark |
| GET | `/demo/retailer/...` | Public demo store. Not a live merchant. |

Purchase status: `monitoring`, `drop_detected`, `claim_pending`, `claimed`, `expired`.

Claim status: `awaiting_approval`, `submitting`, `submitted`, `refund_received`, `rejected`, `failed`.
