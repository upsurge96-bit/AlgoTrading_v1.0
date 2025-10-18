-- Migration: Create TimescaleDB tables for market data
-- Version: 0001
-- Description: Creates tick_data and ohlcv_data hypertables with appropriate indexes

-- Enable TimescaleDB extension if not already enabled
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ============================================================
-- TABLE: tick_data
-- Real-time tick data from market feed
-- ============================================================
CREATE TABLE IF NOT EXISTS tick_data (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument_token BIGINT NOT NULL,
    
    -- Price data
    last_price NUMERIC(12, 2),
    last_quantity INTEGER,
    average_price NUMERIC(12, 2),
    volume BIGINT,
    
    -- Buy/Sell data
    buy_quantity BIGINT,
    sell_quantity BIGINT,
    
    -- OHLC for the day
    open NUMERIC(12, 2),
    high NUMERIC(12, 2),
    low NUMERIC(12, 2),
    close NUMERIC(12, 2),
    
    -- Open Interest (for F&O)
    oi BIGINT,
    oi_day_high BIGINT,
    oi_day_low BIGINT,
    
    -- Exchange timestamp
    exchange_timestamp TIMESTAMPTZ,
    
    -- Market depth (stored as JSON)
    depth JSONB,
    
    -- Metadata
    mode VARCHAR(10),
    tradable BOOLEAN DEFAULT true,
    
    -- Primary key
    PRIMARY KEY (timestamp, instrument_token)
);

-- Convert to hypertable (partitioned by time)
SELECT create_hypertable(
    'tick_data',
    'timestamp',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS ix_tick_data_instrument_token 
    ON tick_data (instrument_token, timestamp DESC);

CREATE INDEX IF NOT EXISTS ix_tick_data_timestamp 
    ON tick_data (timestamp DESC);

-- ============================================================
-- TABLE: ohlcv_data
-- OHLCV candle data for different timeframes
-- ============================================================
CREATE TABLE IF NOT EXISTS ohlcv_data (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument_token BIGINT NOT NULL,
    interval VARCHAR(20) NOT NULL,
    
    -- OHLCV data
    open NUMERIC(12, 2) NOT NULL,
    high NUMERIC(12, 2) NOT NULL,
    low NUMERIC(12, 2) NOT NULL,
    close NUMERIC(12, 2) NOT NULL,
    volume BIGINT NOT NULL,
    
    -- Open Interest (for F&O)
    oi BIGINT,
    
    -- Metadata
    trades INTEGER,
    
    -- Primary key
    PRIMARY KEY (timestamp, instrument_token, interval)
);

-- Convert to hypertable
SELECT create_hypertable(
    'ohlcv_data',
    'timestamp',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '7 days'
);

-- Create indexes
CREATE INDEX IF NOT EXISTS ix_ohlcv_instrument_interval 
    ON ohlcv_data (instrument_token, interval, timestamp DESC);

CREATE INDEX IF NOT EXISTS ix_ohlcv_timestamp 
    ON ohlcv_data (timestamp DESC);

-- ============================================================
-- TABLE: instrument_master
-- Instrument master data from Kite API
-- ============================================================
CREATE TABLE IF NOT EXISTS instrument_master (
    instrument_token BIGINT PRIMARY KEY,
    exchange_token BIGINT,
    
    -- Instrument details
    tradingsymbol VARCHAR(50) NOT NULL,
    name VARCHAR(200),
    exchange VARCHAR(10) NOT NULL,
    segment VARCHAR(20),
    
    -- Instrument type
    instrument_type VARCHAR(10),
    
    -- Contract details (for F&O)
    expiry TIMESTAMPTZ,
    strike NUMERIC(12, 2),
    tick_size NUMERIC(10, 4),
    lot_size INTEGER,
    
    -- Last update
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS ix_instrument_tradingsymbol 
    ON instrument_master (tradingsymbol);

CREATE INDEX IF NOT EXISTS ix_instrument_exchange 
    ON instrument_master (exchange);

CREATE INDEX IF NOT EXISTS ix_instrument_expiry 
    ON instrument_master (expiry);

-- ============================================================
-- TABLE: data_service_metadata
-- Metadata for data service operations
-- ============================================================
CREATE TABLE IF NOT EXISTS data_service_metadata (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value VARCHAR(500),
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_metadata_key 
    ON data_service_metadata (key);

-- ============================================================
-- RETENTION POLICIES
-- Automatically drop old data to save space
-- ============================================================

-- Best-effort: add retention policy (safe if function available)
DO $$
BEGIN
  PERFORM add_retention_policy('tick_data', INTERVAL '365 days', if_not_exists => TRUE);
EXCEPTION WHEN undefined_function THEN
  RAISE NOTICE 'add_retention_policy not available; skipping retention policy for tick_data';
WHEN OTHERS THEN
  RAISE NOTICE 'add_retention_policy failed for tick_data: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
  PERFORM add_retention_policy('ohlcv_data', INTERVAL '1825 days', if_not_exists => TRUE);
EXCEPTION WHEN undefined_function THEN
  RAISE NOTICE 'add_retention_policy not available; skipping retention policy for ohlcv_data';
WHEN OTHERS THEN
  RAISE NOTICE 'add_retention_policy failed for ohlcv_data: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- CONTINUOUS AGGREGATES (Optional)
-- Pre-compute common aggregations
-- ============================================================

-- 1-minute OHLCV from tick data
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', timestamp) AS timestamp,
    instrument_token,
    '1m' as interval,
    FIRST(last_price, timestamp) AS open,
    MAX(last_price) AS high,
    MIN(last_price) AS low,
    LAST(last_price, timestamp) AS close,
    SUM(last_quantity) AS volume,
    LAST(oi, timestamp) AS oi,
    COUNT(*) AS trades
FROM tick_data
WHERE last_price IS NOT NULL
GROUP BY time_bucket('1 minute', timestamp), instrument_token;

-- ============================================================
-- COMPRESSION POLICIES
-- Compress old data to save storage
-- ============================================================

-- Best-effort: enable compression and add compression policy
DO $$
BEGIN
  BEGIN
    EXECUTE 'ALTER TABLE tick_data SET (timescaledb.compress, timescaledb.compress_segmentby = ''instrument_token'', timescaledb.compress_orderby = ''timestamp DESC'')';
  EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'ALTER TABLE tick_data SET (compress) failed or not supported: %', SQLERRM;
  END;

  PERFORM add_compression_policy('tick_data', INTERVAL '7 days', if_not_exists => TRUE);
EXCEPTION WHEN undefined_function THEN
  RAISE NOTICE 'add_compression_policy not available; skipping compression policy for tick_data';
WHEN OTHERS THEN
  RAISE NOTICE 'add_compression_policy failed for tick_data: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
  BEGIN
    EXECUTE 'ALTER TABLE ohlcv_data SET (timescaledb.compress, timescaledb.compress_segmentby = ''instrument_token, interval'', timescaledb.compress_orderby = ''timestamp DESC'')';
  EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'ALTER TABLE ohlcv_data SET (compress) failed or not supported: %', SQLERRM;
  END;

  PERFORM add_compression_policy('ohlcv_data', INTERVAL '30 days', if_not_exists => TRUE);
EXCEPTION WHEN undefined_function THEN
  RAISE NOTICE 'add_compression_policy not available; skipping compression policy for ohlcv_data';
WHEN OTHERS THEN
  RAISE NOTICE 'add_compression_policy failed for ohlcv_data: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;
