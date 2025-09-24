#!/bin/bash
# SmartShopper Build and Test Script
# Validates Docker build before deployment

set -e

APP_NAME="smartshopper"

# Source version utility
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/version.sh"
VERSION=$(get_version "dev")

echo "🔨 Building and testing SmartShopper Docker container"

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker"
    exit 1
fi

# Verify environment file
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "📝 Please edit .env with your configuration and run again"
    exit 1
fi

# Check if OpenAI embeddings are configured for Docker
if ! grep -q "EMBEDDINGS_PROVIDER=openai" .env; then
    echo "⚠️  For Docker deployment, OpenAI embeddings are recommended"
    echo "   Set EMBEDDINGS_PROVIDER=openai in .env to avoid permission issues"
    echo "   Continue anyway? (y/n)"
    read -r response
    if [[ ! $response =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Build Docker image
echo "🏗️  Building Docker image..."
docker build --no-cache -t $APP_NAME:$VERSION .
docker tag $APP_NAME:$VERSION $APP_NAME:latest

# Clean up any existing test containers
docker rm -f $APP_NAME-test 2>/dev/null || true

# Test container
echo "🧪 Testing container..."
CONTAINER_ID=$(docker run -d -p 8000:8000 --env-file .env --name $APP_NAME-test $APP_NAME:latest)

# Wait for startup
echo "⏳ Waiting for container to start..."
sleep 10

# Health checks
echo "🔍 Running health checks..."

# Check if container is running
if ! docker ps | grep -q $APP_NAME-test; then
    echo "❌ Container failed to start"
    docker logs $APP_NAME-test
    docker rm -f $APP_NAME-test
    exit 1
fi

# Check health endpoint
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Health endpoint responding"
else
    echo "❌ Health endpoint failed"
    docker logs $APP_NAME-test
    docker rm -f $APP_NAME-test
    exit 1
fi

# Check API endpoint
if curl -f http://localhost:8000/v1/health > /dev/null 2>&1; then
    echo "✅ API endpoint responding"
else
    echo "❌ API endpoint failed"
    docker logs $APP_NAME-test
    docker rm -f $APP_NAME-test
    exit 1
fi

# Check frontend serving
if curl -f http://localhost:8000/ | grep -q "SmartShopper" > /dev/null 2>&1; then
    echo "✅ Frontend serving correctly"
else
    echo "❌ Frontend not serving correctly"
    docker logs $APP_NAME-test
    docker rm -f $APP_NAME-test
    exit 1
fi

# Cleanup
docker stop $APP_NAME-test
docker rm $APP_NAME-test

echo "✅ All tests passed!"
echo "🐳 Image built: $APP_NAME:$VERSION"
echo "🐳 Tagged as: $APP_NAME:latest"
echo ""
echo "Next steps:"
echo "1. Deploy to EB: ./scripts/deploy.sh"
echo "2. Or run locally: docker run -p 8000:8000 --env-file .env $APP_NAME:latest"