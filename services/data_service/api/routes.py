# services/data-service/api/routes.py

from fastapi import APIRouter, HTTPException, Request
from core.utils.logger import get_logger
import time

router = APIRouter()
logger = get_logger("data_service.api")

@router.get("/health")
async def health_check():
    logger.debug("💓 Health check endpoint called")
    return {"status": "ok", "service": "data-service"}

