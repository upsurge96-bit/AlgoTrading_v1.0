# core/core/utils/metrics.py
import os
from prometheus_client import Counter, Histogram, CollectorRegistry

# Check if metrics are enabled via environment variable
METRICS_ENABLED = os.environ.get("ENABLE_METRICS", "true").lower() in ["true", "1", "yes", "y"]

# Create a registry for metrics (can be used for custom metrics by services)
metrics_registry = CollectorRegistry()

# Standard metrics
INGESTED = Counter("core_ingested_ticks_total", "Ticks ingested", ["service"], registry=metrics_registry)
INGEST_LATENCY = Histogram("core_ingest_latency_seconds", "Ingest latency", ["service"], registry=metrics_registry)

def observe_ingest(service_name, duration):
    INGESTED.labels(service=service_name).inc()
    INGEST_LATENCY.labels(service=service_name).observe(duration)

# Helper function to push metrics to Prometheus
def push_to_prometheus(registry=None, job=None, push_gateway=None):
    """
    Push metrics to Prometheus push gateway.
    
    Args:
        registry: Registry to push, defaults to metrics_registry
        job: Job name, defaults to service name from environment
        push_gateway: Push gateway URL, defaults from environment
    """
    # Skip if metrics are disabled
    if not METRICS_ENABLED:
        return True
        
    try:
        from prometheus_client import push_to_gateway
        
        registry = registry or metrics_registry
        job = job or os.environ.get("SERVICE_NAME", "unknown")
        gateway = push_gateway or os.environ.get("PROMETHEUS_PUSHGATEWAY", "localhost:9091")
        
        push_to_gateway(gateway, job=job, registry=registry)
        return True
    except Exception as e:
        # Don't break if metrics push fails
        print(f"Failed to push metrics: {e}")
        return False
