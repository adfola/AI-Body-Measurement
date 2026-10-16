# =========================
# Stage 1: Builder
# =========================
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Build dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Upgrade tooling
RUN pip install --no-cache-dir --upgrade \
    pip \
    setuptools \
    wheel

COPY requirements.txt .

# Install everything into a dedicated directory
RUN pip install \
    --no-cache-dir \
    --prefix=/install \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.org/simple \
    --retries=10 \
    --timeout=120 \
    -r requirements.txt

# =========================
# Stage 2: Runtime
# =========================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4 \
    TF_CPP_MIN_LOG_LEVEL=3 \
    GLOG_minloglevel=2 \
    YOLO_AUTOINSTALL=False

WORKDIR /app

# Runtime packages only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages
COPY --from=builder /install /usr/local

# Create non-root user
RUN useradd -r -s /usr/sbin/nologin appuser

# Copy project
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .

# Remove pycache files
RUN find /usr/local -type d -name "__pycache__" -exec rm -rf {} + || true

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s \
    --timeout=10s \
    --start-period=60s \
    --retries=3 \
    CMD curl -f "http://localhost:${PORT:-8000}/api/v1/health" || exit 1

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]