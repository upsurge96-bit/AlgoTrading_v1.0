# core/messaging/kafka_client.py
from confluent_kafka import Producer
import json
from core.utils.logger import get_logger

logger = get_logger("kafka_client")

class KafkaClient:
    """Simple wrapper around confluent_kafka.Producer"""

    def __init__(self, brokers="kafka:9092"):
        self.producer = Producer({'bootstrap.servers': brokers})
        logger.info(f"Connected to Kafka brokers: {brokers}")

    def send(self, topic: str, message: dict):
        try:
            self.producer.produce(topic, value=json.dumps(message).encode("utf-8"))
            self.producer.flush()
            logger.debug(f"📤 Published to Kafka topic '{topic}'")
        except Exception as e:
            logger.error(f"Failed to send Kafka message: {e}")
            raise
