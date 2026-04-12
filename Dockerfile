FROM python:3.11-slim

WORKDIR /app

# Install system deps + ODA File Converter for DXF→DWG
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libgeos-dev curl xvfb && \
    rm -rf /var/lib/apt/lists/*

# ODA File Converter (free, required for DWG export)
# If download fails or install fails, DWG export is silently skipped at runtime.
# Update the URL when ODA releases a newer version.
RUN (curl -fsSL --connect-timeout 15 -o /tmp/oda.deb \
    "https://download.opendesign.com/guestfiles/Demo/ODAFileConverter_QT6_lnxX64_8.3dll_25.12.deb" \
    && dpkg -i /tmp/oda.deb \
    && rm -f /tmp/oda.deb \
    && echo "ODA File Converter installed") \
    || echo "WARN: ODA File Converter not available — DWG export will be disabled"

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
