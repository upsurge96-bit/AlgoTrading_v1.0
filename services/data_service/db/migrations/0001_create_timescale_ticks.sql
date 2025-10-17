-- Create TimescaleDB extension, table/hypertable, index, continuous aggregate and policies

-- create extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- raw ticks table
CREATE TABLE IF NOT EXISTS ticks (
  time TIMESTAMPTZ NOT NULL,
  token BIGINT,
  ltp DOUBLE PRECISION,
  open DOUBLE PRECISION,
  high DOUBLE PRECISION,
  low DOUBLE PRECISION,
  close DOUBLE PRECISION,
  raw JSONB
);

-- create hypertable (idempotent)
SELECT create_hypertable('ticks', 'time', if_not_exists => TRUE);

-- index for instrument/time queries
CREATE INDEX IF NOT EXISTS idx_ticks_token_time ON ticks (token, time DESC);

-- Continuous aggregate: per-second downsample
CREATE MATERIALIZED VIEW IF NOT EXISTS ticks_1s
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 second', time) AS bucket,
  token,
  first(ltp, time) AS first_ltp,
  last(ltp, time) AS last_ltp,
  max(high) AS high,
  min(low) AS low,
  count(*) AS ticks
FROM ticks
GROUP BY bucket, token;

-- Best-effort: add retention policy (safe if function available)
DO $$
BEGIN
  PERFORM add_retention_policy('ticks', INTERVAL '30 days');
EXCEPTION WHEN undefined_function THEN
  RAISE NOTICE 'add_retention_policy not available; skipping retention policy';
WHEN OTHERS THEN
  RAISE NOTICE 'add_retention_policy failed: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Best-effort: enable compression and add compression policy (safe if functions available)
DO $$
BEGIN
  -- try to set chunk compression and add compression policy
  BEGIN
    EXECUTE 'ALTER TABLE ticks SET (timescaledb.compress, timescaledb.compress_segmentby = ''token'')';
  EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'ALTER TABLE ... SET (compress) failed or not supported: %', SQLERRM;
  END;

  PERFORM add_compression_policy('ticks', INTERVAL '7 days');
EXCEPTION WHEN undefined_function THEN
  RAISE NOTICE 'add_compression_policy not available; skipping compression policy';
WHEN OTHERS THEN
  RAISE NOTICE 'add_compression_policy failed: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;
