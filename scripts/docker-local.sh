#!/bin/bash
# Quick Docker Local Deployment Script
# For fast local development and testing

set -e

APP_NAME="smartshopper"
CONTAINER_NAME="${APP_NAME}-app"

# For local development, we just use 'latest' to keep things simple
TAG="latest"

echo "🐳 SmartShopper Local Docker Deployment"

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker"
    exit 1
fi

# Verify environment file
if [ ! -f .env ]; then
    echo "❌ .env file not found. Copy from .env.example and configure"
    exit 1
fi

# Function to clean up
cleanup() {
    echo "🧹 Cleaning up existing containers..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
    docker rm $CONTAINER_NAME 2>/dev/null || true
}

# Function to build
build() {
    echo "🔨 Building Docker image..."
    docker build -t $APP_NAME:$TAG .
}

# Function to run
run() {
    echo "🚀 Starting container..."
    docker run -d \
        --name $CONTAINER_NAME \
        -p 8000:8000 \
        --env-file .env \
        $APP_NAME:$TAG
    
    echo "⏳ Waiting for startup..."
    sleep 5
    
    # Health check
    echo "🔍 Checking health..."
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ SmartShopper is running!"
        echo "🌐 Frontend: http://localhost:8000"
        echo "🔧 API: http://localhost:8000/docs"
        echo ""
        echo "Commands:"
        echo "  View logs: docker logs -f $CONTAINER_NAME"
        echo "  Stop: docker stop $CONTAINER_NAME"
        echo "  Remove: docker rm $CONTAINER_NAME"
    else
        echo "❌ Health check failed"
        echo "📋 Container logs:"
        docker logs $CONTAINER_NAME
        exit 1
    fi
}

# Handle command line options
case "${1:-run}" in
    "build")
        cleanup
        build
        ;;
    "run")
        cleanup
        run
        ;;
    "rebuild")
        cleanup
        build
        run
        ;;
    "stop")
        cleanup
        echo "🛑 Container stopped"
        ;;
    "logs")
        docker logs -f $CONTAINER_NAME
        ;;
    "shell")
        docker exec -it $CONTAINER_NAME /bin/bash
        ;;
    *)
        echo "Usage: $0 [build|run|rebuild|stop|logs|shell]"
        echo ""
        echo "Commands:"
        echo "  build   - Build Docker image only"
        echo "  run     - Run container (default)"
        echo "  rebuild - Build and run"
        echo "  stop    - Stop and remove container"
        echo "  logs    - View container logs"
        echo "  shell   - Open shell in container"
        exit 1
        ;;
esac