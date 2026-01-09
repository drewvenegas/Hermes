# Hermes API Dockerfile
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy application code first for proper install
COPY pyproject.toml README.md ./
COPY hermes/ ./hermes/

# Install Python dependencies
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir .

# Production image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY hermes/ ./hermes/
COPY migrations/ ./migrations/
COPY alembic.ini ./

# Create non-root user
RUN useradd -m -u 1000 hermes && chown -R hermes:hermes /app
USER hermes

# Expose ports
EXPOSE 8080 50051

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["uvicorn", "hermes.main:app", "--host", "0.0.0.0", "--port", "8080"]
