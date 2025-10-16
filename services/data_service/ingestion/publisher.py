from core.messaging.kafka_client import KafkaClient
from core.utils.config_loader import load_config
from core.utils.logger import get_logger
from tenacity import retry, stop_after_attempt, wait_exponential
import json
import time
import os

logger = get_logger("data_service.publisher")
CONFIG = load_config("/app/config/config.yaml")

_kafka = None

def get_kafka_client() -> KafkaClient:
    """Lazily initialize and reuse Kafka client."""
    global _kafka
    if _kafka is None:
        try:
            brokers = CONFIG.get("kafka", {}).get("brokers", ["kafka:9092"])
            logger.info("🔌 Initializing Kafka client | brokers=%s", brokers)
            _kafka = KafkaClient(brokers=brokers)
            logger.info("✅ Kafka client initialized successfully")
        except Exception as e:
            logger.exception("❌ Failed to initialize Kafka client: %s", e)
            raise
    return _kafka


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=30))
def _safe_send(kafka, topic, message):
    """Attempt to send a Kafka message with retry logic."""
    kafka.send(topic, message)


def publish_market_data(message: dict, topic: str = "market_data"):
    """Publish a market data payload to Kafka."""
    kafka = get_kafka_client()

    if not isinstance(message, dict):
        raise TypeError(f"Kafka message must be a dict, got {type(message)}")

    try:
        start_time = time.time()
        _safe_send(kafka, topic, message)
        elapsed = round(time.time() - start_time, 3)
        logger.info(
            "📤 Published to Kafka | topic=%s | symbol=%s | size=%d bytes | latency=%.3fs",
            topic,
            message.get("symbol"),
            len(json.dumps(message)),
            elapsed,
        )
    except Exception as e:
        logger.exception("⚠️ Kafka publish failed | topic=%s | symbol=%s | error=%s", topic, message.get("symbol"), e)
        _save_failed_message(message, topic)


def _save_failed_message(message: dict, topic: str):
    """Persist failed messages for replay."""
    failed_path = os.path.join("/logs", f"failed_kafka_{topic}.jsonl")
    try:
        with open(failed_path, "a") as f:
            f.write(json.dumps(message) + "\n")
        logger.warning("🧾 Saved failed message to %s", failed_path)
    except Exception as e:
        logger.error("💥 Failed to save failed Kafka message: %s", e)
