FROM python:3.13-slim

WORKDIR /app

# Install system dependencies (gcc for building, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and entrypoint
COPY src/ src/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV CREWAI_TELEMETRY_OPT_OUT=true

ENTRYPOINT ["./entrypoint.sh"]
