"""
Data Service — Main Entry Point
Provides FastAPI endpoints and orchestrates data workers

Production-ready with:
- Dependency injection container
- Structured error handling
- Health check endpoints
- Prometheus metrics
- Graceful shutdown
"""

import os
import asyncio
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from core.utils.logger import setup_logging, get_logger
from services.data_service.config import get_settings
from services.data_service.container import get_container, reset_container
from services.data_service.middleware import ErrorHandlingMiddleware

# Initialize logger
setup_logging(
    config_path="/app/config/logging.yaml",
    service_name="data_service",
    environment=os.getenv("ENVIRONMENT", "development")
)
logger = get_logger("data_service")

# Load settings
settings = get_settings()
logger.info(f"✅ Loaded settings for environment: {settings.service.environment}")

# Global worker coordinator and shutdown event
worker_coordinator = None
shutdown_event = asyncio.Event()



async def shutdown_handler(sig: signal.Signals):
    """
    Handle shutdown signals gracefully
    
    Args:
        sig: Signal received (SIGTERM, SIGINT)
    """
    logger.info(f"Received signal {sig.name}, initiating graceful shutdown...")
    shutdown_event.set()


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    loop = asyncio.get_event_loop()
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown_handler(s))
        )
    
    logger.info("✅ Signal handlers configured")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    # Startup
    logger.info("🚀 Starting Data Service...")
    
    global worker_coordinator
    
    try:
        # Initialize service container
        container = get_container(settings)
        await container.initialize()
        logger.info("✅ Service container initialized")
        
        # Setup signal handlers
        # setup_signal_handlers()  # Disabled for Windows compatibility
        
        # Start background workers if enabled
        if settings.workers.enable_live_data or settings.workers.enable_historical_data:
            logger.info("Starting background workers...")
            
            from services.data_service.workers import DataServiceCoordinator
            
            worker_coordinator = DataServiceCoordinator(
                instrument_tokens=settings.instruments.tokens,
                enable_live_streaming=settings.workers.enable_live_data,
                enable_historical_fetch=settings.workers.enable_historical_data,
                enable_scheduler=settings.workers.enable_scheduler,
                websocket_mode=settings.websocket.mode
            )
            
            # Start coordinator
            asyncio.create_task(worker_coordinator.start())
            logger.info("✅ Background workers started")
        else:
            logger.info("Workers disabled in configuration")
        
        # Run database migrations if enabled
        if os.getenv("MIGRATE_ON_STARTUP", "true").lower() == "true":
            logger.info("Running database migrations...")
            try:
                from services.data_service.db.migrate import run_migration
                run_migration()
                logger.info("✅ Database migrations completed")
            except Exception as e:
                logger.error(f"❌ Database migration failed: {e}")
        
        logger.info("✅ Data Service startup complete")
        
    except Exception as e:
        logger.critical(f"❌ Failed to start Data Service: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Data Service...")
    
    try:
        # Stop workers first
        if worker_coordinator:
            logger.info("Stopping background workers...")
            await worker_coordinator.stop()
            logger.info("✅ Workers stopped")
        
        # Cleanup container
        container = get_container()
        await container.cleanup()
        reset_container()
        logger.info("✅ Service container cleaned up")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    logger.info("✅ Data Service shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.service.name,
    description="Market data streaming and storage service for AlgoTrading platform",
    version=settings.service.version,
    lifespan=lifespan
)

# Add error handling middleware
app.add_middleware(ErrorHandlingMiddleware)
logger.info("✅ Error handling middleware added")

# Mount health check routes
try:
    from services.data_service.api.health import router as health_router
    app.include_router(health_router)
    logger.info("✅ Mounted health check endpoints")
except Exception as e:
    logger.error(f"Failed to mount health endpoints: {e}")

# Mount API routes
try:
    from services.data_service.api.routes import router as api_router
    app.include_router(api_router, prefix="/api", tags=["data"])
    logger.info("✅ Mounted data service API routes")
except Exception as e:
    logger.error(f"Failed to mount API routes: {e}")




@app.get("/")
def root():
    """Root endpoint with service information"""
    return {
        "service": settings.service.name,
        "version": settings.service.version,
        "environment": settings.service.environment,
        "description": "Market data streaming and storage service",
        "endpoints": {
            "health": "/api/v1/health",
            "readiness": "/api/v1/ready",
            "liveness": "/api/v1/live",
            "metrics": "/metrics",
            "api": "/api",
            "docs": "/docs",
            "redoc": "/redoc"
        },
        "workers": {
            "live_data": settings.workers.enable_live_data,
            "historical_data": settings.workers.enable_historical_data,
            "scheduler": settings.workers.enable_scheduler
        }
    }


@app.get("/health")
async def legacy_health():
    """
    Legacy health endpoint (deprecated)
    
    Use /api/v1/health for comprehensive health checks
    """
    return JSONResponse(content={
        "status": "ok",
        "service": settings.service.name,
        "version": settings.service.version,
        "note": "Use /api/v1/health for detailed health information"
    })


@app.get("/metrics")
def metrics():
    """
    Prometheus metrics endpoint
    
    Exposes service metrics for monitoring
    """
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting Data Service in standalone mode...")
    
    uvicorn.run(
        "main:app",
        host=settings.service.host,
        port=settings.service.port,
        log_level=settings.monitoring.log_level.lower(),
        reload=os.getenv("RELOAD", "false").lower() == "true"
    )


