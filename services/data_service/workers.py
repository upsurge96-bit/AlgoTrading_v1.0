"""
Background Workers for Data Service
Handles WebSocket streaming, historical data sync, and scheduled tasks
"""

import asyncio
import logging
import signal
import os
from datetime import datetime, time
from typing import List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from services.data_service.extraction.websocket_client import KiteWebSocketClient
from services.data_service.extraction.auth_client import AuthClient
from services.data_service.extraction.kite_api_client import HistoricalDataFetcher
from services.data_service.processors.tick_processor import TickProcessor, OHLCVProcessor
from services.data_service.processors.minio_handler import MinIOHandler
from core.utils.logger import get_logger

logger = get_logger("data_service.workers")


class LiveDataWorker:
    """
    Worker for streaming live market data via WebSocket
    
    - Connects to Kite WebSocket
    - Processes ticks in real-time
    - Automatically reconnects on failure
    """
    
    def __init__(
        self,
        instrument_tokens: List[int],
        mode: str = "full",
        auth_client: Optional[AuthClient] = None,
        tick_processor: Optional[TickProcessor] = None
    ):
        """
        Initialize Live Data Worker
        
        Args:
            instrument_tokens: List of instrument tokens to subscribe
            mode: Subscription mode ('ltp', 'quote', 'full')
            auth_client: Auth client for tokens
            tick_processor: Tick processor for handling ticks
        """
        self.instrument_tokens = instrument_tokens
        self.mode = mode
        self.auth_client = auth_client or AuthClient()
        self.tick_processor = tick_processor or TickProcessor()
        
        self.ws_client: Optional[KiteWebSocketClient] = None
        self._running = False
        self._stop_event = asyncio.Event()
        
        logger.info(f"LiveDataWorker initialized with {len(instrument_tokens)} instruments")
    
    def on_tick(self, tick_data: dict):
        """Callback for tick data"""
        try:
            # Process tick
            self.tick_processor.process_tick(tick_data)
        except Exception as e:
            logger.error(f"Error processing tick: {e}")
    
    def on_connect(self):
        """Callback on WebSocket connection"""
        logger.info("✅ WebSocket connected - Live data streaming started")
    
    def on_disconnect(self):
        """Callback on WebSocket disconnection"""
        logger.warning("⚠️ WebSocket disconnected - Will attempt to reconnect")
    
    def on_error(self, error: Exception):
        """Callback on WebSocket error"""
        logger.error(f"WebSocket error: {error}")
    
    async def start(self):
        """Start live data streaming"""
        if self._running:
            logger.warning("LiveDataWorker already running")
            return
        
        self._running = True
        logger.info("Starting live data worker...")
        
        try:
            # Initialize WebSocket client
            self.ws_client = KiteWebSocketClient(
                auth_client=self.auth_client,
                on_tick=self.on_tick,
                on_connect=self.on_connect,
                on_disconnect=self.on_disconnect,
                on_error=self.on_error,
                reconnect_attempts=10,
                reconnect_delay=5
            )
            
            # Connect to WebSocket
            await self.ws_client.connect()
            
            # Subscribe to instruments
            if self.instrument_tokens:
                await self.ws_client.subscribe(self.instrument_tokens)
                await self.ws_client.set_mode(self.mode, self.instrument_tokens)
                logger.info(f"Subscribed to {len(self.instrument_tokens)} instruments in {self.mode} mode")
            
            # Keep running until stop event is set
            await self._stop_event.wait()
            
        except Exception as e:
            logger.exception(f"Error in live data worker: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop live data streaming"""
        if not self._running:
            return
        
        logger.info("Stopping live data worker...")
        self._running = False
        
        if self.ws_client:
            await self.ws_client.close()
        
        # Cleanup processor
        if self.tick_processor:
            self.tick_processor.close()
        
        logger.info("Live data worker stopped")
    
    async def add_instruments(self, tokens: List[int]):
        """Add instruments to subscription"""
        if self.ws_client and self.ws_client._connected:
            await self.ws_client.subscribe(tokens)
            await self.ws_client.set_mode(self.mode, tokens)
            self.instrument_tokens.extend(tokens)
            logger.info(f"Added {len(tokens)} instruments to subscription")
    
    async def remove_instruments(self, tokens: List[int]):
        """Remove instruments from subscription"""
        if self.ws_client and self.ws_client._connected:
            await self.ws_client.unsubscribe(tokens)
            for token in tokens:
                if token in self.instrument_tokens:
                    self.instrument_tokens.remove(token)
            logger.info(f"Removed {len(tokens)} instruments from subscription")


class HistoricalDataWorker:
    """
    Worker for fetching historical data
    
    - Initial 5-year data load
    - Daily incremental updates
    - Scheduled backfill
    """
    
    def __init__(
        self,
        instrument_tokens: List[int],
        auth_client: Optional[AuthClient] = None,
        fetcher: Optional[HistoricalDataFetcher] = None
    ):
        """
        Initialize Historical Data Worker
        
        Args:
            instrument_tokens: List of instrument tokens
            auth_client: Auth client for tokens
            fetcher: Historical data fetcher
        """
        self.instrument_tokens = instrument_tokens
        self.auth_client = auth_client or AuthClient()
        self.fetcher = fetcher or HistoricalDataFetcher(auth_client=self.auth_client)
        
        logger.info(f"HistoricalDataWorker initialized with {len(instrument_tokens)} instruments")
    
    async def fetch_5_years_data(self):
        """Fetch 5 years of historical data"""
        logger.info("Starting 5-year historical data fetch...")
        
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.fetcher.fetch_5_years_data,
                self.instrument_tokens,
                ["day", "60minute", "15minute"],
                1  # Include OI
            )
            
            logger.info("✅ Completed 5-year historical data fetch")
        except Exception as e:
            logger.exception(f"Error fetching 5-year data: {e}")
    
    async def fetch_incremental_data(self, days: int = 1):
        """Fetch incremental data (daily update)"""
        logger.info(f"Starting incremental data fetch ({days} days)...")
        
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.fetcher.fetch_incremental_data,
                self.instrument_tokens,
                ["day", "60minute", "15minute"],
                days,
                1  # Include OI
            )
            
            logger.info("✅ Completed incremental data fetch")
        except Exception as e:
            logger.exception(f"Error fetching incremental data: {e}")


