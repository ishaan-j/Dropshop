-- Tiger Data / TimescaleDB schema for Dropshot (Layer 4).
-- Runs automatically on first `docker compose up` locally; run manually against Tiger Cloud.

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS price_observations (
    time        TIMESTAMPTZ NOT NULL,
    product_id  TEXT        NOT NULL,   -- e.g. 'bestbuy:6505727'
    retailer    TEXT        NOT NULL,
    price_cents INTEGER     NOT NULL,
    in_stock    BOOLEAN,
    source      TEXT        NOT NULL DEFAULT 'poller'   -- poller | seed | manual
);

SELECT create_hypertable('price_observations', by_range('time'), if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_price_obs_product_time
    ON price_observations (product_id, time DESC);

-- Daily rollup for charts + drop detection.
CREATE MATERIALIZED VIEW IF NOT EXISTS price_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time)   AS day,
    product_id,
    retailer,
    min(price_cents)             AS min_price_cents,
    max(price_cents)             AS max_price_cents,
    last(price_cents, time)      AS close_price_cents
FROM price_observations
GROUP BY day, product_id, retailer
WITH NO DATA;

-- Real-time aggregation: days the refresh policy hasn't stored yet are computed from the raw rows
-- when queried. Without it, yesterday is missing from the chart for the first hour or so after
-- midnight UTC, until the policy below gets to it.
ALTER MATERIALIZED VIEW price_daily SET (timescaledb.materialized_only = false);

SELECT add_continuous_aggregate_policy('price_daily',
    start_offset      => INTERVAL '60 days',
    end_offset        => INTERVAL '1 hour',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists     => TRUE);
