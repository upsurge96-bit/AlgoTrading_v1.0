# core/core/utils/metrics.py
from prometheus_client import Counter, Histogram

INGESTED = Counter("core_ingested_ticks_total", "Ticks ingested", ["service"])
INGEST_LATENCY = Histogram("core_ingest_latency_seconds", "Ingest latency", ["service"])

def observe_ingest(service_name, duration):
    INGESTED.labels(service=service_name).inc()
    INGEST_LATENCY.labels(service=service_name).observe(duration)
