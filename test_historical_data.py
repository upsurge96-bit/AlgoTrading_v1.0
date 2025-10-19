"""
Test Historical Data Fetching
Quick test to fetch historical data from Kite API
"""

import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from services.data_service.extraction.auth_client import AuthClient
from services.data_service.extraction.historical_data import HistoricalDataFetcher

def test_historical_data():
    """Test fetching historical data"""
    print("=" * 80)
    print("Testing Historical Data Fetch")
    print("=" * 80)
    
    # Initialize
    auth_client = AuthClient()
    fetcher = HistoricalDataFetcher(auth_client=auth_client)
    
    # Test with one instrument (RELIANCE - 738561)
    instrument_token = 738561
    interval = "day"  # Daily candles
    
    # Fetch last 30 days of data
    to_date = datetime.now()
    from_date = to_date - timedelta(days=30)
    
    print(f"\n📊 Fetching {interval} data for instrument {instrument_token}")
    print(f"   From: {from_date.strftime('%Y-%m-%d')}")
    print(f"   To: {to_date.strftime('%Y-%m-%d')}")
    print("-" * 80)
    
    try:
        df = fetcher.fetch_historical_data(
            instrument_token=instrument_token,
            interval=interval,
            from_date=from_date,
            to_date=to_date
        )
        
        if df is not None and not df.empty:
            print(f"\n✅ SUCCESS! Fetched {len(df)} candles\n")
            print("First 5 candles:")
            print(df.head())
            print("\nLast 5 candles:")
            print(df.tail())
            print("\nSummary:")
            print(df.describe())
            
            return True
        else:
            print("\n❌ No data returned")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_historical_data()
    sys.exit(0 if success else 1)
