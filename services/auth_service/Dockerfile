# -------------------------------------------------------------
# 🐍 Base Python Image
# -------------------------------------------------------------
FROM python:3.12-slim

# -------------------------------------------------------------
# 📂 Working Directory
# -------------------------------------------------------------
WORKDIR /app

# -------------------------------------------------------------
# 🧩 Copy Only Required Files
# -------------------------------------------------------------
COPY ./services/auth_service /app
COPY ./core /app/core
COPY ./config /app/config
COPY .env /app/.env

# -------------------------------------------------------------
# 🧠 Environment
# -------------------------------------------------------------
ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_ENV=true \
    SERVICE_NAME=auth_service \
    LOG_DIR=/app/logs \
    JSON_LOGS=true

# -------------------------------------------------------------
# 📦 Install Dependencies
# -------------------------------------------------------------
RUN pip install --no-cache-dir -r /app/requirements.txt && \
    apt-get update && apt-get install -y curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# -------------------------------------------------------------
# 📁 Setup Data and Logs Directories with Proper Permissions
# -------------------------------------------------------------
RUN mkdir -p /app/data && \
    mkdir -p /app/logs && \
    chmod 700 /app/data && \
    chmod 755 /app/logs

# -------------------------------------------------------------
# 🚀 Run Auth Service with Modular Structure
# -------------------------------------------------------------
ENV FASTAPI_MODE=true \
    PORT=8018 \
    LOG_LEVEL=info

# Use the combined main.py file which supports both FastAPI and core application modes
CMD ["python", "main.py"]
