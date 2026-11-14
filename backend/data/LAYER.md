# Layer 4: Database

**Owner:** _TBD_ · **Stack:** Tiger Data / TimescaleDB, MongoDB Atlas

## You own
- **Tiger Data**: `price_observations` hypertable plus the `price_daily` continuous aggregate (`migrations/001_timescale_init.sql`)
- **MongoDB Atlas**: users, purchases, receipt metadata, retailer policies, claims, agent logs (`mongo.py`, `mongo_indexes.py`)
- **Seed data** for the demo (`seed.py`)
- The schema doc: [`docs/data-model.md`](../../docs/data-model.md)

## Setup
- Local: `docker compose up -d timescaledb` from the repo root (the migration runs automatically on first start)
- Cloud: create a Tiger Cloud service and an Atlas cluster (free tiers), then put the URLs in `.env`

### MongoDB Atlas
1. In Atlas, create a free M0 cluster.
2. Database Access: add a database user with a password (read and write).
3. Network Access: allow your IP, or `0.0.0.0/0` for the hackathon.
4. Connect → Drivers → copy the connection string into `.env`:
   `MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority`
   URL-encode any special characters in the password (`@` is `%40`).
5. From `backend/`: `python -m data.seed`. It creates the indexes and loads the demo state. Run it
   again whenever the demo should start over (`POST /demo/reset` only resets the in-memory store).
6. Set `MOCK_MODE=false` and restart the API. `GET /health` should report `"store": "db"`.

With `MOCK_MODE=false` and no reachable cluster the API keeps the database store and its requests
fail, so set `DATA_BACKEND=memory` until `MONGODB_URI` is filled in.

### Tiger Data (Tiger Cloud)
1. In the Tiger Cloud console, create a service. Save the password it shows: it is shown once.
2. Copy the service URL into `.env`:
   `TIMESCALE_URL=postgres://tsdbadmin:<password>@<host>:<port>/tsdb?sslmode=require`
3. From `backend/`: `python -m data.seed`. It applies `migrations/001_timescale_init.sql` (no `psql`
   needed), loads 30 days of price history for the demo products and refreshes `price_daily`.
   `python -m data.timescale` applies the schema only.
4. Restart the API. `GET /health` should report `"prices": "tiger"`.

How it is used: every price check is a row in the `price_observations` hypertable. The chart reads
completed days from the `price_daily` continuous aggregate and today from the raw rows, so a price
recorded a moment ago shows at once.

Tiger Data is optional for the database store. If it doesn't answer at startup, the API holds price
history in its own process until it restarts (`"prices": "memory"`), and logs why.

The tests never connect to either service: `backend/conftest.py` swaps in an in-process fake for
Mongo and refuses Tiger Data connections.

## Status
- [x] `mongo.py` repository, `mongo_indexes.py` and the Mongo part of `seed.py`, with tests (`test_mongo.py`). Verified against Atlas.
- [x] `timescale.py`: migration runner, `insert_price`, `latest_price`, `price_history`, seed history, with tests of what it sends (`test_timescale.py`). **The SQL has not been run against a real TimescaleDB yet.**
- [ ] Run `python -m data.seed` against Tiger Cloud and confirm the chart reads from `price_daily`
- [ ] Stretch: a "lowest price in 30 days" query for the dashboard (shows off Timescale)
