"""
Test script for Historical Data Loader

This script tests the historical data loader functionality:
1. Configuration loading
2. MinIO connectivity
3. Symbol mapping
4. Data fetching from Kite API
5. Partitioned storage to MinIO
6. Existence checks (incremental loading)
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from core.utils.logger import setup_logging, get_logger
from services.data_service.load.historical_data import HistoricalDataLoader

# Setup logging
setup_logging(service_name="test_historical_loader", log_level="DEBUG")
logger = get_logger(__name__)

IST = ZoneInfo("Asia/Kolkata")


def test_configuration():
    """Test 1: Configuration Loading"""
    logger.info("=" * 80)
    logger.info("TEST 1: Configuration Loading")
    logger.info("=" * 80)
    
    try:
        loader = HistoricalDataLoader()
        
        logger.info(f"✅ Loader initialized successfully")
        logger.info(f"   Symbols: {len(loader.symbols)} instruments")
        logger.info(f"   Intervals: {', '.join(loader.intervals)}")
        logger.info(f"   Schedule Time: {loader.schedule_time}")
        logger.info(f"   MinIO Bucket: {loader.bucket}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Configuration test failed: {e}")
        return False


def test_minio_connectivity():
    """Test 2: MinIO Connectivity"""
    logger.info("=" * 80)
    logger.info("TEST 2: MinIO Connectivity")
    logger.info("=" * 80)
    
    try:
        loader = HistoricalDataLoader()
        
        # Check if bucket exists
        exists = loader.minio_client.bucket_exists(loader.bucket)
        
        if exists:
            logger.info(f"✅ MinIO bucket '{loader.bucket}' exists")
            
            # List some objects
            objects = list(loader.minio_client.list_objects(loader.bucket, prefix="historical/", max_keys=5))
            logger.info(f"   Found {len(objects)} sample objects")
            
            for obj in objects[:3]:
                logger.info(f"   - {obj.object_name}")
            
            return True
        else:
            logger.error(f"❌ MinIO bucket '{loader.bucket}' not found")
            return False
            
    except Exception as e:
        logger.error(f"❌ MinIO connectivity test failed: {e}")
        return False


def test_symbol_mapping():
    """Test 3: Symbol Mapping"""
    logger.info("=" * 80)
    logger.info("TEST 3: Symbol Name Mapping")
    logger.info("=" * 80)
    
    try:
        loader = HistoricalDataLoader()
        
        logger.info(f"Symbol mapping loaded: {len(loader.symbol_mapping)} symbols")
        
        # Test mapping for configured symbols
        for token in loader.symbols[:5]:
            symbol = loader.get_symbol_name(token)
            logger.info(f"   {token} → {symbol}")
        
        logger.info("✅ Symbol mapping test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Symbol mapping test failed: {e}")
        return False


def test_path_generation():
    """Test 4: MinIO Path Generation"""
    logger.info("=" * 80)
    logger.info("TEST 4: MinIO Path Generation")
    logger.info("=" * 80)
    
    try:
        loader = HistoricalDataLoader()
        
        # Test path for different timestamps and intervals
        test_cases = [
            (datetime(2025, 10, 18, 9, 15, tzinfo=IST), "minute"),
            (datetime(2025, 10, 18, 14, 30, tzinfo=IST), "5minute"),
            (datetime(2025, 10, 18, 15, 0, tzinfo=IST), "day"),
        ]
        
        for timestamp, interval in test_cases:
            path = loader.generate_minio_path("NIFTY50", timestamp, interval)
            logger.info(f"   {timestamp.strftime('%Y-%m-%d %H:%M')} ({interval})")
            logger.info(f"   → {path}")
        
        logger.info("✅ Path generation test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Path generation test failed: {e}")
        return False


def test_existence_check():
    """Test 5: Data Existence Check"""
    logger.info("=" * 80)
    logger.info("TEST 5: Data Existence Check")
    logger.info("=" * 80)
    
    try:
        loader = HistoricalDataLoader()
        
        # Check for recent date
        yesterday = datetime.now(IST) - timedelta(days=1)
        yesterday = yesterday.replace(hour=9, minute=15, second=0, microsecond=0)
        
        symbol = loader.get_symbol_name(loader.symbols[0])
        
        logger.info(f"Checking data for: {symbol} on {yesterday.date()}")
        
        for interval in ["minute", "day"]:
            exists = loader.check_existing_data(symbol, yesterday, interval)
            status = "✅ EXISTS" if exists else "⏭️ NOT FOUND"
            logger.info(f"   {interval}: {status}")
        
        logger.info("✅ Existence check test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Existence check test failed: {e}")
        return False


def test_data_fetch_small():
    """Test 6: Small Data Fetch (5 minutes)"""
    logger.info("=" * 80)
    logger.info("TEST 6: Small Data Fetch (5 minutes)")
    logger.info("=" * 80)
    
    try:
        loader = HistoricalDataLoader()
        
        # Fetch 5 minutes of data for testing
        yesterday = datetime.now(IST) - timedelta(days=1)
        from_time = yesterday.replace(hour=9, minute=15, second=0, microsecond=0)
        to_time = from_time + timedelta(minutes=5)
        
        symbol_token = loader.symbols[0]
        symbol_name = loader.get_symbol_name(symbol_token)
        
        logger.info(f"Fetching data for: {symbol_name} ({symbol_token})")
        logger.info(f"   From: {from_time}")
        logger.info(f"   To: {to_time}")
        
        df = loader.fetch_historical_data(
            instrument_token=symbol_token,
            interval="minute",
            from_date=from_time,
            to_date=to_time
        )
        
        if df is not None and not df.empty:
            logger.info(f"✅ Fetched {len(df)} candles")
            logger.info(f"   Columns: {list(df.columns)}")
            logger.info(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
            logger.info(f"   Sample data:")
            logger.info(f"{df.head(2).to_string()}")
            return True
        else:
            logger.warning("⚠️ No data returned (might be non-trading day)")
            return True  # Not a failure
            
    except Exception as e:
        logger.error(f"❌ Data fetch test failed: {e}")
        return False


def test_full_workflow():
    """Test 7: Full Workflow (Fetch + Store)"""
    logger.info("=" * 80)
    logger.info("TEST 7: Full Workflow (Fetch + Store to MinIO)")
    logger.info("=" * 80)
    
    try:
        loader = HistoricalDataLoader()
        
        # Use yesterday's date
        yesterday = datetime.now(IST) - timedelta(days=1)
        from_time = yesterday.replace(hour=14, minute=0, second=0, microsecond=0)
        to_time = from_time + timedelta(minutes=10)
        
        symbol_token = loader.symbols[0]
        symbol_name = loader.get_symbol_name(symbol_token)
        interval = "minute"
        
        logger.info(f"Full workflow test for: {symbol_name}")
        logger.info(f"   Date: {yesterday.date()}")
        logger.info(f"   Time: {from_time.strftime('%H:%M')} - {to_time.strftime('%H:%M')}")
        logger.info(f"   Interval: {interval}")
        
        # Step 1: Fetch
        logger.info("Step 1: Fetching data from Kite API...")
        df = loader.fetch_historical_data(
            instrument_token=symbol_token,
            interval=interval,
            from_date=from_time,
            to_date=to_time
        )
        
        if df is None or df.empty:
            logger.warning("⚠️ No data fetched (might be non-trading day)")
            return True
        
        logger.info(f"   ✅ Fetched {len(df)} candles")
        
        # Step 2: Store
        logger.info("Step 2: Storing to MinIO...")
        success = loader.store_to_minio(df, symbol_name, interval)
        
        if success:
            logger.info("   ✅ Data stored successfully")
            
            # Step 3: Verify
            logger.info("Step 3: Verifying stored data...")
            exists = loader.check_existing_data(symbol_name, from_time, interval)
            
            if exists:
                logger.info("   ✅ Data verified in MinIO")
                logger.info("✅ Full workflow test PASSED")
                return True
            else:
                logger.error("   ❌ Data not found after storage")
                return False
        else:
            logger.error("   ❌ Storage failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Full workflow test failed: {e}", exc_info=True)
        return False


def run_all_tests():
    """Run all tests"""
    logger.info("🚀 Starting Historical Data Loader Tests")
    logger.info("=" * 80)
    
    tests = [
        ("Configuration", test_configuration),
        ("MinIO Connectivity", test_minio_connectivity),
        ("Symbol Mapping", test_symbol_mapping),
        ("Path Generation", test_path_generation),
        ("Existence Check", test_existence_check),
        ("Small Data Fetch", test_data_fetch_small),
        ("Full Workflow", test_full_workflow),
    ]
    
    results = {}
    
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            logger.error(f"Test '{name}' crashed: {e}")
            results[name] = False
        
        logger.info("")
    
    # Summary
    logger.info("=" * 80)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 80)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {name}")
    
    logger.info("=" * 80)
    logger.info(f"Results: {passed}/{total} tests passed")
    logger.info("=" * 80)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
