# Architecture

DropShop is a Next.js app and a FastAPI service. The browser never holds API keys, OAuth tokens, or a wallet secret.

```
browser ──session token──▶ FastAPI
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
         rules engine     repositories     integrations
         (eligibility)    Mongo or memory  Gemini, Gmail,
                          Timescale or     Nessie, Solana
                          memory prices    Devnet, Playwright
```

Agents do not write the database. The orchestrator in `backend/app/services/orchestrator.py` calls them and stores the results. Every stored event has a time, an agent, and a `data_origin` of `demo`, `live`, or `sandbox`.

## Agents

| Agent | Does | Does not |
|---|---|---|
| Receipt | Reads Gmail, opted-in Sentient notes, or explicit demo emails. Extracts fields. Drops anything not in the source text. | Invent a price, date, or retailer. |
| Price | Reads the Harbor & Co demo catalog for products it knows. Writes an observation with a source. | Scrape an unverified retailer or copy the receipt price forward as a new market price. |
| Eligibility | Applies the policy window, exclusions, and the verified price. | Let a model override the rule result. |
| Claim | Writes a packet from verified numbers. Submits only after approval, and only to the in-app demo retailer. | Open Best Buy, Target, Amazon, or any other live site. |

Sentient OS keeps a Markdown knowledge base at `~/Sentient OS - Knowledge Base` ([project README](https://github.com/Sentient-OS-Labs/sentient-os)). DropShop can read order-like notes from that folder after an opt-in. That is the integration the docs support. There is no Sentient orchestration SDK in use, and DropShop does not label its own runs as Sentient runs.

## Data

Mongo collections, created on connect: `users`, `purchases`, `receipts`, `retailer_policies`, `claims`, `refunds`, `agent_runs`, `agent_events`, `user_approvals`, `savings_allocations`, `notification_preferences`, `integration_connections`, `demo_submissions`.

Timescale tables, created on connect: `price_observations`, `price_change_events`, `monitoring_events`. `price_observations` is a hypertable when the Timescale extension is present. Recent prices are read from the raw table so a continuous aggregate delay cannot hide a new observation.

A `purchase_record` observation is the price printed on the receipt. Drop detection uses the latest observation whose source is not `purchase_record`.

## Money

Potential difference = price paid − current verified price, and only when that number is positive.

Eligibility also requires a known window that is still open, a price source, and no Final Sale flag. The result is a potential difference. A refund record is created only from a matched Nessie sandbox deposit or from an explicit demo-ledger action. Those two sources are labeled differently.

A Solana transfer is a third step. The user signs it in their wallet. The API marks it confirmed only after Devnet `getTransaction` shows the vault balance increased. The RPC URL must contain `devnet`.

## Demo retailer

Harbor & Co is a site this API serves under `/demo/retailer`. Its policy text is the source the parser reads (`Window: 14 days`, Final Sale excluded). Its catalog prices are the only prices the price agent will record. Playwright, when installed, fills `/demo/retailer/claim`. The form posts back to the API. The claim is marked submitted only if that post matched a claim already in `submitting`.

## Security boundary

- Gemini, Nessie, Mongo, Gmail, and the session secret stay in the API process.
- Gmail scope is `gmail.readonly`.
- Wallet private keys are never accepted.
- Screenshot paths cannot leave the claim's own files.
- Errors are scrubbed of connection strings and bearer tokens.
- One user cannot read another's purchases. The demo scenario resets only that user's demo rows.

## What is optional

Redis and arq can run the same functions on a schedule. The API does not need them. Docker Compose can start Redis, TimescaleDB, and local Mongo. The app still runs with none of them.
