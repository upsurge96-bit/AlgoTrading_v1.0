"""
Configuration Module for Data Service
Production-ready configuration management with validation
"""

from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings
from typing import List, Optional, Literal
from pathlib import Path
import os


class DatabaseConfig(BaseModel):
    """Database configuration"""
    host: str = Field(default="timescaledb", description="Database host")
    port: int = Field(default=5432, description="Database port")
    username: str = Field(default="trader", description="Database username")
    password: str = Field(default="traderpass", description="Database password")
    database: str = Field(default="trading", description="Database name")
    pool_size: int = Field(default=10, ge=1, le=100, description="Connection pool size")
    max_overflow: int = Field(default=20, ge=0, le=100, description="Max overflow connections")
    pool_timeout: int = Field(default=30, ge=1, le=300, description="Pool timeout in seconds")
    echo: bool = Field(default=False, description="Echo SQL statements")

    @property
    def connection_url(self) -> str:
        """Get database connection URL"""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class KafkaConfig(BaseModel):
    """Kafka configuration"""
    enabled: bool = Field(default=True, description="Enable Kafka")
    brokers: str = Field(default="kafka:9092", description="Kafka brokers")
    topic: str = Field(default="market_data", description="Kafka topic for market data")
    client_type: Literal["confluent", "kafka-python"] = Field(default="confluent", description="Kafka client type")
    compression: Literal["none", "gzip", "snappy", "lz4"] = Field(default="snappy", description="Compression type")
    batch_size: int = Field(default=100, ge=1, le=10000, description="Batch size for messages")
    linger_ms: int = Field(default=100, ge=0, le=5000, description="Linger time in milliseconds")


class MinIOConfig(BaseModel):
    """MinIO configuration"""
    enabled: bool = Field(default=True, description="Enable MinIO")
    endpoint: str = Field(default="minio:9000", description="MinIO endpoint")
    access_key: str = Field(default="minioadmin", description="MinIO access key")
    secret_key: str = Field(default="minioadmin", description="MinIO secret key")
    bucket: str = Field(default="market-data", description="MinIO bucket name")
    secure: bool = Field(default=False, description="Use HTTPS")
    compression: Literal["snappy", "gzip", "none"] = Field(default="snappy", description="Parquet compression")


class AuthServiceConfig(BaseModel):
    """Auth service configuration"""
    url: str = Field(default="http://auth_service:8018", description="Auth service URL")
    timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")
    cache_ttl: int = Field(default=300, ge=60, le=3600, description="Token cache TTL in seconds")
    retry_attempts: int = Field(default=3, ge=1, le=10, description="Retry attempts")
    retry_backoff: float = Field(default=0.5, ge=0.1, le=10.0, description="Retry backoff factor")


class WebSocketConfig(BaseModel):
    """WebSocket configuration"""
    url: str = Field(default="wss://ws.kite.trade", description="WebSocket URL")
    mode: Literal["ltp", "quote", "full"] = Field(default="full", description="Subscription mode")
    ping_interval: int = Field(default=20, ge=5, le=60, description="Ping interval in seconds")
    ping_timeout: int = Field(default=10, ge=5, le=60, description="Ping timeout in seconds")
    reconnect_delay: int = Field(default=5, ge=1, le=60, description="Reconnect delay in seconds")
    max_reconnect_attempts: int = Field(default=10, ge=1, le=100, description="Max reconnect attempts")
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=5.0, description="Backoff multiplier")


class WorkersConfig(BaseModel):
    """Workers configuration"""
    enabled: bool = Field(default=True, description="Enable background workers")
    live_streaming: bool = Field(default=True, description="Enable live data streaming")
    historical_fetch: bool = Field(default=False, description="Enable historical data fetch")
    scheduler: bool = Field(default=False, description="Enable scheduler")


class MonitoringConfig(BaseModel):
    """Monitoring configuration"""
    enabled: bool = Field(default=True, description="Enable monitoring")
    metrics_port: int = Field(default=9090, ge=1024, le=65535, description="Metrics port")
    health_check_interval: int = Field(default=30, ge=10, le=300, description="Health check interval")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Log level"
    )


class ServiceConfig(BaseModel):
    """Service configuration"""
    name: str = Field(default="data_service", description="Service name")
    version: str = Field(default="1.0.0", description="Service version")
    environment: Literal["development", "staging", "production"] = Field(
        default="development", description="Environment"
    )
    host: str = Field(default="0.0.0.0", description="Service host")
    port: int = Field(default=8080, ge=1024, le=65535, description="Service port")
    debug: bool = Field(default=False, description="Debug mode")
    workers: int = Field(default=1, ge=1, le=32, description="Number of workers")


