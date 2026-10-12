# -----------------------------------------------------------------------------
# Stage 1 – dependency builder
#   Installs all Python wheels into /install so the final stage stays small.
#   Keeping build tools out of the runtime image reduces the attack surface.
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# Install build-time system libraries needed to compile some wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libsm6 \
        libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Upgrade pip / setuptools / wheel first
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 1. Pin numpy BEFORE everything else
# mediapipe, opencv, torch, and ultralytics all link against the numpy C-API.
# Installing numpy first guarantees every subsequent wheel compiles/links against
# the same ABI version, preventing "import numpy as np" failures at runtime.
RUN pip install --no-cache-dir "numpy>=1.26"

# 2. PyTorch CPU-only (large wheel — separate layer for Docker cache)
RUN pip install --no-cache-dir \
        torch torchvision \
        --index-url https://download.pytorch.org/whl/cpu

# 3. Remaining application requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2 – runtime image
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4 \
    TF_CPP_MIN_LOG_LEVEL=3 \
    GLOG_minloglevel=2 \
    YOLO_AUTOINSTALL=False

# Runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libsm6 \
        libxext6 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python environment from builder
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin

# Non-root user
RUN useradd --no-create-home --shell /bin/false appuser

WORKDIR /app

# Application source
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info"]
