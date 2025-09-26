# SmartShopper Production Deployment Guide

Complete guide for deploying SmartShopper to AWS Elastic Beanstalk.

## Prerequisites

### 1. Required Tools
```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Install EB CLI
pip install awsebcli

# Install Docker
# Follow: https://docs.docker.com/engine/install/
```

### 2. AWS Setup
```bash
# Configure AWS credentials
aws configure
# Enter: Access Key ID, Secret Access Key, Region (e.g., us-east-1), Output format (json)

# Verify credentials
aws sts get-caller-identity
```

### 3. Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit with production values
nano .env
```

**Required Environment Variables:**
```bash
# Database
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/
DATABASE_NAME=smartshopper

# API Keys
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...

# Security
JWT_SECRET_KEY=your-super-secure-production-key-min-32-chars

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://your-domain.com/auth/google/callback

# Production Settings
ENVIRONMENT=production
EMBEDDINGS_PROVIDER=openai
EMAIL_PROVIDER=console
```

## Build and Test

### 1. Local Build Test
```bash
# Build and test container locally
./scripts/build-and-test.sh
```

This script will:
- Build Docker image
- Run health checks
- Verify all endpoints
- Test frontend serving

### 2. Manual Test (Optional)
```bash
# Build image
docker build -t smartshopper:latest .

# Run container
docker run -p 8000:8000 --env-file .env smartshopper:latest

# Test endpoints
curl http://localhost:8000/health
curl http://localhost:8000/v1/health
curl http://localhost:8000/
```

## AWS Elastic Beanstalk Deployment

### 1. Initialize EB Application
```bash
# Quick setup (recommended)
./scripts/eb-init.sh us-east-1

# Or manual setup
eb init smartshopper --platform Docker --region us-east-1
eb create smartshopper-production --instance-type t3.small
```

### 2. Configure Environment Variables

#### Option A: AWS Console (Recommended)
1. Go to [AWS Elastic Beanstalk Console](https://console.aws.amazon.com/elasticbeanstalk/)
2. Select your application -> Environment
3. **Configuration** -> **Software** -> **Edit**
4. Add environment properties:

```
MONGODB_URL=mongodb+srv://...
DATABASE_NAME=smartshopper
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
JWT_SECRET_KEY=your-production-key
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://your-eb-domain.com/auth/google/callback
ENVIRONMENT=production
EMBEDDINGS_PROVIDER=openai
```

#### Option B: EB CLI
```bash
eb setenv MONGODB_URL="mongodb+srv://..." \
         DATABASE_NAME="smartshopper" \
         OPENAI_API_KEY="sk-..." \
         TAVILY_API_KEY="tvly-..." \
         JWT_SECRET_KEY="your-production-key" \
         GOOGLE_CLIENT_ID="your-client-id" \
         GOOGLE_CLIENT_SECRET="your-client-secret" \
         ENVIRONMENT="production"
```

### 3. Deploy Application
```bash
# Automated deployment
./scripts/deploy.sh

# Or manual deployment
eb deploy --label $(date +%Y%m%d-%H%M%S)
```

### 4. Verify Deployment
```bash
# Check application status
eb status

# View logs
eb logs

# Open application
eb open
```

## Production Configuration

### 1. Security Settings
The application includes production-ready security:
- Non-root container user
- JWT secure cookies
- CORS configuration
- Input validation
- Rate limiting (add as needed)

### 2. Performance Optimization
- **Instance Type**: t3.small (recommended minimum)
- **Auto Scaling**: 1-4 instances based on load
- **Health Checks**: 30-second intervals
- **Load Balancer**: Cross-zone enabled

### 3. Monitoring and Logging
```bash
# Enable enhanced health reporting
eb config

# Add to configuration:
aws:elasticbeanstalk:healthreporting:system:
  SystemType: enhanced

# Enable CloudWatch logs
aws:elasticbeanstalk:cloudwatch:logs:
  StreamLogs: true
  RetentionInDays: 7
```

## MongoDB Atlas Setup

### 1. Vector Search Indexes
Create required indexes for RSS vector search:

**Using MongoDB Compass:**
1. Connect to your Atlas cluster
2. Navigate to `smartshopper.rss_items` collection
3. Go to **Search Indexes** tab
4. Create two indexes:

**Index 1: `rss_summary_minilm_idx`**
```json
{
  "fields": [
    {
      "type": "vector",
      "path": "summary_vec_minilm_384",
      "numDimensions": 384,
      "similarity": "cosine"
    }
  ]
}
```

**Index 2: `rss_summary_openai_idx`**
```json
{
  "fields": [
    {
      "type": "vector",
      "path": "summary_vec_openai_1536",
      "numDimensions": 1536,
      "similarity": "cosine"
    }
  ]
}
```

### 2. Network Access
- Add EB environment IP ranges to Atlas IP whitelist
- Or use `0.0.0.0/0` for all IPs (less secure)

## CI/CD Pipeline (Optional)

### GitHub Actions Example
```yaml
# .github/workflows/deploy.yml
name: Deploy to AWS EB

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
          
      - name: Deploy to EB
        run: |
          pip install awsebcli
          eb deploy --label ${GITHUB_SHA:0:7}
```

## Troubleshooting

### Common Issues

#### 1. Container Health Check Failures
```bash
# Check application logs
eb logs

# Common fixes:
# - Verify MONGODB_URL format
# - Check API keys are valid
# - Ensure all environment variables are set
```

#### 2. Build Failures
```bash
# Test build locally first
./scripts/build-and-test.sh

# Check .dockerignore excludes unnecessary files
# Verify uv.lock exists and is valid
```

#### 3. MongoDB Connection Issues
```bash
# Test connection locally
python -c "import pymongo; print(pymongo.MongoClient('your-url').admin.command('ping'))"

# Check Atlas network access settings
# Verify connection string format
```

#### 4. Google OAuth Issues
```bash
# Verify redirect URI matches exactly
# Format: https://your-eb-domain.com/auth/google/callback
# Update in Google Cloud Console
```

### Useful Commands
```bash
# View environment details
eb status

# SSH into instance
eb ssh

# Restart application
eb deploy --staged

# Scale application
eb scale 2

# Terminate environment
eb terminate
```

## Monitoring

### Application Metrics
- Health endpoint: `/health`
- API health: `/v1/health`
- Workflow health: `/v1/health/workflow`

### CloudWatch Metrics
- Request count
- Response times
- Error rates
- Instance health

### Cost Monitoring
- Set up AWS billing alerts
- Monitor Tavily API usage
- Track OpenAI costs

## Security Checklist

- Environment variables in EB (not in code)
- JWT secure cookies with strong secret
- CORS properly configured
- Non-root container user
- MongoDB connection encrypted
- API keys properly secured
- Regular dependency updates

## Performance Targets

### Response Times
- Health endpoints: < 100ms
- Search API: < 30s (with Tavily)
- Frontend loads: < 3s

### Availability
- Uptime: 99.9%
- Auto-scaling: 1-4 instances
- Health check grace period: 5s

## Support

### Getting Help
- AWS EB Documentation: https://docs.aws.amazon.com/elasticbeanstalk/
- MongoDB Atlas Support: https://support.mongodb.com/
- Application logs: `eb logs`

### Emergency Procedures
```bash
# Quick rollback
eb deploy --version <previous-version>

# Emergency scale down
eb scale 1

# Check application health
curl https://your-domain.com/health
```

---

**Congratulations!** Your SmartShopper application is now running in production on AWS Elastic Beanstalk with MongoDB Atlas.