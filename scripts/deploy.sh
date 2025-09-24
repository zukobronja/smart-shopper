#!/bin/bash
# SmartShopper Deployment Script
# Usage: ./scripts/deploy.sh [environment]

set -e

ENVIRONMENT=${1:-production}
APP_NAME="smartshopper"

# Source version utility
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/version.sh"
VERSION=$(get_version "auto")

echo "🚀 Deploying SmartShopper to AWS Elastic Beanstalk"
echo "Environment: $ENVIRONMENT"
echo "Version: $VERSION"

# Check prerequisites
if ! command -v eb &> /dev/null; then
    echo "❌ EB CLI not found. Please install: pip install awsebcli"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker"
    exit 1
fi

# Verify environment file
if [ ! -f .env ]; then
    echo "❌ .env file not found. Copy from .env.example and configure"
    exit 1
fi

# Build and test locally first
echo "🔨 Building Docker image locally..."
docker build -t $APP_NAME:$VERSION .

echo "🧪 Testing container locally..."
docker run --rm -d -p 8000:8000 --env-file .env --name $APP_NAME-test $APP_NAME:$VERSION

# Wait for container to start
sleep 5

# Health check
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Local container health check passed"
    docker stop $APP_NAME-test
else
    echo "❌ Local container health check failed"
    docker stop $APP_NAME-test
    exit 1
fi

# Deploy to EB
echo "📦 Deploying to Elastic Beanstalk..."

# Create application version
eb deploy --label $VERSION

echo "✅ Deployment complete!"
echo "🌐 Application URL: $(eb status | grep 'CNAME' | awk '{print $2}')"

# Optional: Open in browser
read -p "Open application in browser? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    eb open
fi