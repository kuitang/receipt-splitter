# Multi-stage Dockerfile for Receipt Splitter
# This example shows how to optimize builds and reduce image size

# ============================================
# Stage 1: Python dependencies builder
# ============================================
# Security-fixed native HEIF stack. Source URLs, hashes and upstream recipe are
# pinned in the builder; CPU dispatch stays portable across Fly amd64 hosts.
FROM python:3.15.0-slim-trixie AS heif-native
ARG SECURITY_REBUILD=local
RUN printf '%s\n' "$SECURITY_REBUILD" > /tmp/security-rebuild
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake pkg-config nasm ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV INSTALL_DIR_LIBS=/opt/heif \
    CMAKE_PREFIX_PATH=/opt/heif \
    PKG_CONFIG_PATH=/opt/heif/lib/pkgconfig \
    LD_LIBRARY_PATH=/opt/heif/lib \
    CFLAGS="-O2 -pipe" CXXFLAGS="-O2 -pipe"
COPY docker/build_native_heif.py /tmp/build_native_heif.py
RUN python /tmp/build_native_heif.py \
    && find /opt/heif/lib -name '*.a' -delete
COPY docker/record_native_build.py /tmp/record_native_build.py
RUN python /tmp/record_native_build.py

FROM python:3.15.0-slim-trixie as python-deps
ARG SECURITY_REBUILD=local
RUN printf '%s\n' "$SECURITY_REBUILD" > /tmp/security-rebuild

# Install build dependencies (only needed for compilation)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    pkg-config \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=heif-native /opt/heif /opt/heif
ENV LIBHEIF_ROOT=/opt/heif \
    PKG_CONFIG_PATH=/opt/heif/lib/pkgconfig \
    LD_LIBRARY_PATH=/opt/heif/lib

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies
COPY requirements.txt requirements-build.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements-build.txt \
    && pip install --no-cache-dir --no-build-isolation --no-binary=pillow-heif --require-hashes -r requirements.txt

# ============================================
# Stage 2: Static files builder
# ============================================
FROM python:3.15.0-slim-trixie as static-builder
ARG SECURITY_REBUILD=local
RUN printf '%s\n' "$SECURITY_REBUILD" > /tmp/security-rebuild

# Copy virtual environment from previous stage
COPY --from=python-deps /opt/venv /opt/venv
COPY --from=heif-native /opt/heif /opt/heif
ENV LD_LIBRARY_PATH=/opt/heif/lib
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies for Django
RUN apt-get update && apt-get install -y \
    libmagic1 libstdc++6 libgomp1 \
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
FROM python:3.15.0-slim-trixie
ARG SECURITY_REBUILD=local
RUN printf '%s\n' "$SECURITY_REBUILD" > /tmp/security-rebuild

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y \
    libmagic1 libstdc++6 libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser

WORKDIR /code

# Copy virtual environment from builder
COPY --from=python-deps /opt/venv /opt/venv
COPY --from=heif-native /opt/heif /opt/heif
ENV LD_LIBRARY_PATH=/opt/heif/lib

# Copy application code
COPY --chown=appuser:appuser . .

# Copy collected static files from static builder
COPY --from=static-builder --chown=appuser:appuser /build/staticfiles ./staticfiles

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Package installers are build-only; keep the production runtime free of their vendored libraries.
RUN /usr/local/bin/python -m pip uninstall -y pip setuptools wheel
RUN /opt/venv/bin/python -m pip uninstall -y pip wheel

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
