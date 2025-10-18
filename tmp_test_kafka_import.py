import sys
sys.path.append(r'D:\PROJECTS\AlgoTrading_v1')
from core.messaging.kafka_client import KafkaProducer
print('KafkaProducer imported:', KafkaProducer)
inst = KafkaProducer()
print('KafkaProducer instance created:', type(inst))