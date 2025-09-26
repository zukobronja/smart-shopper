# SmartShopper Docker Guide

Quick guide for containerized development and deployment of SmartShopper.

## Quick Start

### 1. Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your MongoDB Atlas URL and API keys
nano .env
```

### 2. Development Options

#### Option A: MongoDB Atlas (Recommended)
```bash
# Build and start with Atlas
docker-compose -f docker-compose.dev.yml up --build

# Visit: http://localhost:8000
```

#### Option B: With Local MongoDB
```bash
# Start with local MongoDB for offline development
docker-compose -f docker-compose.local.yml --profile local-mongo up --build

# Update .env to use: MONGODB_URL=mongodb://mongo-local:27017
```

#### Option C: Separate Frontend Development
```bash
# Start backend + separate frontend dev server
docker-compose -f docker-compose.local.yml --profile frontend-dev up --build

# Backend: http://localhost:8000
# Frontend: http://localhost:3000 (with hot reload)
```

## Build Commands

### Quick Deployment (Recommended)
```bash
# One-command deploy (rebuild + run + health check)
./scripts/docker-local.sh rebuild

# Just run (uses existing image)
./scripts/docker-local.sh run

# Full build with testing
./scripts/build-and-test.sh
```

### Manual Commands
```bash
# Production build
docker build -t smartshopper:latest .

# Development build (with hot reload)
docker-compose -f docker-compose.dev.yml up --build

# Production-like local test
docker-compose up --build
```

## File Structure

```
smartshopper/
├── Dockerfile                 # Multi-stage production build
├── docker-compose.yml         # Production-like deployment
├── docker-compose.dev.yml     # Development with Atlas
├── docker-compose.local.yml   # Local dev with optional MongoDB
├── .dockerignore              # Optimized build context
├── .env.example               # Environment template
└── .ebextensions/             # AWS Elastic Beanstalk config
```

## Deployment Scenarios

### Local Development
- **Atlas + Hot Reload**: `docker-compose.dev.yml`
- **Local MongoDB**: `docker-compose.local.yml --profile local-mongo`
- **Native Development**: Run backend/frontend separately

### Staging/Production
- **Single Container**: `docker-compose.yml`
- **AWS Elastic Beanstalk**: `Dockerfile` + `.ebextensions/`
- **Kubernetes**: Use production `Dockerfile`

## Pro Tips

### Development Workflow
```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up

# Rebuild only backend after dependency changes
docker-compose -f docker-compose.dev.yml build smartshopper-dev

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Stop and clean up
docker-compose -f docker-compose.dev.yml down -v
```

### Environment Variables Priority
1. `.env` file (local development)
2. AWS EB environment variables (production)
3. Default values in `config.py`

### MongoDB Options
- **Atlas (Recommended)**: Always available, vector search enabled, production-like
- **Local MongoDB**: Good for offline work, testing migrations
- **In-Memory**: For unit tests only

## Troubleshooting

### Critical: Embeddings Configuration
**For Docker deployment, use OpenAI embeddings to avoid permission issues:**
```bash
# In .env file
EMBEDDINGS_PROVIDER=openai  # Recommended for Docker
```

**Issue**: MiniLM embeddings cause permission errors in Docker:
```
ERROR: PermissionError at /home/appuser when downloading sentence-transformers/all-MiniLM-L6-v2
```
**Solution**: Use `EMBEDDINGS_PROVIDER=openai` which uses API calls instead of downloading models.

### Build Issues
```bash
# Clear Docker cache
docker system prune -f

# Rebuild from scratch
docker-compose build --no-cache

# Quick rebuild and deploy
./scripts/docker-local.sh rebuild
```

### MongoDB Connection
- Atlas: Check connection string format and IP whitelist
- Local: Ensure MongoDB container is running

### Port Conflicts
- Backend: Default 8000 (change with `PORT=8001`)
- Frontend Dev: Default 3000 (change in docker-compose)
- MongoDB: Default 27017 (change in docker-compose)

## Performance Notes

### Build Times
- **First Build**: 3-5 minutes (downloads dependencies)
- **Code Changes**: 10-30 seconds (layer caching)
- **Dependency Changes**: 1-2 minutes (partial rebuild)

### Resource Usage
- **Memory**: ~2-4GB runtime (includes PyTorch), ~4GB during build
- **Disk**: ~7.4GB final image (includes ML dependencies)
- **CPU**: Low during runtime, high during ML operations and search queries

### Optimization Tips
- Use `.dockerignore` (already configured)
- Multi-stage builds separate concerns
- Layer caching optimizes rebuild times
- Non-root user improves security

## Version Management

### Smart Semantic Versioning
SmartShopper uses Git-based semantic versioning instead of timestamp chaos:

```bash
# Check current version
./scripts/version.sh

# Create release tags
./scripts/tag-release.sh patch "Fix embedding permissions"
./scripts/tag-release.sh minor "Add new search features"
./scripts/tag-release.sh major "Breaking API changes"
```

### Version Examples
- **Tagged release**: `v1.2.3`
- **Development**: `v1.2.3-dev.5.a1b2c3d` (5 commits since v1.2.3)
- **Release candidate**: `v1.2.4-rc.2` (2 commits since last tag)
- **Local development**: `v0.0.0-dev.0.local-dirty`

### Benefits vs Timestamp Versioning
- **Semantic meaning**: Know what changed (patch/minor/major)
- **No junk images**: Clean version progression
- **Git integration**: Automatic versioning from repository state
- **Production ready**: Clear release vs development builds
