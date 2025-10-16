# ==============================================
# 🩵 MONITORING SERVICE (lightweight, no TA-Lib)
# ==============================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    SERVICE_NAME=monitoring_service \
    LOG_DIR=/logs

WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade "pip<26" setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

COPY ./core ./core
COPY ./services/monitoring-service ./services/monitoring-service
COPY ./config ./config

VOLUME ["/logs"]
EXPOSE 8070

CMD ["python", "services/monitoring-service/main.py"]