class DataServiceScheduler:
    """
    Scheduler for data service tasks
    
    Schedules:
    - Daily historical data updates
    - Health checks
    - Data cleanup
    """
    
    def __init__(
        self,
        historical_worker: Optional[HistoricalDataWorker] = None
    ):
        """Initialize Data Service Scheduler"""
        self.historical_worker = historical_worker
        self.scheduler = AsyncIOScheduler()
        
        logger.info("DataServiceScheduler initialized")
    
    def setup_schedules(self):
        """Setup scheduled tasks"""
        
        # Daily incremental data fetch (runs at 4:00 PM IST after market close)
        self.scheduler.add_job(
            func=self._run_incremental_fetch,
            trigger=CronTrigger(hour=16, minute=0, timezone="Asia/Kolkata"),
            id="daily_incremental_fetch",
            name="Daily Incremental Data Fetch",
            replace_existing=True
        )
        logger.info("Scheduled: Daily incremental data fetch at 4:00 PM IST")
        
        # Weekly full day backfill (runs every Sunday at 2:00 AM IST)
        self.scheduler.add_job(
            func=self._run_weekly_backfill,
            trigger=CronTrigger(day_of_week='sun', hour=2, minute=0, timezone="Asia/Kolkata"),
            id="weekly_backfill",
            name="Weekly Data Backfill",
            replace_existing=True
        )
        logger.info("Scheduled: Weekly backfill on Sundays at 2:00 AM IST")
        
        # Health check every 5 minutes
        self.scheduler.add_job(
            func=self._health_check,
            trigger=IntervalTrigger(minutes=5),
            id="health_check",
            name="Health Check",
            replace_existing=True
        )
        logger.info("Scheduled: Health check every 5 minutes")
    
    async def _run_incremental_fetch(self):
        """Run incremental data fetch"""
        logger.info("Running scheduled incremental data fetch...")
        if self.historical_worker:
            await self.historical_worker.fetch_incremental_data(days=1)
    
    async def _run_weekly_backfill(self):
        """Run weekly backfill"""
        logger.info("Running scheduled weekly backfill...")
        if self.historical_worker:
            await self.historical_worker.fetch_incremental_data(days=7)
    
    async def _health_check(self):
        """Perform health check"""
        logger.debug("Running health check...")
        # Add health check logic here
    
    def start(self):
        """Start scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("✅ Scheduler started")
    
    def stop(self):
        """Stop scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")


