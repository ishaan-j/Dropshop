# Layer 2: Backend

**Owner:** _TBD_ · **Stack:** Python, FastAPI, Redis + arq background workers

## You own
- API endpoints (`routers/`). The contract is in [`docs/api-contract.md`](../../docs/api-contract.md).
- Background jobs and scheduling (`workers/`): overnight scans, price polling, claim submission, refund reconciliation
- **Orchestration.** You're the only layer that calls agents (L3), data (L4) and finance (L5) together.
- Claim lifecycle and the `AgentEvent` log that drives the activity feed

## Setup
See [`backend/README.md`](../README.md). Swagger UI at `http://localhost:8000/docs`.

## First tasks
- [ ] Keep mock mode working end-to-end (the frontend depends on it from hour 0)
- [ ] Wire the arq queue: `POST /purchases/scan` and `POST /claims/{id}/approve` enqueue jobs
- [ ] Implement `poll_prices` with a **simulated price feed** in demo mode (deterministic drop on the hero product)
- [ ] Implement `evaluate_purchase` → `submit_claim` → `reconcile_refunds` using L3/L4/L5 interfaces (stub them until they land)
- [ ] Replace mock branches in routers with `data.mongo` / `data.timescale` calls as L4 delivers
- [ ] Add a `POST /demo/reset` endpoint to reseed the demo state between judge runs
