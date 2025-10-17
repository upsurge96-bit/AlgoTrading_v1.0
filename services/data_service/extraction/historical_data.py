import requests
import pandas as pd
from datetime import datetime
import sys
import logging

def get_historical_data(api_key, access_token, instrument_token, interval, from_date, to_date, continuous=0, oi=0, timeout=10, max_retries=3):
    """
    Fetch historical candle data from Kite API.

    Parameters:
        api_key (str): Your Kite API key
        access_token (str): Your Kite access token
        instrument_token (int): Instrument token (from instruments API)
        interval (str): Interval for candles ('minute', '5minute', 'day', etc.)
        from_date (str): Start date in 'YYYY-MM-DD HH:MM:SS' format
        to_date (str): End date in 'YYYY-MM-DD HH:MM:SS' format
        continuous (int): 1 for continuous futures data
        oi (int): 1 to include open interest data
        timeout (int): Request timeout in seconds
        max_retries (int): Maximum number of retries for request

    Returns:
        pandas.DataFrame: DataFrame of historical candles
    """
    # Accept datetime or string inputs
    if isinstance(from_date, datetime):
        from_date = from_date.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(to_date, datetime):
        to_date = to_date.strftime("%Y-%m-%d %H:%M:%S")

    url = f"https://api.kite.trade/instruments/historical/{instrument_token}/{interval}"
    headers = {
        "X-Kite-Version": "3",
        "Authorization": f"token {api_key}:{access_token}"
    }

    params = {
        "from": from_date,
        "to": to_date,
        "continuous": continuous,
        "oi": oi
    }

    # Use a session with retries
    session = requests.Session()
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    retries = Retry(total=max_retries, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))

    try:
        response = session.get(url, headers=headers, params=params, timeout=timeout)
    except requests.RequestException as e:
        # Don't exit the process from a library function; raise an exception
        raise RuntimeError(f"Network error while fetching historical data: {e}")

    if response.status_code != 200:
        # Raise to let caller decide how to handle
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

    data = response.json()

    if data.get("status") != "success":
        raise RuntimeError(f"API call failed: {data}")

    candles = data.get("data", {}).get("candles", [])

    if not candles:
        # Return empty DataFrame instead of exiting
        return pd.DataFrame()

    # Define columns based on whether OI is included
    columns = ["timestamp", "open", "high", "low", "close", "volume"]
    if oi:
        columns.append("oi")

    df = pd.DataFrame(candles, columns=columns)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


# add module logger
logger = logging.getLogger(__name__)

if __name__ == "__main__":
	# configure logging only when running this module directly
	logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

	# Example usage (replace placeholders with your credentials)
	# Avoid embedding secrets in the file; use environment variables or a secrets manager.
	api_key = "<YOUR_API_KEY>"
	access_token = "<YOUR_ACCESS_TOKEN>"
	instrument_token = 5633  # NSE-ACC example
	interval = "minute"
	from_date = "2017-12-15 09:15:00"
	to_date = "2017-12-15 09:20:00"

	try:
		df = get_historical_data(api_key, access_token, instrument_token, interval, from_date, to_date, continuous=0, oi=0)
		if not df.empty:
			output_file = f"historical_data_{instrument_token}_{interval}.csv"
			df.to_csv(output_file, index=False)
			logger.info("Data saved to %s", output_file)
			logger.info("\n%s", df.head().to_string())
		else:
			logger.warning("No data returned for the given range.")
	except Exception as e:
		logger.exception("Error fetching historical data: %s", e)
