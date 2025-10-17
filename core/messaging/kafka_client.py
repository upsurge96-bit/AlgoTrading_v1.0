import os
import json
import time
from typing import Optional, Callable, Any, Dict
from core.utils.logger import get_logger

logger = get_logger("kafka_client")

class KafkaClient:
    """
    Modular Kafka client.

    Usage:
        kc = KafkaClient()                            # uses env KAFKA_BROKERS and default backend
        kc.send("topic", {"foo": "bar"}, key="123")  # non-blocking by default
        kc.flush()                                   # ensure delivery before exit
        kc.close()

    Behavior:
      - Default backend: confluent-kafka (if available).
      - Falls back to kafka-python if specified via client_type.
      - Non-blocking produce with optional immediate flush.
      - Delivery callbacks supported.
    """

    def __init__(
        self,
        brokers: Optional[str] = None,
        client_type: Optional[str] = None,  # "confluent" | "kafka-python"
        default_topic: Optional[str] = None,
        immediate_flush: bool = False,
    ):
        self.brokers = brokers or os.getenv("KAFKA_BROKERS", "kafka:9092")
        self.default_topic = default_topic
        self.immediate_flush = immediate_flush

        # detect desired client
        env_client = (os.getenv("KAFKA_CLIENT") or "").lower() or None
        self.client_type = client_type or env_client or "confluent"

        self._producer = None
        self._init_producer()

    def _init_producer(self):
        if self.client_type == "confluent":
            try:
                from confluent_kafka import Producer  # type: ignore
                conf = {"bootstrap.servers": self.brokers}
                # keep acks/defaults configurable via env if needed
                self._producer = Producer(conf)
                self.client_type = "confluent"
                logger.info("KafkaClient using confluent-kafka -> %s", self.brokers)
                return
            except Exception:
                logger.exception("confluent-kafka not available or failed to init; falling back if possible")

        if self.client_type in ("kafka-python", "kafka"):
            try:
                from kafka import KafkaProducer  # type: ignore
                self._producer = KafkaProducer(
                    bootstrap_servers=[s.strip() for s in self.brokers.split(",")],
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k is not None else None,
                )
                self.client_type = "kafka-python"
                logger.info("KafkaClient using kafka-python -> %s", self.brokers)
                return
            except Exception:
                logger.exception("kafka-python not available or failed to init")

        # if no producer initialized, log and keep None (best-effort disabled)
        if not self._producer:
            logger.warning("No Kafka producer available. Set KAFKA_CLIENT or install dependencies.")

    def _delivery_report(self, err: Optional[Exception], msg: Any, topic: str):
        if err is not None:
            logger.error("Kafka delivery failed for topic %s: %s", topic, err)
        else:
            # msg may be confluent message object or kafka-python FutureRecordMetadata
            try:
                if hasattr(msg, "topic"):
                    logger.debug("Kafka delivered to %s [partition=%s offset=%s]", msg.topic(), msg.partition(), msg.offset())
                else:
                    logger.debug("Kafka delivered: %s", msg)
            except Exception:
                logger.debug("Kafka delivered (unknown message object)")

    def send(
        self,
        topic: Optional[str],
        message: Dict,
        key: Optional[str] = None,
        async_send: bool = True,
        callback: Optional[Callable[[Optional[Exception], Any], None]] = None,
        immediate_flush: Optional[bool] = None,
    ) -> None:
        """
        Send a message to Kafka.

        - topic: target topic (falls back to default_topic)
        - message: serializable dict
        - key: optional partitioning key (string)
        - async_send: if False, blocks until flush
        - callback: optional (err, msg) callable invoked on delivery
        - immediate_flush: override instance immediate_flush for this send
        """
        if not topic:
            topic = self.default_topic
        if not topic:
            raise ValueError("topic must be provided or default_topic set")

        if not self._producer:
            logger.warning("Kafka producer not initialized; dropping message for topic %s", topic)
            return

        immediate = self.immediate_flush if immediate_flush is None else immediate_flush

        try:
            if self.client_type == "confluent":
                # confluent Producer.produce is non-blocking; callback on delivery
                def _cb(err, msg):
                    try:
                        if callback:
                            callback(err, msg)
                        else:
                            self._delivery_report(err, msg, topic)
                    except Exception:
                        logger.exception("Error in delivery callback")

                self._producer.produce(topic, key=key.encode("utf-8") if key else None, value=json.dumps(message).encode("utf-8"), callback=_cb)
                if immediate or not async_send:
                    self._producer.flush()
            elif self.client_type == "kafka-python":
                # kafka-python returns a Future
                future = self._producer.send(topic, value=message, key=(key.encode("utf-8") if key else None))
                if callback:
                    def _on_done(record_metadata):
                        callback(None, record_metadata)
                    def _on_err(exc):
                        callback(exc, None)
                    future.add_callback(_on_done)
                    future.add_errback(_on_err)
                if immediate or not async_send:
                    self._producer.flush()
            else:
                logger.warning("Unknown kafka client type '%s', message dropped", self.client_type)
        except Exception as e:
            logger.exception("Failed to send kafka message to %s: %s", topic, e)
            raise

    def flush(self, timeout: int = 10):
        """Block until all messages are delivered (or timeout)."""
        if not self._producer:
            return
        try:
            if self.client_type == "confluent":
                self._producer.flush(timeout=timeout)
            elif self.client_type == "kafka-python":
                self._producer.flush()
        except Exception:
            logger.exception("Error while flushing producer")

    def close(self, timeout: int = 10):
        """Flush and close producer."""
        try:
            self.flush(timeout=timeout)
        finally:
            # kafka-python has close()
            try:
                if self.client_type == "kafka-python" and hasattr(self._producer, "close"):
                    self._producer.close()
            except Exception:
                logger.exception("Error while closing kafka producer")

    # Context manager support
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
