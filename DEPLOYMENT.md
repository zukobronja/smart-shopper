# SmartShopper - AWS Elastic Beanstalk Deployment Guide

## 🚀 Deployment Overview

SmartShopper is deployed as a **single Docker container** containing both the React frontend and FastAPI backend. This guide covers the complete deployment process to AWS Elastic Beanstalk.

## 📋 Prerequisites

1. **AWS CLI configured** with appropriate permissions
2. **EB CLI installed**: `pip install awsebcli`
3. **MongoDB Atlas** cluster set up with connection string
4. **API Keys** ready:
   - OpenAI API Key
   - Tavily API Key
   - Google OAuth credentials (optional)

## 🏗️ Deployment Package Structure

```
smartshopper/
├── Dockerfile                    # Multi-stage build (React + FastAPI)
├── Dockerrun.aws.json          # EB Docker configuration
├── .ebextensions/
│   └── 01_docker.config        # EB environment settings
├── backend/                     # Python FastAPI application
├── frontend/                    # React application
└── DEPLOYMENT.md               # This guide
```

## 🔧 Step 1: Initialize Elastic Beanstalk Application

```bash
# Initialize EB application (run once)
eb init smartshopper --platform "Docker" --region us-east-1

# Create environment
eb create smartshopper-prod --instance-type t3.small --single-instance
```

## 🔑 Step 2: Configure Environment Variables

Set these via AWS Console > Elastic Beanstalk > Environment > Configuration > Environment Properties:

### Required Variables
```
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/smartshopper
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
JWT_SECRET_KEY=your-secure-random-key-256-bits
```

### Optional (Google OAuth)
```
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://your-eb-url.elasticbeanstalk.com/auth/google/callback
```

### Pre-configured (via Dockerrun.aws.json)
```
EMBEDDINGS_PROVIDER=openai       # Use OpenAI embeddings (no PyTorch)
ENVIRONMENT=production           # Production mode
ENABLE_RSS_INGESTION=true       # Enable background RSS workers
PORT=8000                       # Container port
```

## 📦 Step 3: Deploy Application

```bash
# Deploy to Elastic Beanstalk
eb deploy

# Check deployment status
eb status

# View logs
eb logs
```

## 🔍 Step 4: Verify Deployment

1. **Health Check**: Visit `https://your-app.elasticbeanstalk.com/health`
2. **Frontend**: Visit `https://your-app.elasticbeanstalk.com/`
3. **API Docs**: Visit `https://your-app.elasticbeanstalk.com/docs`

## 📊 Container Specifications

- **Image Size**: 516MB (optimized, no PyTorch/NVIDIA dependencies)
- **Memory Usage**: ~512MB typical
- **CPU**: Single core sufficient
- **Instance**: t3.small recommended minimum

## 🛠️ Troubleshooting

### Common Issues

**1. Container Won't Start**
```bash
eb logs --all
# Check for missing environment variables or MongoDB connection issues
```

**2. Health Check Failures**
- Ensure MongoDB Atlas IP whitelist includes `0.0.0.0/0` or EB IPs
- Verify all required environment variables are set

**3. Frontend Not Loading**
- Check that static files are properly built in container
- Verify `PORT=8000` environment variable

**4. Search Not Working**
- Verify OpenAI and Tavily API keys
- Check API rate limits and billing

### Performance Monitoring

```bash
# View real-time logs
eb logs --all --follow

# Monitor container resources
eb health
```

## 🔒 Security Configuration

1. **Environment Variables**: Set sensitive keys via EB Console (not in code)
2. **MongoDB**: Use Atlas with IP restrictions and authentication
3. **HTTPS**: Enabled automatically via EB load balancer
4. **Container**: Runs as non-root user

## 💰 Cost Optimization

- **Instance Type**: Start with `t3.small` ($15-20/month)
- **Auto-scaling**: Single instance for demo, scale as needed
- **API Costs**: Monitor OpenAI and Tavily usage
- **MongoDB**: Atlas M0 free tier sufficient for development

## 🔄 Updates & Maintenance

```bash
# Deploy code changes
eb deploy

# Update environment configuration
eb config

# Scale instances
eb scale 2

# Terminate environment (when done)
eb terminate smartshopper-prod
```

## 📈 Production Readiness Checklist

- ✅ MongoDB Atlas connection configured
- ✅ All API keys set via environment variables
- ✅ Health check endpoint responding
- ✅ HTTPS/SSL certificate configured (automatic via EB)
- ✅ Container optimized (516MB, no GPU dependencies)
- ✅ Background RSS workers functional
- ✅ Error logging and monitoring configured
- ✅ Instance type appropriate for traffic

## 🆘 Support

If deployment fails:
1. Check `eb logs --all` for error details
2. Verify all environment variables in EB Console
3. Test container locally with `docker build` and `docker run`
4. Ensure MongoDB Atlas connectivity from AWS region

---

**Deployment Status**: Ready for production deployment
**Container Size**: 516MB (optimized)
**Features**: Complete SmartShopper with search, auth, favorites, and RSS