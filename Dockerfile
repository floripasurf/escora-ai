FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libgeos-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy everything first (needed for pip install . with setuptools)
COPY . .

# Install Python deps
RUN pip install --no-cache-dir .

# Create data dirs (will be overlaid by the Fly volume at /data)
RUN mkdir -p /data/uploads /data/output /data/learning

# Runtime data dir — overridden by Fly env but set here for local docker runs
ENV ESCORA_DATA_DIR=/data

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
