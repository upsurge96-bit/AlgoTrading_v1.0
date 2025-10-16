# services/data-service/api/routes.py

from fastapi import APIRouter, HTTPException, Request
from services.data_service.ingestion.fetcher import fetch_historical_ccxt
from core.utils.logger import get_logger
import time

router = APIRouter()
logger = get_logger("data_service.api")

@router.get("/health")
async def health_check():
    logger.debug("💓 Health check endpoint called")
    return {"status": "ok", "service": "data-service"}

@router.post("/fetch")
async def fetch_data(
    request: Request,
    symbol: str = "BTC/USDT",
    timeframe: str = "1m",
    limit: int = 100
):
    start_time = time.time()
    client_host = request.client.host if request.client else "unknown"

    logger.info(
        "📥 /fetch endpoint called | client=%s | symbol=%s | timeframe=%s | limit=%d",
        client_host, symbol, timeframe, limit
    )

    try:
        df = fetch_historical_ccxt(symbol, timeframe=timeframe, limit=limit)
        rows = len(df) if df is not None else 0
        duration = round(time.time() - start_time, 3)

        logger.info(
            "✅ Successfully fetched %d rows for %s [%s] in %ss",
            rows, symbol, timeframe, duration
        )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "rows": rows,
            "duration": duration,
            "status": "success"
        }

    except Exception as e:
        logger.exception(
            "❌ Error fetching data for %s [%s]: %s",
            symbol, timeframe, e
        )
        raise HTTPException(status_code=500, detail=str(e))
