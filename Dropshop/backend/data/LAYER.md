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
- Atlas: allow your IP (or `0.0.0.0/0` for the hackathon) under Network Access

## First tasks
- [ ] Run the migration on Tiger Cloud and confirm `price_daily` refreshes
- [ ] Implement `timescale.insert_price`, `latest_price` and `price_history`
- [ ] Implement the `mongo.py` repository functions and `mongo_indexes.py`
- [ ] `seed.py`: demo user, 5 purchases, 30 days of price history with a visible drop on the hero product
- [ ] Stretch: a "lowest price in 30 days" query for the dashboard (shows off Timescale)
