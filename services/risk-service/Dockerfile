# ==============================================
# ⚙️ RISK SERVICE (with TA-Lib)
# ==============================================
FROM python:3.10-slim

# Environment setup
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .

# Install build tools and Python packages. We skip TA-Lib C library here because it requires
# system-level ta-lib and extra headers; install that later in a specialized image if needed.
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
 && pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir "numpy<2.0" \
 && pip install --no-cache-dir -r requirements.txt \
 && apt-get purge -y gcc && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Copy source code
COPY ./core ./core
COPY ./services/risk-service ./services/risk-service
COPY ./config ./config

# Runtime
EXPOSE 8040
CMD ["python", "services/risk-service/main.py"]
