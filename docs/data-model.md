# Data model

Owner: Layer 4 (Database). Field names match `backend/app/models.py`.

The runtime schema is created by `backend/data/repository.py` on connect. Demo purchases are Harbor & Co catalog rows with `data_origin: "demo"`. Do not seed invented prices for other retailers.

Price rows include `source`, `data_origin`, `user_id`, and `collection_status`. A `purchase_record` row is the receipt price, not a market observation.

## MongoDB Atlas (application state)

| Collection | Holds | Key indexes |
|---|---|---|
| `users` | `{_id, name, email, nessie_customer_id, nessie_account_id, solana_wallet}` | `_id` |
| `purchases` | `Purchase` documents plus raw receipt metadata (`receipt: {...}`) | `(user_id, purchased_at desc)`, `(status)`, `(product_id)` |
| `retailer_policies` | `{retailer, policy_url, window_days, conditions, raw_text, summarized_at}`, cached Gemini policy reads | `retailer` unique |
| `claims` | `Claim` documents | `(user_id, created_at desc)`, `(purchase_id)`, `(status)` |
| `agent_events` | `AgentEvent` documents (activity feed and agent logs) | `(user_id, time desc)` |

## Tiger Data / TimescaleDB (time series)

See `backend/data/migrations/001_timescale_init.sql`.

- **`price_observations`** (hypertable on `time`): `(time, product_id, retailer, price_cents, in_stock, source)`. Every price check writes one row.
- **`price_daily`** (continuous aggregate): daily min/max/last price per product. Feeds the history chart and drop detection.

### Drop detection rule (v1)

A purchase has a drop when `latest price_cents < purchase.price_paid_cents` **and** `now <= purchase.adjustment_window_ends`. Gemini then confirms eligibility against the retailer's policy.

## Demo seed data

`backend/data/seed.py` should create the following:

- 1 demo user with a Nessie customer and checking account
- ~5 purchases across 3 retailers, at least one with a guaranteed price drop inside its window
- 30 days of synthetic price history per product, with a visible drop on the hero product
