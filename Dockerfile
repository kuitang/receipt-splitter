# Multi-stage Dockerfile for Receipt Splitter
# This example shows how to optimize builds and reduce image size

# ============================================
# Stage 1: Python dependencies builder
# ============================================
FROM python:3.13-slim-trixie as python-deps

# Install build dependencies (only needed for compilation)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    pkg-config \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# ============================================
# Stage 2: Static files builder
# ============================================
FROM python:3.13-slim-trixie as static-builder

# Copy virtual environment from previous stage
COPY --from=python-deps /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies for Django
RUN apt-get update && apt-get install -y \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy application code
COPY . .

# Collect static files
ENV SECRET_KEY="doesnt matter"
RUN python manage.py collectstatic --noinput

# ============================================
# Stage 3: Final production image
# ============================================
FROM python:3.13-slim-trixie

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser

WORKDIR /code

# Copy virtual environment from builder
COPY --from=python-deps /opt/venv /opt/venv

# Copy application code
COPY --chown=appuser:appuser . .

# Copy collected static files from static builder
COPY --from=static-builder --chown=appuser:appuser /build/staticfiles ./staticfiles

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Expose port
EXPOSE 8000

# Run gunicorn with optimal production settings
CMD ["gunicorn", "receipt_splitter.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--worker-class", "gthread", \
     "--threads", "4", \
     "--worker-tmp-dir", "/dev/shm", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--preload", \
     "--timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]