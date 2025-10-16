# ==============================================
# 🧠 DATA SERVICE (Full-featured Ingestion Engine)
# ==============================================
FROM python:3.12-slim

# -----------------------------------------------------------------
# Global environment setup
# -----------------------------------------------------------------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    SERVICE_NAME=data_service \
    LOG_DIR=/logs

WORKDIR /app

# -----------------------------------------------------------------
# Install system dependencies (for Pandas, Numpy, Scipy, PostgreSQL, etc.)
# -----------------------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        gcc \
        g++ \
        curl \
        wget \
        git && \
    rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------
# Install Python dependencies
# -----------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade "pip<26" setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------
# Copy service-specific code
# -----------------------------------------------------------------
COPY ./core ./core
COPY ./services/data_service ./services/data_service
COPY ./config ./config

# -----------------------------------------------------------------
# Volumes + Ports
# -----------------------------------------------------------------
VOLUME ["/logs"]
EXPOSE 8080

# -----------------------------------------------------------------
# Run the FastAPI app via Uvicorn
# -----------------------------------------------------------------
CMD ["uvicorn", "services.data_service.main:app", "--host", "0.0.0.0", "--port", "8080"]
