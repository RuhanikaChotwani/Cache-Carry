FROM python:3.11-slim

# Install system dependencies for OpenCV headless
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxrender1 libxext6 curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend requirements and install Python dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir onnxruntime>=1.16.0

# Copy backend code
COPY backend/ /app/

# Download ONNX models (gitignored, so must fetch during build)
RUN python download_models.py

# Create required data directories
RUN mkdir -p /app/data /app/data/evidence /app/data/snapshots \
    /app/runtime_uploads /app/models

# Expose port (Render sets PORT env var)
EXPOSE 8000

# Start command - Render sets PORT dynamically
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