class DataServiceCoordinator:
    """
    Coordinator for all data service workers
    
    Manages:
    - Live data streaming
    - Historical data fetch
    - Scheduled tasks
    """
    
    def __init__(
        self,
        instrument_tokens: List[int],
        enable_live_streaming: bool = True,
        enable_historical_fetch: bool = True,
        enable_scheduler: bool = True,
        websocket_mode: str = "full"
    ):
        """
        Initialize Data Service Coordinator
        
        Args:
            instrument_tokens: List of instrument tokens
            enable_live_streaming: Enable live data streaming
            enable_historical_fetch: Enable historical data fetch
            enable_scheduler: Enable scheduler
            websocket_mode: WebSocket subscription mode
        """
        self.instrument_tokens = instrument_tokens
        self.enable_live_streaming = enable_live_streaming
        self.enable_historical_fetch = enable_historical_fetch
        self.enable_scheduler = enable_scheduler
        self.websocket_mode = websocket_mode
        
        # Initialize workers
        self.live_worker: Optional[LiveDataWorker] = None
        self.historical_worker: Optional[HistoricalDataWorker] = None
        self.scheduler: Optional[DataServiceScheduler] = None
        
        self._tasks = []
        self._stop_event = asyncio.Event()
        
        logger.info("DataServiceCoordinator initialized")
    
    async def start(self):
        """Start all enabled workers"""
        logger.info("Starting Data Service Coordinator...")
        
        try:
            # Initialize historical worker
            if self.enable_historical_fetch:
                self.historical_worker = HistoricalDataWorker(
                    instrument_tokens=self.instrument_tokens
                )
            
            # Initialize scheduler
            if self.enable_scheduler and self.historical_worker:
                self.scheduler = DataServiceScheduler(
                    historical_worker=self.historical_worker
                )
                self.scheduler.setup_schedules()
                self.scheduler.start()
            
            # Start live streaming
            if self.enable_live_streaming:
                self.live_worker = LiveDataWorker(
                    instrument_tokens=self.instrument_tokens,
                    mode=self.websocket_mode
                )
                task = asyncio.create_task(self.live_worker.start())
                self._tasks.append(task)
            
            # Setup signal handlers
            self._setup_signal_handlers()
            
            logger.info("✅ Data Service Coordinator started successfully")
            
            # Wait for stop event
            await self._stop_event.wait()
            
        except Exception as e:
            logger.exception(f"Error in Data Service Coordinator: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop all workers"""
        logger.info("Stopping Data Service Coordinator...")
        
        # Stop live worker
        if self.live_worker:
            await self.live_worker.stop()
        
        # Stop scheduler
        if self.scheduler:
            self.scheduler.stop()
        
        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        logger.info("✅ Data Service Coordinator stopped")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, initiating shutdown...")
            self._stop_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def trigger_historical_fetch(self, years: int = 5):
        """Manually trigger historical data fetch"""
        if self.historical_worker:
            if years == 5:
                await self.historical_worker.fetch_5_years_data()
            else:
                days = years * 365
                await self.historical_worker.fetch_incremental_data(days=days)
        else:
            logger.warning("Historical worker not initialized")


# Main entry point for running workers
async def main():
    """Main entry point for data service workers"""
    # Get configuration from environment
    instrument_tokens_str = os.getenv("INSTRUMENT_TOKENS", "")
    instrument_tokens = [int(t.strip()) for t in instrument_tokens_str.split(",") if t.strip()]
    
    if not instrument_tokens:
        logger.warning("No instrument tokens configured, using default")
        instrument_tokens = [408065]  # INFY as default
    
    enable_live = os.getenv("ENABLE_LIVE_STREAMING", "true").lower() == "true"
    enable_historical = os.getenv("ENABLE_HISTORICAL_FETCH", "true").lower() == "true"
    enable_scheduler = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
    websocket_mode = os.getenv("WEBSOCKET_MODE", "full")
    
    # Create coordinator
    coordinator = DataServiceCoordinator(
        instrument_tokens=instrument_tokens,
        enable_live_streaming=enable_live,
        enable_historical_fetch=enable_historical,
        enable_scheduler=enable_scheduler,
        websocket_mode=websocket_mode
    )
    
    # Start coordinator
    await coordinator.start()


if __name__ == "__main__":
    asyncio.run(main())
