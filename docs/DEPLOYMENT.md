# SmartShopper Deployment Guide

Complete production-ready deployment guide for SmartShopper on AWS Elastic Beanstalk with MongoDB Atlas.

## Prerequisites

### 1. Required Tools
```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Install EB CLI
pip install awsebcli

# Verify Docker installation
docker --version
```

### 2. AWS Account Setup
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
```env
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

## Deployment Architecture

### Single Container Strategy
SmartShopper uses a **production-optimized single container** approach:

- **Frontend**: React app built into static assets
- **Backend**: FastAPI serving both API endpoints and static files
- **Container**: Multi-stage Docker build for optimal size and security
- **Platform**: AWS Elastic Beanstalk with Docker

### Infrastructure Components
- **Compute**: EC2 instances (t3.small recommended)
- **Database**: MongoDB Atlas with vector search
- **Load Balancer**: AWS Application Load Balancer
- **Monitoring**: CloudWatch logs and metrics
- **Auto Scaling**: 1-4 instances based on load

## Docker Configuration

### Multi-Stage Dockerfile
The production `Dockerfile` includes:

1. **Frontend Builder Stage**:
   - Node.js 20 Alpine
   - npm ci for reproducible builds
   - React production build

2. **Backend Runtime Stage**:
   - Python 3.12 slim
   - uv package manager for fast installs
   - Non-root user for security
   - Health checks for AWS ELB

### Build Optimization
- **Layer caching** for dependency changes
- **Security hardening** with non-root user
- **Health checks** for load balancer integration
- **Production commands** with uvloop for performance

```dockerfile
# Key optimizations from production Dockerfile
FROM python:3.12-slim AS backend-runner

# Security: non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Performance: uv package manager
RUN pip install --no-cache-dir uv

# Health check for AWS ELB
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Production command with uvloop
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --loop uvloop"]
```

## Quick Deploy (Automated)

### 1. Build and Test Locally
```bash
# Automated build and validation
./scripts/build-and-test.sh
```

This script performs:
- Docker image build
- Container health checks
- API endpoint validation
- Frontend serving verification

### 2. Initialize AWS EB (One-time)
```bash
# Quick EB setup with recommended settings
./scripts/eb-init.sh us-east-1
```

### 3. Deploy to Production
```bash
# Automated deployment with health checks
./scripts/deploy.sh
```

## Manual AWS Elastic Beanstalk Setup

### 1. Initialize EB Application
```bash
# Initialize with Docker platform
eb init smartshopper --platform Docker --region us-east-1

# Create production environment
eb create smartshopper-production --instance-type t3.small --enable-spot
```

### 2. Configure Environment Variables

#### Option A: AWS Console (Recommended)
1. Go to [AWS Elastic Beanstalk Console](https://console.aws.amazon.com/elasticbeanstalk/)
2. Select **smartshopper** -> **smartshopper-production**
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
         ENVIRONMENT="production"
```

### 3. Deploy Application
```bash
# Deploy with versioned label
eb deploy --label $(date +%Y%m%d-%H%M%S)

# Check deployment status
eb status

# View application logs
eb logs

# Open in browser
eb open
```

## MongoDB Atlas Configuration

### 1. Database Setup
- Create MongoDB Atlas cluster (M10+ recommended for production)
- Create database: `smartshopper`
- Configure network access for EB IP ranges

### 2. Vector Search Indexes (Required)
Create two Atlas Search vector indexes for RSS semantic search:

**Using MongoDB Compass:**
1. Connect to your Atlas cluster
2. Navigate to `smartshopper.rss_items` collection
3. Go to **Search Indexes** tab
4. Create indexes:

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

### 3. Network Security
```bash
# Option 1: Specific EB IP ranges (more secure)
# Get EB environment IPs and add to Atlas whitelist

# Option 2: All IPs (less secure, easier setup)
# Add 0.0.0.0/0 to Atlas IP access list
```

## Production Configuration

### AWS EB Extensions
The `.ebextensions/` directory contains production configurations:

**`01_python.config`** - Python/WSGI settings:
```yaml
option_settings:
  aws:elasticbeanstalk:application:environment:
    PYTHONPATH: "/app/backend"
    PYTHONUNBUFFERED: "1"
  aws:elb:healthcheck:
    HealthyThreshold: 3
    Target: "HTTP:80/health"
```

**`02_environment.config`** - Auto-scaling and monitoring:
```yaml
option_settings:
  aws:autoscaling:asg:
    MinSize: 1
    MaxSize: 4
  aws:elasticbeanstalk:healthreporting:system:
    SystemType: enhanced
  aws:elasticbeanstalk:cloudwatch:logs:
    StreamLogs: true
    RetentionInDays: 7
```

### Container Configuration
**`Dockerrun.aws.json`** - EB Docker deployment:
```json
{
  "AWSEBDockerrunVersion": "1",
  "Image": {
    "Name": "%IMAGE_URL%",
    "Update": "true"
  },
  "Ports": [{"ContainerPort": "8000"}]
}
```

## Security Configuration

### Application Security
- **JWT Secure Cookies**: HttpOnly, Secure flags enabled
- **CORS**: Properly configured for production domain
- **Input Validation**: Pydantic models throughout
- **Non-root Container**: Security hardened Docker image
- **Environment Variables**: Secrets managed through AWS EB

