-- Migration: 0001_recreate_live_market_data.sql
-- Purpose: Safely backup (rename) any existing live_market_data table then recreate the table with the expected schema
-- Notes: Run as a DB superuser or as an owner of the schema. Always backup DB before running destructive operations.

BEGIN;

-- 1) If the table exists, rename it to a backup name with timestamp (preserve data). This is safe and non-destructive.
DO $$
DECLARE
    exists boolean;
    backup_name text;
BEGIN
    SELECT to_regclass('public.live_market_data') IS NOT NULL INTO exists;
    IF exists THEN
        backup_name := format('live_market_data_backup_%s', to_char(now(), 'YYYYMMDD_HH24MISS'));
        RAISE NOTICE 'Renaming existing table to %', backup_name;
        EXECUTE format('ALTER TABLE public.live_market_data RENAME TO %I', backup_name);

        -- If the old table had a primary key constraint named 'live_market_data_pkey',
        -- rename that constraint on the backup table to avoid a schema-wide name collision
        -- (constraint names are unique per schema). Trap errors to avoid aborting.
        BEGIN
            EXECUTE format('ALTER TABLE %I RENAME CONSTRAINT live_market_data_pkey TO %I', backup_name, backup_name || '_pkey');
            RAISE NOTICE 'Renamed constraint live_market_data_pkey on % to %', backup_name, backup_name || '_pkey';
        EXCEPTION WHEN undefined_object THEN
            -- no constraint to rename; continue
            RAISE NOTICE 'No primary key constraint named live_market_data_pkey found on %, skipping constraint rename', backup_name;
        END;

    ELSE
        RAISE NOTICE 'No existing live_market_data table found. Skipping rename.';
    END IF;
END$$;

-- 2) Create the new table with the intended schema
-- Use IF NOT EXISTS for idempotency in case someone created it already
CREATE TABLE IF NOT EXISTS public.live_market_data (
    symbol TEXT NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    source TEXT
);

-- 3) Add time-dimension columns if missing
ALTER TABLE public.live_market_data
    ADD COLUMN IF NOT EXISTS year INTEGER,
    ADD COLUMN IF NOT EXISTS month INTEGER,
    ADD COLUMN IF NOT EXISTS week INTEGER,
    ADD COLUMN IF NOT EXISTS date DATE,
    ADD COLUMN IF NOT EXISTS hour INTEGER;

-- 4) Add primary key constraint if missing. Before adding, check that no duplicates exist.
-- If duplicates exist, this will abort; inspect the backup table created earlier.
DO $$
DECLARE
    has_pk boolean := false;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'live_market_data' AND c.contype = 'p'
    ) INTO has_pk;

    IF NOT has_pk THEN
        -- Ensure there are no duplicates
        IF EXISTS(
            SELECT symbol, "timestamp", COUNT(*)
            FROM public.live_market_data
            GROUP BY symbol, "timestamp"
            HAVING COUNT(*) > 1
        ) THEN
            RAISE EXCEPTION 'Cannot add primary key because duplicate (symbol, timestamp) rows exist. Inspect backup table.';
        ELSE
            EXECUTE 'ALTER TABLE public.live_market_data ADD CONSTRAINT live_market_data_pkey PRIMARY KEY (symbol, "timestamp")';
        END IF;
    ELSE
        RAISE NOTICE 'Primary key already exists on live_market_data; skipping.';
    END IF;
END$$;

-- 5) Create hypertable if TimescaleDB extension is available
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        BEGIN
            PERFORM create_hypertable('public.live_market_data', 'timestamp', if_not_exists => TRUE);
            RAISE NOTICE 'Hypertable created/verified.';
        EXCEPTION WHEN others THEN
            RAISE NOTICE 'Hypertable creation skipped (maybe already a hypertable or no permission): %', SQLERRM;
        END;
    ELSE
        RAISE NOTICE 'TimescaleDB extension not installed; skipping hypertable creation.';
    END IF;
END$$;

COMMIT;

-- Recommended follow-ups:
-- 1) If you renamed an existing table, inspect the backup table (live_market_data_backup_YYYYMMDD_HHMMSS) and migrate data as needed.
-- 2) Re-run any ingestion to repopulate the new table, or write scripts to copy/transform data from the backup table into the new table with proper partitioning and deduplication.
