#!/bin/bash
# SmartShopper EB Initialization Script
# Sets up AWS Elastic Beanstalk application

set -e

APP_NAME="smartshopper"
REGION=${1:-us-east-1}
PLATFORM="Docker"

echo "🚀 Initializing AWS Elastic Beanstalk for SmartShopper"
echo "Application: $APP_NAME"
echo "Region: $REGION"
echo "Platform: $PLATFORM"

# Check prerequisites
if ! command -v eb &> /dev/null; then
    echo "❌ EB CLI not found. Installing..."
    pip install awsebcli
fi

if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install AWS CLI"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS credentials not configured. Run: aws configure"
    exit 1
fi

# Initialize EB application
echo "📦 Initializing EB application..."
eb init $APP_NAME --platform "$PLATFORM" --region $REGION

# Create environment
echo "🌍 Creating EB environment..."
ENV_NAME="$APP_NAME-production"
eb create $ENV_NAME --instance-type t3.small --enable-spot

echo "✅ EB application initialized!"
echo ""
echo "Environment: $ENV_NAME"
echo "Platform: $PLATFORM"
echo "Region: $REGION"
echo ""
echo "Next steps:"
echo "1. Configure environment variables in AWS Console"
echo "2. Deploy: ./scripts/deploy.sh"
echo "3. Check status: eb status"
echo "4. Open app: eb open"