### Google OAuth Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create/select project
3. Enable Google+ API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URI: `https://your-eb-domain.com/auth/google/callback`

### Production Secrets Checklist
- Strong JWT secret (32+ characters)
- MongoDB Atlas user with minimal permissions
- Google OAuth credentials for production domain
- API keys (OpenAI, Tavily) with usage limits
- Environment variables (never in code)

## Monitoring and Health Checks

### Health Endpoints
```bash
# Application health
curl https://your-domain.com/health

# API health  
curl https://your-domain.com/v1/health

# Workflow health
curl https://your-domain.com/v1/health/workflow
```

### CloudWatch Integration
- **Logs**: Automatic log streaming to CloudWatch
- **Metrics**: Request count, response times, error rates
- **Alarms**: Set up alerts for high error rates or latency
- **Dashboards**: Monitor application performance

### Performance Targets
- **Health endpoints**: < 100ms response time
- **Search API**: < 30s (including Tavily processing)
- **Frontend load**: < 3s initial page load
- **Availability**: 99.9% uptime target

## Deployment Operations

### Routine Deployments
```bash
# Update application code
git commit -am "Update: feature description"

# Deploy to production
./scripts/deploy.sh

# Monitor deployment
eb status
eb logs --all
```

### Scaling Operations
```bash
# Scale up for high load
eb scale 4

# Scale down for cost optimization  
eb scale 1

# Check current scaling
eb status
```

### Rollback Procedures
```bash
# List recent deployments
eb history

# Rollback to previous version
eb deploy --version <version-label>

# Emergency rollback
eb abort
```

## Troubleshooting

### Common Deployment Issues

#### 1. Container Health Check Failures
```bash
# Symptom: EB environment shows "Severe" health
# Check logs
eb logs

# Common causes:
# - Missing environment variables
# - MongoDB connection issues
# - Invalid API keys
# - Port binding problems
```

#### 2. Build Failures
```bash
# Test build locally first
./scripts/build-and-test.sh

# Common issues:
# - Missing uv.lock file
# - Frontend build errors
# - Docker layer size limits
```

#### 3. Database Connection Issues
```bash
# Test MongoDB connection
python -c "import pymongo; print(pymongo.MongoClient('your-url').admin.command('ping'))"

# Check Atlas network access
# Verify connection string format
# Ensure database user permissions
```

#### 4. Google OAuth Failures
```bash
# Verify redirect URI exactly matches:
# https://your-eb-domain.com/auth/google/callback

# Check Google Cloud Console settings
# Ensure client ID/secret are correct
```

### Performance Issues
```bash
# Monitor resource usage
eb health

# Check application metrics
eb logs --all

# Scale if needed
eb scale 2
```

### Emergency Procedures
```bash
# Immediate rollback
eb deploy --version <previous-version>

# Emergency scale down
eb scale 1

# Check application health
curl https://your-domain.com/health
```

## Cost Optimization

### Resource Optimization
- **Instance Type**: Start with t3.small, scale as needed
- **Auto Scaling**: Configure based on actual usage patterns
- **Spot Instances**: Use for non-production environments
- **CloudWatch**: Monitor costs with billing alerts

### API Cost Management
- **Tavily Credits**: Monitor usage in Tavily dashboard
- **OpenAI Costs**: Set usage limits and alerts
- **MongoDB Atlas**: Choose appropriate tier (M10+ for production)

### Cost Monitoring
```bash
# Set up AWS billing alerts
aws budgets create-budget --budget file://budget.json

# Monitor API usage
# - Tavily dashboard
# - OpenAI usage page
# - MongoDB Atlas metrics
```

## Production Checklist

### Pre-Deployment
- Environment variables configured
- MongoDB Atlas vector indexes created
- Google OAuth production URLs set
- Local build and test passed
- AWS credentials configured

### Post-Deployment
- Health endpoints responding
- Search functionality working
- User authentication working
- CloudWatch logs flowing
- Performance metrics normal

### Ongoing Maintenance
- Monitor application logs
- Track API usage and costs
- Update dependencies regularly
- Review security settings
- Backup MongoDB data

## Support and Resources

### Documentation
- **AWS EB**: https://docs.aws.amazon.com/elasticbeanstalk/
- **MongoDB Atlas**: https://docs.atlas.mongodb.com/
- **Docker**: https://docs.docker.com/

### Getting Help
```bash
# Application logs
eb logs --all

# Environment details
eb status

# Health information
eb health

# SSH access (if needed)
eb ssh
```

### Community Resources
- AWS Elastic Beanstalk forums
- MongoDB community forums
- Docker community
- Stack Overflow

---

## Success!

Your SmartShopper application is now running in production with:

- **High Availability**: Auto-scaling load-balanced deployment
- **Security**: Hardened container with secure secret management
- **Monitoring**: CloudWatch integration with health checks
- **Performance**: Optimized Docker build and efficient runtime
- **Scalability**: Auto-scaling from 1-4 instances based on load

**Application URL**: Access via `eb open` or your custom domain

**Next Steps**: Set up monitoring alerts, configure custom domain, and establish regular backup procedures.