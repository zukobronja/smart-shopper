# Production-Optimized Multi-Stage Docker Build for AWS Elastic Beanstalk
# Eliminates PyTorch/NVIDIA dependencies by using OpenAI embeddings only

# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files first for better Docker layer caching
COPY frontend/package*.json ./

# Install dependencies (cached layer if package.json unchanged)
RUN npm ci --no-audit --no-fund

# Copy source code and build
COPY frontend/ ./
RUN npm run build

# Stage 2: Production Backend - Lightweight Python Runtime
FROM python:3.12-slim AS production

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    PORT=8000 \
    EMBEDDINGS_PROVIDER=openai \
    PYTHONHTTPSVERIFY=1 \
    SSL_CERT_DIR=/etc/ssl/certs \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Install essential system dependencies with enhanced SSL support
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    openssl \
    ca-certificates-java \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && update-ca-certificates \
    && c_rehash /etc/ssl/certs/

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# CACHE BUSTER - Force fresh build
ARG CACHEBUST=1

# Install production-only Python dependencies (NO PyTorch/NVIDIA packages)
# EXPLICITLY exclude torch, transformers, sentence-transformers
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    # Add explicit SSL support for Python
    "certifi>=2023.11.17" \
    "urllib3>=1.26.0" \
    # FastAPI Core
    "fastapi>=0.109.1" \
    "uvicorn[standard]>=0.27.0" \
    "pydantic>=2.11.7" \
    "pydantic-settings>=2.0.3" \
    # Database
    "motor>=3.3.2" \
    "pymongo>=4.6.1" \
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

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check for AWS ELB/ALB
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Production-optimized uvicorn command
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--loop", "uvloop", "--access-log", "--log-level", "info"]