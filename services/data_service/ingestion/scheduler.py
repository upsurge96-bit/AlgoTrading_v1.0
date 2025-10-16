# services/data_service/ingestion/scheduler.py
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from core.utils.logger import get_logger
from core.utils.config_loader import load_config
from .ingester import archive_old_data, incremental_minio_load
from .fetcher import fetch_historical_ccxt, fetch_historical_kite
from .websocket_handler import start_kite_ws

# -------------------------------------------------------------------
#  GLOBALS
# -------------------------------------------------------------------
logger = get_logger("data_service.scheduler")
CFG = load_config("/app/config/config.yaml")

IST = ZoneInfo("Asia/Kolkata")
scheduler = AsyncIOScheduler(timezone=IST)

# -------------------------------------------------------------------
#  UTILITIES
# -------------------------------------------------------------------
def _today_ist_date_str() -> str:
    return datetime.now(tz=IST).strftime("%Y-%m-%d")

def _five_years_ago_ist_date_str() -> str:
    d = datetime.now(tz=IST) - timedelta(days=5 * 365)
    return d.strftime("%Y-%m-%d")

# -------------------------------------------------------------------
#  PERIODIC FETCH JOB
# -------------------------------------------------------------------
def schedule_periodic_fetch(symbol: str, timeframe: str, interval_seconds: int):
    """Schedules periodic CCXT data fetches for live market updates."""
    def job():
        logger.info("🕐 Running scheduled fetch | symbol=%s | timeframe=%s", symbol, timeframe)
        try:
            if symbol.upper() in ["NIFTY50", "NIFTY 50", "BANKNIFTY"]:
                df = fetch_historical_kite(symbol, timeframe, limit)
            else:
                df = fetch_historical_ccxt(symbol, timeframe, limit)
            if not df.empty:
                logger.info("✅ Completed scheduled fetch | rows=%d | symbol=%s", len(df), symbol)
        except Exception as e:
            logger.exception("❌ Scheduled fetch failed for %s: %s", symbol, e)


    job_id = f"fetch_{symbol.replace('/', '_')}_{timeframe}"
    scheduler.add_job(job, "interval", seconds=interval_seconds, id=job_id, replace_existing=True)
    logger.info("📆 Scheduled job added | id=%s | every=%ss", job_id, interval_seconds)

# -------------------------------------------------------------------
#  JOB EVENT LISTENERS
# -------------------------------------------------------------------
def _on_job_event(event):
    """Logs job completion and failures."""
    job = scheduler.get_job(event.job_id)
    if event.exception:
        logger.error("💥 Job failed | id=%s | error=%s", event.job_id, event.exception)
    else:
        logger.debug("✅ Job executed successfully | id=%s", event.job_id)

# -------------------------------------------------------------------
#  SCHEDULER STARTUP
# -------------------------------------------------------------------
def start_scheduler():
    """
    Initializes and starts the data-service scheduler:
      - Periodic CCXT fetches
      - Pre-market incremental MinIO load (09:00 IST)
      - End-of-day archival to MinIO (17:30 IST)
      - Optional Kite WebSocket for live ticks
    """
    try:
        symbols = CFG.get("data", {}).get("symbols", ["BTC/USDT"])
        timeframe = CFG.get("data", {}).get("timeframe", "1m")
        interval = CFG.get("data", {}).get("fetch_interval_sec", 60)

        logger.info(
            "⚙️ Starting scheduler | symbols=%s | timeframe=%s | interval=%ss | tz=Asia/Kolkata",
            symbols, timeframe, interval
        )

        # 1️⃣ Periodic fetch job
        for symbol in symbols:
            schedule_periodic_fetch(symbol, timeframe, interval)

        # 2️⃣ Pre-market incremental MinIO load (daily 09:00 IST)
        def pre_market_backfill():
            end_date = _today_ist_date_str()
            start_date = _five_years_ago_ist_date_str()
            for sym in symbols:
                logger.info(
                    "📦 Pre-market MinIO incremental load | symbol=%s | %s → %s",
                    sym, start_date, end_date
                )
                incremental_minio_load(sym, start_date, end_date)

        scheduler.add_job(
            pre_market_backfill,
            "cron",
            hour=9,
            minute=0,
            id="incremental_minio_load",
            replace_existing=True,
        )

        # 3️⃣ End-of-day archival (daily 17:30 IST)
        def eod_archive():
            for sym in symbols:
                logger.info(
                    "🗂️ EOD archival job started | symbol=%s | retention=%sd",
                    sym,
                    CFG.get("retention", {}).get("timescale_days", 90),
                )
                archive_old_data(sym)

        scheduler.add_job(
            eod_archive,
            "cron",
            hour=17,
            minute=30,
            id="archive_old_data",
            replace_existing=True,
        )

        # 4️⃣ Optional: Start Kite WebSocket (if configured)
        kite_tokens = CFG.get("kite", {}).get("tokens", [])
        if kite_tokens:
            logger.info("📡 Starting Kite WebSocket stream for %d tokens", len(kite_tokens))
            try:
                start_kite_ws(kite_tokens, symbols)
                logger.info("✅ Kite WebSocket successfully started")
            except Exception as e:
                logger.exception("⚠️ Failed to start Kite WebSocket: %s", e)

        # Add event listeners and start the scheduler
        scheduler.add_listener(_on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        scheduler.start()

        # Summary
        logger.info("✅ Scheduler started with %d jobs", len(scheduler.get_jobs()))
        for job in scheduler.get_jobs():
            logger.debug("🗓️ Active job: %s | next_run=%s", job.id, job.next_run_time)

    except Exception as e:
        logger.exception("💥 Scheduler failed to start: %s", e)
        raise
