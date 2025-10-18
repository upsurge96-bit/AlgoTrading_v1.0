"""
Dependency Injection Container
Manages service lifecycle and dependencies
"""

from typing import Optional, Dict, Any, Callable
from contextlib import asynccontextmanager
import logging

from services.data_service.config import Settings, get_settings
from services.data_service.extraction.auth_client import AuthClient
from services.data_service.processors.tick_processor import TickProcessor, OHLCVProcessor
from services.data_service.processors.minio_handler import MinIOHandler
from services.data_service.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class ServiceContainer:
    """
    Dependency Injection Container
    
    Manages the lifecycle of all services and their dependencies
    Implements singleton pattern for shared resources
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize service container
        
        Args:
            settings: Application settings (defaults to global settings)
        """
        self.settings = settings or get_settings()
        self._services: Dict[str, Any] = {}
        self._initialized = False
        logger.info("ServiceContainer initialized")
    
    @property
    def auth_client(self) -> AuthClient:
        """Get or create AuthClient instance"""
        if "auth_client" not in self._services:
            self._services["auth_client"] = AuthClient(
                auth_service_url=self.settings.auth_service.url,
                timeout=self.settings.auth_service.timeout,
                cache_ttl=self.settings.auth_service.cache_ttl
            )
            logger.info("AuthClient created")
        return self._services["auth_client"]
    
    @property
    def minio_handler(self) -> Optional[MinIOHandler]:
        """Get or create MinIOHandler instance"""
        if not self.settings.minio.enabled:
            return None
            
        if "minio_handler" not in self._services:
            self._services["minio_handler"] = MinIOHandler(
                endpoint=self.settings.minio.endpoint,
                access_key=self.settings.minio.access_key,
                secret_key=self.settings.minio.secret_key,
                bucket=self.settings.minio.bucket,
                secure=self.settings.minio.secure
            )
            logger.info("MinIOHandler created")
        return self._services["minio_handler"]
    
    @property
    def tick_processor(self) -> TickProcessor:
        """Get or create TickProcessor instance"""
        if "tick_processor" not in self._services:
            self._services["tick_processor"] = TickProcessor(
                minio_handler=self.minio_handler,
                enable_kafka=self.settings.kafka.enabled
            )
            logger.info("TickProcessor created")
        return self._services["tick_processor"]
    
    @property
    def ohlcv_processor(self) -> OHLCVProcessor:
        """Get or create OHLCVProcessor instance"""
        if "ohlcv_processor" not in self._services:
            self._services["ohlcv_processor"] = OHLCVProcessor(
                minio_handler=self.minio_handler
            )
            logger.info("OHLCVProcessor created")
        return self._services["ohlcv_processor"]
    
    async def initialize(self):
        """Initialize all services"""
        if self._initialized:
            logger.warning("ServiceContainer already initialized")
            return
        
        logger.info("Initializing ServiceContainer...")
        
        try:
            # Initialize services that need async setup
            if self.settings.kafka.enabled:
                # Initialize Kafka connections
                pass
            
            if self.settings.minio.enabled:
                # Ensure MinIO bucket exists
                minio = self.minio_handler
                if minio:
                    # MinIO client will create bucket if it doesn't exist
                    logger.info(f"MinIO bucket ready: {self.settings.minio.bucket}")
            
            self._initialized = True
            logger.info("✅ ServiceContainer initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ServiceContainer: {e}")
            raise ConfigurationError(f"Service initialization failed: {e}")
    
    async def cleanup(self):
        """Cleanup all services"""
        logger.info("Cleaning up ServiceContainer...")
        
        try:
            # Close tick processor
            if "tick_processor" in self._services:
                await self._services["tick_processor"].close()
                logger.info("TickProcessor closed")
            
            # Close OHLCV processor
            if "ohlcv_processor" in self._services:
                await self._services["ohlcv_processor"].close()
                logger.info("OHLCVProcessor closed")
            
            # Clear services
            self._services.clear()
            self._initialized = False
            
            logger.info("✅ ServiceContainer cleaned up")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def get_service(self, service_name: str) -> Any:
        """
        Get a service by name
        
        Args:
            service_name: Name of the service
            
        Returns:
            Service instance
            
        Raises:
            KeyError: If service not found
        """
        if service_name not in self._services:
            raise KeyError(f"Service not found: {service_name}")
        return self._services[service_name]
    
    def register_service(self, service_name: str, service_instance: Any):
        """
        Register a custom service
        
        Args:
            service_name: Name to register the service under
            service_instance: Service instance
        """
        self._services[service_name] = service_instance
        logger.info(f"Service registered: {service_name}")
    
    @asynccontextmanager
    async def lifespan(self):
        """
        Context manager for service lifecycle
        
        Usage:
            async with container.lifespan():
                # Use services
                pass
        """
        try:
            await self.initialize()
            yield self
        finally:
            await self.cleanup()


# Global container instance
_container: Optional[ServiceContainer] = None


def get_container(settings: Optional[Settings] = None) -> ServiceContainer:
    """
    Get global service container (singleton)
    
    Args:
        settings: Optional settings to use for first initialization
        
    Returns:
        ServiceContainer instance
    """
    global _container
    if _container is None:
        _container = ServiceContainer(settings=settings)
    return _container


def reset_container():
    """Reset global container (useful for testing)"""
    global _container
    _container = None


class DependencyProvider:
    """
    Helper class to provide dependencies to FastAPI endpoints
    
    Usage in FastAPI:
        @app.get("/endpoint")
        async def endpoint(deps: DependencyProvider = Depends(get_dependencies)):
            auth_client = deps.auth_client
    """
    
    def __init__(self, container: ServiceContainer):
        """Initialize with container"""
        self.container = container
    
    @property
    def auth_client(self) -> AuthClient:
        """Get AuthClient"""
        return self.container.auth_client
    
    @property
    def tick_processor(self) -> TickProcessor:
        """Get TickProcessor"""
        return self.container.tick_processor
    
    @property
    def ohlcv_processor(self) -> OHLCVProcessor:
        """Get OHLCVProcessor"""
        return self.container.ohlcv_processor
    
    @property
    def minio_handler(self) -> Optional[MinIOHandler]:
        """Get MinIOHandler"""
        return self.container.minio_handler
    
    @property
    def settings(self) -> Settings:
        """Get Settings"""
        return self.container.settings


def get_dependencies() -> DependencyProvider:
    """
    FastAPI dependency provider
    
    Returns:
        DependencyProvider instance
    """
    container = get_container()
    return DependencyProvider(container)
