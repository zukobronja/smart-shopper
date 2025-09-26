# Production-Optimized Multi-Stage Docker Build for AWS Elastic Beanstalk
# Eliminates PyTorch/NVIDIA dependencies by using OpenAI embeddings only

# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files first for better Docker layer caching
COPY frontend/package*.json ./

# Install dependencies (cached layer if package.json unchanged)
RUN npm ci --no-audit --no-fund

# Copy source code
COPY frontend/ ./

# Build frontend with placeholder - will be replaced at runtime
ENV VITE_API_BASE_URL=__VITE_API_BASE_URL_PLACEHOLDER__
RUN echo "Building frontend with VITE_API_BASE_URL=${VITE_API_BASE_URL}" && npm run build

# Stage 2: Production Backend - Lightweight Python Runtime
FROM python:3.12-slim AS production

# Environment variables (simplified like working demo)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    PORT=8000 \
    EMBEDDINGS_PROVIDER=openai \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# Install essential system dependencies (simplified SSL approach like working demo)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Remove complex OpenSSL configuration - use system defaults

WORKDIR /app

# CACHE BUSTER - Force fresh build with timestamp
ARG CACHEBUST=20250924_2130

# Install production-only Python dependencies (NO PyTorch/NVIDIA packages)
# EXPLICITLY exclude torch, transformers, sentence-transformers
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    # SSL support for Python and MongoDB (simplified like working demo)
    "certifi>=2024.0.0" \
    "dnspython>=2.6.1" \
    # FastAPI Core
    "fastapi>=0.109.1" \
    "uvicorn[standard]>=0.27.0" \
    "pydantic>=2.11.7" \
    "pydantic-settings>=2.0.3" \
    # Database with explicit version for SSL compatibility
    "motor>=3.3.2" \
    "pymongo[srv]>=4.6.1" \
    "dnspython>=2.4.0" \
    # Authentication
    "python-jose[cryptography]>=3.3.0" \
    "passlib[argon2,bcrypt]>=1.7.4" \
    "argon2-cffi>=23.1.0" \
    "python-multipart>=0.0.6" \
    # Google OAuth
    "google-auth>=2.27.0" \
    "google-auth-oauthlib>=1.2.0" \
    # AI/ML APIs (NO LOCAL MODELS)
    "openai>=1.12.0" \
    "tavily-python>=0.7.6" \
    # LangChain/LangGraph (minimal versions to avoid torch deps)
    "langchain-core>=0.3.65" \
    "langchain-openai>=0.3.23" \
    "langchain-tavily>=0.2.6" \
    "langchain>=0.3.25" \
    "langgraph>=0.4.8" \
    # Web/HTTP
    "requests>=2.32.3" \
    "httpx>=0.26.0" \
    "aiohttp>=3.9.0" \
    # Data Processing (minimal numpy only)
    "pandas>=2.1.0" \
    "python-dateutil>=2.8.2" \
    "numpy>=1.24.0" \
    # RSS/Feeds
    "feedparser>=6.0.10" \
    "beautifulsoup4>=4.12.0" \
    "lxml>=5.0.0" \
    # Utilities
    "python-dotenv>=1.1.0" \
    "structlog>=23.2.0" \
    "emails>=0.6.0" \
    "jsonschema>=4.20.0" \
    "babel>=2.14.0"

# Copy backend source code
COPY backend ./backend

# Create static directory and copy frontend build
RUN mkdir -p backend/app/static
COPY --from=frontend-builder /app/frontend/dist/ ./backend/app/static/

# Create startup script for environment variable substitution
RUN echo '#!/bin/bash' > /app/startup.sh && \
    echo '# Replace placeholder with actual environment variable in built frontend files' >> /app/startup.sh && \
    echo 'if [ ! -z "$VITE_API_BASE_URL" ]; then' >> /app/startup.sh && \
    echo '    echo "Configuring frontend with VITE_API_BASE_URL: $VITE_API_BASE_URL"' >> /app/startup.sh && \
    echo '    find /app/backend/app/static -type f -name "*.js" -exec sed -i "s|__VITE_API_BASE_URL_PLACEHOLDER__|$VITE_API_BASE_URL|g" {} \;' >> /app/startup.sh && \
    echo '    find /app/backend/app/static -type f -name "*.html" -exec sed -i "s|__VITE_API_BASE_URL_PLACEHOLDER__|$VITE_API_BASE_URL|g" {} \;' >> /app/startup.sh && \
    echo 'fi' >> /app/startup.sh && \
    echo '# Start the application' >> /app/startup.sh && \
    echo 'exec "$@"' >> /app/startup.sh && \
    chmod +x /app/startup.sh

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check for AWS ELB/ALB
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Production-optimized uvicorn command with startup script
ENTRYPOINT ["/app/startup.sh"]
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--loop", "uvloop", "--access-log", "--log-level", "info"]