class InstrumentConfig(BaseModel):
    """Instrument configuration"""
    tokens: List[int] = Field(
        default=[408065, 884737, 738561, 779521, 340481, 256265, 264969],
        description="List of instrument tokens"
    )
    
    @validator('tokens')
    def validate_tokens(cls, v):
        """Validate instrument tokens"""
        if not v:
            raise ValueError("At least one instrument token is required")
        if len(v) > 3000:
            raise ValueError("Maximum 3000 instruments allowed")
        return v


class Settings(BaseSettings):
    """
    Main application settings
    Loads from environment variables with DATA_SERVICE_ prefix
    """
    
    # Service config
    service: ServiceConfig = Field(default_factory=ServiceConfig)
    
    # Database config
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    
    # Kafka config
    kafka: KafkaConfig = Field(default_factory=KafkaConfig)
    
    # MinIO config
    minio: MinIOConfig = Field(default_factory=MinIOConfig)
    
    # Auth service config
    auth_service: AuthServiceConfig = Field(default_factory=AuthServiceConfig)
    
    # WebSocket config
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig)
    
    # Workers config
    workers: WorkersConfig = Field(default_factory=WorkersConfig)
    
    # Monitoring config
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    # Instrument config
    instruments: InstrumentConfig = Field(default_factory=InstrumentConfig)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = "DATA_SERVICE_"
        case_sensitive = False
        
    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment"""
        # Override with specific env vars if they exist
        overrides = {}
        
        # Database overrides
        if os.getenv("TIMESCALEDB_HOST"):
            overrides.setdefault("database", {})["host"] = os.getenv("TIMESCALEDB_HOST")
        if os.getenv("TIMESCALEDB_PORT"):
            overrides.setdefault("database", {})["port"] = int(os.getenv("TIMESCALEDB_PORT"))
        if os.getenv("TIMESCALEDB_USER"):
            overrides.setdefault("database", {})["username"] = os.getenv("TIMESCALEDB_USER")
        if os.getenv("TIMESCALEDB_PASSWORD"):
            overrides.setdefault("database", {})["password"] = os.getenv("TIMESCALEDB_PASSWORD")
        if os.getenv("TIMESCALEDB_DB"):
            overrides.setdefault("database", {})["database"] = os.getenv("TIMESCALEDB_DB")
            
        # Kafka overrides
        if os.getenv("KAFKA_BROKERS"):
            overrides.setdefault("kafka", {})["brokers"] = os.getenv("KAFKA_BROKERS")
        if os.getenv("ENABLE_KAFKA"):
            overrides.setdefault("kafka", {})["enabled"] = os.getenv("ENABLE_KAFKA").lower() == "true"
            
        # Workers overrides
        if os.getenv("ENABLE_WORKERS"):
            overrides.setdefault("workers", {})["enabled"] = os.getenv("ENABLE_WORKERS").lower() == "true"
        if os.getenv("ENABLE_LIVE_STREAMING"):
            overrides.setdefault("workers", {})["live_streaming"] = os.getenv("ENABLE_LIVE_STREAMING").lower() == "true"
        if os.getenv("ENABLE_HISTORICAL_FETCH"):
            overrides.setdefault("workers", {})["historical_fetch"] = os.getenv("ENABLE_HISTORICAL_FETCH").lower() == "true"
        if os.getenv("ENABLE_SCHEDULER"):
            overrides.setdefault("workers", {})["scheduler"] = os.getenv("ENABLE_SCHEDULER").lower() == "true"
            
        # Instrument tokens override
        if os.getenv("INSTRUMENT_TOKENS"):
            tokens_str = os.getenv("INSTRUMENT_TOKENS")
            tokens = [int(t.strip()) for t in tokens_str.split(",") if t.strip()]
            overrides.setdefault("instruments", {})["tokens"] = tokens
            
        # WebSocket mode override
        if os.getenv("WEBSOCKET_MODE"):
            overrides.setdefault("websocket", {})["mode"] = os.getenv("WEBSOCKET_MODE")
            
        # Environment override
        if os.getenv("ENVIRONMENT"):
            overrides.setdefault("service", {})["environment"] = os.getenv("ENVIRONMENT")
        
        return cls(**overrides)
    
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.service.environment == "production"
    
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.service.environment == "development"


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get application settings (singleton)"""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def reload_settings() -> Settings:
    """Reload settings (useful for testing)"""
    global _settings
    _settings = Settings.from_env()
    return _settings
