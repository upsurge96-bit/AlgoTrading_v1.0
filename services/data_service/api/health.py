"""
Health Check and Monitoring Endpoints
Provides health and readiness checks for deployment orchestration
"""

import logging
import time
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.data_service.container import get_dependencies, DependencyProvider
from services.data_service.config import get_settings
from services.data_service.exceptions import DatabaseError, KafkaError, MinIOError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["health"])


class HealthStatus(str, Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class DependencyHealth(BaseModel):
    """Health status of a single dependency"""
    name: str
    status: HealthStatus
    message: Optional[str] = None
    response_time_ms: Optional[float] = None
    last_checked: datetime


class HealthResponse(BaseModel):
    """Complete health check response"""
    status: HealthStatus
    version: str
    uptime_seconds: float
    timestamp: datetime
    dependencies: List[DependencyHealth]
    details: Optional[Dict[str, Any]] = None


class ReadinessResponse(BaseModel):
    """Readiness check response"""
    ready: bool
    message: str
    dependencies: List[DependencyHealth]


# Track service start time
_start_time = time.time()


async def check_database_health() -> DependencyHealth:
    """
    Check database connectivity
    
    Returns:
        DependencyHealth for database
    """
    start = time.time()
    
    try:
        # Import here to avoid circular dependencies
        from core.db.session import get_session
        
        # Test database connection
        async with get_session() as session:
            await session.execute("SELECT 1")
        
        elapsed = (time.time() - start) * 1000
        
        return DependencyHealth(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Connected",
            response_time_ms=round(elapsed, 2),
            last_checked=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        
        elapsed = (time.time() - start) * 1000
        
        return DependencyHealth(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message=str(e),
            response_time_ms=round(elapsed, 2),
            last_checked=datetime.utcnow()
        )


async def check_kafka_health() -> Optional[DependencyHealth]:
    """
    Check Kafka connectivity
    
    Returns:
        DependencyHealth for Kafka (None if disabled)
    """
    settings = get_settings()
    
    if not settings.kafka.enabled:
        return None
    
    start = time.time()
    
    try:
        # Test Kafka connection by checking cluster metadata
        from confluent_kafka.admin import AdminClient
        
        admin = AdminClient({
            'bootstrap.servers': ','.join(settings.kafka.bootstrap_servers)
        })
        
        # Get cluster metadata (timeout 5 seconds)
        metadata = admin.list_topics(timeout=5)
        
        elapsed = (time.time() - start) * 1000
        
        return DependencyHealth(
            name="kafka",
            status=HealthStatus.HEALTHY,
            message=f"Connected to {len(metadata.brokers)} brokers",
            response_time_ms=round(elapsed, 2),
            last_checked=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Kafka health check failed: {e}")
        
        elapsed = (time.time() - start) * 1000
        
        return DependencyHealth(
            name="kafka",
            status=HealthStatus.UNHEALTHY,
            message=str(e),
            response_time_ms=round(elapsed, 2),
            last_checked=datetime.utcnow()
        )


async def check_minio_health(deps: DependencyProvider) -> Optional[DependencyHealth]:
    """
    Check MinIO connectivity
    
    Args:
        deps: Dependency provider
        
    Returns:
        DependencyHealth for MinIO (None if disabled)
    """
    settings = get_settings()
    
    if not settings.minio.enabled:
        return None
    
    start = time.time()
    
    try:
        minio = deps.minio_handler
        if minio is None:
            raise MinIOError("MinIO handler not initialized")
        
        # Check if bucket exists
        bucket_exists = minio.client.bucket_exists(settings.minio.bucket)
        
        elapsed = (time.time() - start) * 1000
        
        if bucket_exists:
            return DependencyHealth(
                name="minio",
                status=HealthStatus.HEALTHY,
                message=f"Bucket '{settings.minio.bucket}' accessible",
                response_time_ms=round(elapsed, 2),
                last_checked=datetime.utcnow()
            )
        else:
            return DependencyHealth(
                name="minio",
                status=HealthStatus.UNHEALTHY,
                message=f"Bucket '{settings.minio.bucket}' not found",
                response_time_ms=round(elapsed, 2),
                last_checked=datetime.utcnow()
            )
        
    except Exception as e:
        logger.error(f"MinIO health check failed: {e}")
        
        elapsed = (time.time() - start) * 1000
        
        return DependencyHealth(
            name="minio",
            status=HealthStatus.UNHEALTHY,
            message=str(e),
            response_time_ms=round(elapsed, 2),
            last_checked=datetime.utcnow()
        )


async def check_auth_service_health(deps: DependencyProvider) -> DependencyHealth:
    """
    Check auth service connectivity
    
    Args:
        deps: Dependency provider
        
    Returns:
        DependencyHealth for auth service
    """
    start = time.time()
    
    try:
        # Test auth service by checking token (will use cached token)
        token = await deps.auth_client.get_access_token()
        
        elapsed = (time.time() - start) * 1000
        
        if token:
            return DependencyHealth(
                name="auth_service",
                status=HealthStatus.HEALTHY,
                message="Token available",
                response_time_ms=round(elapsed, 2),
                last_checked=datetime.utcnow()
            )
        else:
            return DependencyHealth(
                name="auth_service",
                status=HealthStatus.DEGRADED,
                message="No token available",
                response_time_ms=round(elapsed, 2),
                last_checked=datetime.utcnow()
            )
        
    except Exception as e:
        logger.error(f"Auth service health check failed: {e}")
        
        elapsed = (time.time() - start) * 1000
        
        return DependencyHealth(
            name="auth_service",
            status=HealthStatus.UNHEALTHY,
            message=str(e),
            response_time_ms=round(elapsed, 2),
            last_checked=datetime.utcnow()
        )


@router.get("/health", response_model=HealthResponse)
async def health_check(deps: DependencyProvider = Depends(get_dependencies)):
    """
    Comprehensive health check
    
    Checks all dependencies and returns overall health status
    Used for monitoring and alerting
    
    Returns:
        HealthResponse with status of all dependencies
    """
    settings = get_settings()
    
    # Check all dependencies
    dependencies = []
    
    # Database (required)
    db_health = await check_database_health()
    dependencies.append(db_health)
    
    # Kafka (optional)
    kafka_health = await check_kafka_health()
    if kafka_health:
        dependencies.append(kafka_health)
    
    # MinIO (optional)
    minio_health = await check_minio_health(deps)
    if minio_health:
        dependencies.append(minio_health)
    
    # Auth service (required)
    auth_health = await check_auth_service_health(deps)
    dependencies.append(auth_health)
    
    # Determine overall status
    unhealthy = [d for d in dependencies if d.status == HealthStatus.UNHEALTHY]
    degraded = [d for d in dependencies if d.status == HealthStatus.DEGRADED]
    
    if unhealthy:
        overall_status = HealthStatus.UNHEALTHY
    elif degraded:
        overall_status = HealthStatus.DEGRADED
    else:
        overall_status = HealthStatus.HEALTHY
    
    # Calculate uptime
    uptime = time.time() - _start_time
    
    response = HealthResponse(
        status=overall_status,
        version=settings.service.version,
        uptime_seconds=round(uptime, 2),
        timestamp=datetime.utcnow(),
        dependencies=dependencies,
        details={
            "environment": settings.service.environment,
            "workers_enabled": {
                "live_data": settings.workers.live_streaming,
                "historical_data": settings.workers.historical_fetch
            }
        }
    )
    
    # Set HTTP status based on health
    status_code = status.HTTP_200_OK
    if overall_status == HealthStatus.UNHEALTHY:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif overall_status == HealthStatus.DEGRADED:
        status_code = status.HTTP_200_OK  # Still available but degraded
    
    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(mode='json')
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check(deps: DependencyProvider = Depends(get_dependencies)):
    """
    Kubernetes readiness probe
    
    Checks if service is ready to accept traffic
    More strict than health check - all critical dependencies must be healthy
    
    Returns:
        ReadinessResponse with ready status
    """
    # Check critical dependencies
    dependencies = []
    
    # Database (required)
    db_health = await check_database_health()
    dependencies.append(db_health)
    
    # Auth service (required)
    auth_health = await check_auth_service_health(deps)
    dependencies.append(auth_health)
    
    # Check if all critical dependencies are healthy
    all_healthy = all(
        d.status == HealthStatus.HEALTHY
        for d in dependencies
    )
    
    if all_healthy:
        response = ReadinessResponse(
            ready=True,
            message="Service is ready",
            dependencies=dependencies
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=response.dict()
        )
    else:
        unhealthy = [d.name for d in dependencies if d.status != HealthStatus.HEALTHY]
        response = ReadinessResponse(
            ready=False,
            message=f"Service not ready: {', '.join(unhealthy)} unhealthy",
            dependencies=dependencies
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response.dict()
        )


@router.get("/live")
async def liveness_check():
    """
    Kubernetes liveness probe
    
    Simple check that service is alive
    Returns 200 if process is running
    
    Returns:
        Simple status message
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }
