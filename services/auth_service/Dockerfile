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
    DOCKER_ENV=true

# -------------------------------------------------------------
# 📦 Install Dependencies
# -------------------------------------------------------------
RUN pip install --no-cache-dir -r /app/requirements.txt && \
    apt-get update && apt-get install -y curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# -------------------------------------------------------------
# 📁 Setup Data Directory with Proper Permissions
# -------------------------------------------------------------
RUN mkdir -p /app/data && \
    chmod 700 /app/data

# -------------------------------------------------------------
# 🚀 Run Auth Service with Modular Structure
# -------------------------------------------------------------
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8018"]
