# Multi-stage Docker build optimized for AWS Elastic Beanstalk
# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files first for better Docker layer caching
COPY frontend/package.json frontend/package-lock.json ./

# Install dependencies including dev dependencies for build (cached layer if package.json unchanged)
RUN npm ci --no-audit --no-fund

# Copy source code and build
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend with Static Assets
FROM python:3.12-slim AS backend-runner

# Environment variables for Python optimization
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    PORT=8000

# Install system dependencies and security updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy dependency files for better caching
COPY pyproject.toml uv.lock ./

# Install Python dependencies (cached layer if requirements unchanged)
RUN uv pip install --system --no-cache .

# Copy backend source code
COPY backend ./backend

# Create static directory and copy frontend build
RUN mkdir -p backend/app/static
COPY --from=frontend-builder /app/frontend/dist/ ./backend/app/static/

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check for AWS ELB/ALB
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port (AWS EB will map this automatically)
EXPOSE ${PORT}

# Production-optimized uvicorn command
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --loop uvloop --access-log --log-level info"]