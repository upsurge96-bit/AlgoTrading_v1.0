# services/data-service/ingestion/subscriber.py

from confluent_kafka import Consumer, KafkaError, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic
from core.utils.config_loader import load_config
from core.utils.logger import get_logger
import json
import time
import threading
import signal
import sys
import ast
from json import JSONDecodeError

logger = get_logger("data_service.consumer")

# Load configuration
CONFIG = load_config("/app/config/config.yaml")

class KafkaSubscriber:
    def __init__(self, topic: str = "market_data", group_id: str = "data_service_group"):
        self.topic = topic
        self.running = True
        brokers = CONFIG.get("kafka", {}).get("brokers", "kafka:9092")

        self.conf = {
            "bootstrap.servers": brokers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }

        try:
            self.consumer = Consumer(self.conf)
            logger.info("✅ Kafka consumer initialized | topic=%s | group_id=%s", topic, group_id)
        except KafkaException as e:
            logger.exception("❌ Failed to initialize Kafka consumer: %s", e)
            raise

    def ensure_kafka_topic(topic_name, brokers="kafka:9092"):
        admin = AdminClient({"bootstrap.servers": brokers})
        topics = admin.list_topics(timeout=5).topics
        if topic_name not in topics:
            new_topic = NewTopic(topic_name, num_partitions=3, replication_factor=1)
            fs = admin.create_topics([new_topic])
            for t, f in fs.items():
                try:
                    f.result()
                    logger.info("✅ Created missing Kafka topic: %s", t)
                except Exception as e:
                    logger.warning("⚠️ Could not create topic %s: %s", t, e)


    def start(self):
        """Start consuming Kafka messages in a loop."""
        try:
            self.consumer.subscribe([self.topic])
            logger.info("📡 Subscribed to topic: %s", self.topic)

            while self.running:
                msg = self.consumer.poll(1.0)  # 1 second timeout
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        logger.error("⚠️ Kafka error: %s", msg.error())
                    continue

                try:
                    raw = msg.value()
                    text = raw.decode("utf-8", errors="replace")
                    try:
                        data = json.loads(text)
                    except JSONDecodeError as e:
                        # Log a compact preview of the payload to help debugging
                        preview = text[:300]
                        logger.warning("⚠️ JSON decode failed (%s). Raw preview: %s", e, preview)
                        # Try a safe python-literal parse as a fallback for single-quoted dicts
                        try:
                            data = ast.literal_eval(text)
                            logger.info("ℹ️ Fallback ast.literal_eval succeeded for message")
                        except Exception:
                            # Last-ditch attempt: try to coerce simple single-quote JSON to double-quotes
                            coerced = text.replace("'", '"')
                            try:
                                data = json.loads(coerced)
                                logger.info("ℹ️ Coerced single-quote JSON parsed successfully")
                            except Exception as final_exc:
                                # Give a helpful error message and skip this message
                                logger.error("❌ Failed to parse Kafka message after fallbacks. skipping. error=%s", final_exc)
                                logger.debug("Raw message bytes: %s", raw[:400])
                                continue

                    logger.info("📥 Received message | topic=%s | partition=%d | offset=%d | symbol=%s",
                                msg.topic(), msg.partition(), msg.offset(), data.get("symbol") if isinstance(data, dict) else None)
                    # 👉 TODO: process message (e.g., insert into TimescaleDB)
                except Exception as e:
                    logger.exception("❌ Failed to process message: %s", e)

        except KeyboardInterrupt:
            logger.warning("🛑 Kafka consumer interrupted by user.")
        except Exception as e:
            logger.exception("💥 Kafka consumer error: %s", e)
        finally:
            self.stop()

    def stop(self):
        """Gracefully stop the consumer."""
        try:
            self.running = False
            self.consumer.close()
            logger.info("✅ Kafka consumer stopped gracefully")
        except Exception as e:
            logger.error("⚠️ Failed to stop Kafka consumer: %s", e)

def start_consumer_in_background():
    """Start consumer in a daemon thread."""
    consumer = KafkaSubscriber()
    thread = threading.Thread(target=consumer.start, daemon=True)
    thread.start()
    logger.info("🧵 Kafka consumer running in background thread")
    return consumer

# Optional: standalone entry point
if __name__ == "__main__":
    consumer = KafkaSubscriber()
    try:
        consumer.start()
    except KeyboardInterrupt:
        consumer.stop()
