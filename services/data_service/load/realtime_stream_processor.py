"""
Realtime Stream Processor - Real-Time Market Data Streaming
Connects to Kite WebSocket and stores live ticks to TimescaleDB in real-time

Features:
- WebSocket connection to Kite API for live market data
- Configurable symbols and intervals
- Real-time tick storage to TimescaleDB
- OHLCV candle aggregation from ticks
- Multi-granularity candle generation
- Comprehensive logging and error handling
- Auto-reconnection on connection loss
- Market status awareness (shows when market is closed)
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, time
from zoneinfo import ZoneInfo

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from core.utils.logger import setup_logging, get_logger
from core.utils.time_utils import utc_now
from services.data_service.extraction.auth_client import AuthClient
from core.messaging.web_socket import KiteWebSocketClient
from services.data_service.processors.tick_processor import TickProcessor, OHLCVProcessor

# Setup logging
setup_logging(
    service_name="realtime_stream_processor",
    log_level=os.getenv("LOG_LEVEL", "INFO")
)
logger = get_logger(__name__)

# Timezone
IST = ZoneInfo("Asia/Kolkata")


def is_market_open() -> tuple[bool, str]:
    """
    Check if Indian stock market is open
    
    Returns:
        tuple: (is_open: bool, reason: str)
    """
    now_ist = datetime.now(IST)
    current_day = now_ist.weekday()  # 0=Monday, 6=Sunday
    current_time = now_ist.time()
    
    # Market hours: Monday-Friday, 9:15 AM - 3:30 PM IST
    MARKET_OPEN = time(9, 15)
    MARKET_CLOSE = time(15, 30)
    
    # Check if weekend
    if current_day >= 5:  # Saturday (5) or Sunday (6)
        day_name = now_ist.strftime("%A")
        return False, f"Weekend ({day_name})"
    
    # Check if during market hours
    if current_time < MARKET_OPEN:
        return False, f"Pre-market (opens at 09:15 AM)"
    elif current_time > MARKET_CLOSE:
        return False, f"After-hours (closed at 03:30 PM)"
    else:
        return True, "Market hours (9:15 AM - 3:30 PM)"


def get_market_status_emoji() -> str:
    """Get emoji for current market status"""
    is_open, _ = is_market_open()
    return "🟢 OPEN" if is_open else "🔴 CLOSED"


def get_market_status_message() -> str:
    """Get detailed market status message"""
    is_open, reason = is_market_open()
    now_ist = datetime.now(IST)
    
    if is_open:
        return f"🟢 Market OPEN ({reason})"
    else:
        return f"🔴 Market CLOSED ({reason})"


class RealtimeStreamProcessor:
    """
    Real-time market data processor
    
    Connects to Kite WebSocket and:
    1. Stores ticks to TimescaleDB
    2. Aggregates ticks into candles (1m, 5m, 15m, 1h, 1d)
    3. Stores candles to TimescaleDB
    4. Publishes to Kafka (optional)
    5. Archives to MinIO (optional)
    
    Configuration via environment variables:
    - LIVE_DATA_SYMBOLS: Comma-separated instrument tokens
    - LIVE_DATA_MODE: WebSocket mode (ltp, quote, full)
    - LIVE_DATA_INTERVALS: Comma-separated intervals to generate
    - ENABLE_TICK_STORAGE: Store raw ticks (default: true)
    - ENABLE_CANDLE_GENERATION: Generate candles (default: true)
    """
    
    def __init__(
        self,
        symbols: Optional[List[int]] = None,
        mode: str = "full",
        intervals: Optional[List[str]] = None,
        enable_tick_storage: bool = True,
        enable_candle_generation: bool = True
    ):
        """
        Initialize Live Data Processor
        
        Args:
            symbols: List of instrument tokens (if None, loads from config)
            mode: WebSocket subscription mode (ltp, quote, full)
            intervals: List of candle intervals to generate
            enable_tick_storage: Whether to store raw ticks to DB
            enable_candle_generation: Whether to generate candles from ticks
        """
        # Load configuration
        self.symbols = symbols or self._load_symbols_from_config()
        self.mode = mode or os.getenv("LIVE_DATA_MODE", "full")
        self.intervals = intervals or self._load_intervals_from_config()
        self.enable_tick_storage = enable_tick_storage
        self.enable_candle_generation = enable_candle_generation
        
        # Validate mode
        if self.mode not in ["ltp", "quote", "full"]:
            raise ValueError(f"Invalid mode: {self.mode}. Must be 'ltp', 'quote', or 'full'")
        
        # Initialize clients
        self.auth_client = AuthClient()
        self.ws_client: Optional[KiteWebSocketClient] = None
        
        # Initialize processors
        self.tick_processor: Optional[TickProcessor] = None
        self.candle_processor: Optional[OHLCVProcessor] = None
        
        if self.enable_tick_storage:
            self.tick_processor = TickProcessor()
            logger.info("✅ Tick storage enabled")
        
        if self.enable_candle_generation:
            self.candle_processor = OHLCVProcessor()
            logger.info("✅ Candle generation enabled")
        
        # Statistics
        self.stats = {
            "ticks_received": 0,
            "ticks_stored": 0,
            "candles_generated": 0,
            "errors": 0,
            "start_time": None,
            "last_tick_time": None,
            "last_heartbeat_time": None
        }
        
        # Heartbeat configuration
        self.heartbeat_interval = int(os.getenv("HEARTBEAT_INTERVAL", "60"))  # seconds
        self._heartbeat_task = None
        
        # Connection state
        self._running = False
        self._connected = False
        
        logger.info(f"✅ LiveDataProcessor initialized")
        logger.info(f"   Symbols: {len(self.symbols)} instruments")
        logger.info(f"   Mode: {self.mode}")
        logger.info(f"   Intervals: {', '.join(self.intervals) if self.intervals else 'N/A'}")
        logger.info(f"   Tick Storage: {self.enable_tick_storage}")
        logger.info(f"   Candle Generation: {self.enable_candle_generation}")
    
    def _load_symbols_from_config(self) -> List[int]:
        """Load instrument tokens from environment or config"""
        # Try environment variable first
        env_symbols = os.getenv("LIVE_DATA_SYMBOLS", "")
        if env_symbols:
            tokens = [int(t.strip()) for t in env_symbols.split(",") if t.strip()]
            logger.info(f"Loaded {len(tokens)} symbols from LIVE_DATA_SYMBOLS env")
            return tokens
        
        # Fallback to config
        try:
            from services.data_service.config import get_settings
            settings = get_settings()
            tokens = settings.instruments.tokens
            logger.info(f"Loaded {len(tokens)} symbols from config")
            return tokens
        except Exception as e:
            logger.warning(f"Could not load symbols from config: {e}")
            # Default symbols
            default = [408065, 884737, 738561]  # NIFTY 50, BANKNIFTY, INFY
            logger.info(f"Using default symbols: {default}")
            return default
    
    def _load_intervals_from_config(self) -> List[str]:
        """Load intervals from environment"""
        env_intervals = os.getenv("LIVE_DATA_INTERVALS", "1m,5m,15m,1h,1d")
        intervals = [i.strip() for i in env_intervals.split(",") if i.strip()]
        logger.info(f"Loaded intervals: {', '.join(intervals)}")
        return intervals
    
    def on_connect(self):
        """Callback when WebSocket connects"""
        self._connected = True
        market_status = get_market_status_message()
        is_open, market_reason = is_market_open()
        
        logger.info("=" * 80)
        logger.info("🟢 WebSocket CONNECTED - Live data streaming started")
        logger.info("=" * 80)
        logger.info(f"   Time: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')} IST")
        logger.info(f"   Market Status: {market_status}")
        logger.info(f"   Symbols: {len(self.symbols)}")
        logger.info(f"   Mode: {self.mode}")
        logger.info("=" * 80)
        
        # Add helpful message if connected outside market hours
        if not is_open:
            logger.info(f"ℹ️  WebSocket connected successfully, but market is {market_reason}.")
            logger.info(f"ℹ️  Data will start flowing when market opens (Mon-Fri 9:15 AM - 3:30 PM IST).")
            logger.info("=" * 80)
    
    def on_disconnect(self):
        """Callback when WebSocket disconnects"""
        self._connected = False
        logger.warning("=" * 80)
        logger.warning("🔴 WebSocket DISCONNECTED - Will attempt to reconnect")
        logger.warning("=" * 80)
    
    def on_error(self, error: Exception):
        """Callback when WebSocket error occurs"""
        self.stats["errors"] += 1
        logger.error(f"❌ WebSocket ERROR: {error}")
    
    def on_tick(self, tick_data: Dict[str, Any]):
        """
        Callback when tick data is received
        
        Args:
            tick_data: Tick data from WebSocket
        """
        try:
            self.stats["ticks_received"] += 1
            self.stats["last_tick_time"] = utc_now()
            
            # Log periodic updates (every 100 ticks)
            if self.stats["ticks_received"] % 100 == 0:
                logger.info(f"📊 Processed {self.stats['ticks_received']} ticks | "
                          f"Stored: {self.stats['ticks_stored']} | "
                          f"Candles: {self.stats['candles_generated']} | "
                          f"Errors: {self.stats['errors']}")
            
            # Process tick data
            self._process_tick(tick_data)
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error in on_tick callback: {e}", exc_info=True)
    
    def _process_tick(self, tick_data: Dict[str, Any]):
        """
        Process individual tick
        
        Args:
            tick_data: Tick data dictionary
        """
        # Ensure timestamp is timezone-aware
        if "timestamp" in tick_data and tick_data["timestamp"].tzinfo is None:
            tick_data["timestamp"] = tick_data["timestamp"].replace(tzinfo=IST)
        
        # Store raw tick to database
        if self.enable_tick_storage and self.tick_processor:
            try:
                self.tick_processor.process_tick(tick_data)
                self.stats["ticks_stored"] += 1
            except Exception as e:
                logger.error(f"Error storing tick: {e}")
                self.stats["errors"] += 1
        
        # Generate candles from tick
        if self.enable_candle_generation and self.candle_processor:
            try:
                # Process through multi-granularity pipeline
                candles = self.candle_processor.process_tick(tick_data)
                
                if candles:
                    self.stats["candles_generated"] += len(candles)
                    
                    # Log candle generation
                    for candle in candles:
                        logger.info(f"🕯️  Candle generated: "
                                  f"{candle['interval']} | "
                                  f"Token: {candle['instrument_token']} | "
                                  f"Time: {candle['timestamp']} | "
                                  f"OHLC: {candle['open']:.2f}/{candle['high']:.2f}/"
                                  f"{candle['low']:.2f}/{candle['close']:.2f} | "
                                  f"Vol: {candle['volume']}")
                
            except Exception as e:
                logger.error(f"Error generating candles: {e}")
                self.stats["errors"] += 1
    
    async def start(self):
        """Start live data streaming"""
        if self._running:
            logger.warning("Live data processor already running")
            return
        
        self._running = True
        self.stats["start_time"] = utc_now()
        
        # Check market status at startup
        market_status = get_market_status_message()
        is_open, market_reason = is_market_open()
        
        logger.info("🚀 Starting Live Data Processor...")
        logger.info("=" * 80)
        logger.info(f"   Market Status: {market_status}")
        logger.info(f"   Symbols: {len(self.symbols)}")
        logger.info(f"   Mode: {self.mode}")
        logger.info(f"   Tick Storage: {'✅' if self.enable_tick_storage else '❌'}")
        logger.info(f"   Candle Generation: {'✅' if self.enable_candle_generation else '❌'}")
        logger.info("=" * 80)
        
        if not is_open:
            logger.info(f"ℹ️  Starting outside market hours ({market_reason}).")
            logger.info(f"ℹ️  WebSocket will connect, but data will only flow during market hours.")
            logger.info(f"ℹ️  Market Hours: Monday-Friday, 9:15 AM - 3:30 PM IST")
            logger.info("=" * 80)
        
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
            
            # Subscribe to symbols
            logger.info(f"📡 Subscribing to {len(self.symbols)} instruments...")
            await self.ws_client.subscribe(self.symbols)
            
            # Set mode
            logger.info(f"⚙️  Setting mode to '{self.mode}'...")
            await self.ws_client.set_mode(self.mode, self.symbols)
            
            logger.info("✅ Live data streaming active")
            logger.info("=" * 80)
            
            # Start heartbeat monitoring
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            # Keep running
            while self._running:
                await asyncio.sleep(1)
        
        except Exception as e:
            logger.error(f"❌ Error in live data processor: {e}", exc_info=True)
            raise
        
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop live data streaming"""
        if not self._running:
            return
        
        logger.info("🛑 Stopping Live Data Processor...")
        
        self._running = False
        
        try:
            # Close WebSocket
            if self.ws_client:
                await self.ws_client.close()
                logger.info("✅ WebSocket closed")
            
            # Flush candle processor
            if self.candle_processor:
                self.candle_processor.flush_all()
                logger.info("✅ Candle processor flushed")
            
            # Close tick processor
            if self.tick_processor:
                self.tick_processor.close()
                logger.info("✅ Tick processor closed")
            
            # Log final stats
            self._log_stats()
            
            logger.info("✅ Live Data Processor stopped")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    def _log_stats(self):
        """Log current statistics"""
        uptime = (utc_now() - self.stats["start_time"]).total_seconds() if self.stats["start_time"] else 0
        hours, remainder = divmod(int(uptime), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        last_tick_ago = "Never"
        if self.stats["last_tick_time"]:
            seconds_ago = (utc_now() - self.stats["last_tick_time"]).total_seconds()
            last_tick_ago = f"{int(seconds_ago)}s ago"
        
        logger.info("=" * 80)
        logger.info("📊 LIVE DATA PROCESSOR STATISTICS")
        logger.info("=" * 80)
        logger.info(f"   Uptime: {hours}h {minutes}m {seconds}s")
        logger.info(f"   Connected: {'🟢 YES' if self._connected else '🔴 NO'}")
        logger.info(f"   Ticks Received: {self.stats['ticks_received']:,}")
        logger.info(f"   Ticks Stored: {self.stats['ticks_stored']:,}")
        logger.info(f"   Candles Generated: {self.stats['candles_generated']:,}")
        logger.info(f"   Errors: {self.stats['errors']:,}")
        logger.info(f"   Last Tick: {last_tick_ago}")
        
        # Calculate tick batch size if processor exists
        if self.tick_processor and hasattr(self.tick_processor, '_tick_batch'):
            logger.info(f"   Tick Batch Size: {len(self.tick_processor._tick_batch)}")
        
        logger.info("=" * 80)
    
    async def _heartbeat_loop(self):
        """Background task to log heartbeat at regular intervals"""
        logger.info(f"💓 Heartbeat monitoring started (interval: {self.heartbeat_interval}s)")
        
        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                if not self._running:
                    break
                
                # Log heartbeat with key metrics
                uptime = (utc_now() - self.stats["start_time"]).total_seconds() if self.stats["start_time"] else 0
                
                # Market status
                is_open, market_reason = is_market_open()
                market_status = get_market_status_message()
                
                last_tick_status = "🟢 Active"
                if self.stats["last_tick_time"]:
                    seconds_ago = (utc_now() - self.stats["last_tick_time"]).total_seconds()
                    if seconds_ago > 30:
                        last_tick_status = f"⚠️  {int(seconds_ago)}s ago"
                    elif seconds_ago > 60:
                        last_tick_status = f"🔴 {int(seconds_ago)}s ago"
                    else:
                        last_tick_status = f"🟢 {int(seconds_ago)}s ago"
                else:
                    last_tick_status = "⚠️  No ticks yet"
                
                # Update heartbeat time
                self.stats["last_heartbeat_time"] = utc_now()
                
                # Connection status with context
                connection_status = "🟢" if self._connected else "🔴"
                
                # Build heartbeat message
                heartbeat_msg = (f"💓 HEARTBEAT | "
                               f"Uptime: {int(uptime//60)}m | "
                               f"Connected: {connection_status} | "
                               f"Market: {market_status} | "
                               f"Ticks: {self.stats['ticks_received']:,} | "
                               f"Stored: {self.stats['ticks_stored']:,} | "
                               f"Candles: {self.stats['candles_generated']:,} | "
                               f"Errors: {self.stats['errors']} | "
                               f"Last Tick: {last_tick_status}")
                
                logger.info(heartbeat_msg)
                
                # Add explanation if connected but no data (market closed scenario)
                if self._connected and not is_open and self.stats["ticks_received"] == 0:
                    logger.info(f"ℹ️  WebSocket connected but market is {market_reason}. "
                              f"Data will flow when market opens.")
                
                # Log detailed stats every 5 minutes
                if int(uptime) % 300 == 0 and int(uptime) > 0:
                    self._log_stats()
                
            except asyncio.CancelledError:
                logger.info("💓 Heartbeat monitoring stopped")
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(self.heartbeat_interval)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics"""
        stats = {
            **self.stats,
            "running": self._running,
            "connected": self._connected
        }
        
        if self.tick_processor:
            stats["tick_processor"] = self.tick_processor.get_stats()
        
        if self.candle_processor:
            stats["candle_processor"] = self.candle_processor.get_stats()
        
        return stats


async def main():
    """Main entry point for testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Live Data Processor")
    parser.add_argument("--symbols", help="Comma-separated instrument tokens", default=None)
    parser.add_argument("--mode", help="WebSocket mode (ltp, quote, full)", default="full")
    parser.add_argument("--intervals", help="Comma-separated intervals", default=None)
    parser.add_argument(
        "--no-tick-storage",
        action="store_true",
        help="Disable raw tick storage"
    )
    parser.add_argument(
        "--no-candles",
        action="store_true",
        help="Disable candle generation"
    )
    
    args = parser.parse_args()
    
    # Parse symbols
    symbols = None
    if args.symbols:
        symbols = [int(t.strip()) for t in args.symbols.split(",")]
    
    # Parse intervals
    intervals = None
    if args.intervals:
        intervals = [i.strip() for i in args.intervals.split(",")]
    
    # Create processor
    processor = RealtimeStreamProcessor(
        symbols=symbols,
        mode=args.mode,
        intervals=intervals,
        enable_tick_storage=not args.no_tick_storage,
        enable_candle_generation=not args.no_candles
    )
    
    # Handle shutdown gracefully
    import signal
    
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        asyncio.create_task(processor.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start processor
    try:
        await processor.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await processor.stop()


if __name__ == "__main__":
    asyncio.run(main())
