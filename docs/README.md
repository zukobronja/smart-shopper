# SmartShopper Documentation

## Core Documentation

### Project Specifications
- **[SMART_SHOPPER.md](SMART_SHOPPER.md)** - Complete system specification and implementation blueprint
- **[TAVILY_EXPLORATION.md](TAVILY_EXPLORATION.md)** - Tavily integration schemas, coverage rules, validation
- **[MASTER_PROMPT.md](MASTER_PROMPT.md)** - Development guidelines and workflow

### Implementation Tracking  
- **[TASKS.md](TASKS.md)** - Phase-by-phase implementation plan and progress tracking
- **[BUG_TRACKER.md](BUG_TRACKER.md)** - Bug discovery, tracking, and resolution status
- **[API.md](API.md)** - API endpoints, authentication, and response schemas
- **[SCHEMAS.md](SCHEMAS.md)** - Database models and data structures

### System Components

#### Phase 3: Extraction System COMPLETED
- **[EXTRACTION_SYSTEM.md](EXTRACTION_SYSTEM.md)** - **⭐ Comprehensive extraction system documentation**
  - Hybrid extraction architecture (Tavily + LLM)
  - Category-agnostic schemas supporting unlimited product types
  - 4-component credibility scoring system
  - Golden URL testing framework
  - Integration examples and usage patterns

#### Phase 4.1: Tavily Integration Improvements IN PROGRESS
- **[TAVILY_IMPROVEMENT_PLAN.md](TAVILY_IMPROVEMENT_PLAN.md)** - **Comprehensive Tavily optimization plan**
  - Critical bug fixes and parameter optimization
  - Map API integration for comprehensive site discovery
  - Intelligent URL filtering and cost optimization
  - Three-step architecture (Discovery -> Filter -> Extract)
  - 40-60% cost reduction with quality improvements

#### Phase 4.2: LangGraph Pipeline NEXT
- Coming soon: LangGraph multi-agent pipeline documentation

### Deployment & Operations
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Docker configuration and AWS deployment setup

## Quick Start Guide

### 1. Development Setup
```bash
# Backend
uv pip install -e ".[dev]" 
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend  
cd frontend && npm install && npm run dev
```

### 2. Testing
```bash
# Backend tests (21 tests covering extraction system)
cd backend && pytest

# Frontend tests
cd frontend && npm run lint && npm run type-check
```

### 3. Extraction System Usage
```python
from app.extractors.hybrid_extractor import HybridExtractor

extractor = HybridExtractor(tavily_api_key="...", openai_api_key="...")
results = extractor.extract_and_rank_by_credibility([
    "https://www.amazon.com/laptop",
    "https://www.bestbuy.com/laptop"
], schema_type="ecom_v1")
```

### 4. Interactive Testing (Jupyter Notebooks)
```bash
# Start Jupyter from backend directory
cd backend && jupyter lab

# Open comprehensive testing notebook
# notebooks/simple_tavily_test.ipynb
```

### 5. Seed Initial RSS Feeds
```bash
# From repo root (uses .env Mongo credentials)
python scripts/seed_rss_feeds.py
```
This registers curated feeds (TechCrunch, Slickdeals, HotUKDeals, etc.) so the RSS ingestion worker has data to ingest before vector retrieval tests.

## System Architecture Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Phase 1   │───▶│   Phase 2   │───▶│   Phase 3   │───▶│   Phase 4   │
│ Foundation  │    │ Auth & API  │    │ Frontend UI │    │ Production  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                       NEXT

┌─────────────────────────────────────────────────────────────────────────────┐
│                    Current Full-Stack System (Phases 1-3)                  │
│                                                                             │
│  React Frontend + FastAPI Backend + MongoDB Atlas + LangGraph Pipeline     │
│  ├── Frontend: Glass morphism UI with SmartShopper branding               │
│  ├── Backend: 5-agent LangGraph pipeline with /v1/search API              │
│  ├── Database: MongoDB Atlas with search persistence & user management     │
│  └── Pipeline: Tavily -> Credibility -> Extraction -> Ranking -> Results      │
│      ├── QueryOrchestrator (intent detection & parameter extraction)       │
│      ├── TavilyRetriever (live web search & content extraction)           │
│      ├── CredibilityFilter (domain scoring & quality assessment)          │
│      ├── SpecExtractor (structured data extraction & normalization)       │
│      └── ResultsRanker (multi-criteria scoring & explanations)            │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Progress Summary

### Completed (Phases 1-3)
- **Foundation**: Repository scaffold, dependencies, configuration
- **Backend Pipeline**: 5-agent LangGraph system with Tavily integration
- **Authentication**: JWT system, user management, MongoDB connection  
- **Database Integration**: MongoDB Atlas with search persistence and vector indexes
- **Frontend UI**: Professional glass morphism design with SmartShopper branding
- **Testing**: 21 comprehensive tests covering all backend components
- **Documentation**: Complete system documentation and usage guides

### Tavily Client Architecture
- **`tavily_client.py`**: Async client for LangGraph pipeline (Tavily best practices)
  - Intent-based optimization and domain quality filtering
  - LangChain integration with rate limiting and best practices
  - Cost optimization through intelligent parameter selection
  - Used by all agents in the 5-agent architecture

### Next Steps (Phase 4)
- **LangGraph Pipeline**: Multi-agent orchestration system
- **Nodes**: Orchestrator, Source Planner, Retrievers, Credibility Filter, Spec Extractor
- **Integration**: Connect pipeline to `/v1/search` endpoint
- **Performance**: Parallel processing, caching, cost optimization

### Key Achievements
- **Category-Agnostic Design**: Works with unlimited product types (electronics, kitchen, furniture, books, tools, etc.)
- **Intelligent Fallback**: Tavily-first with LLM backup (60% coverage threshold)
- **Quality Scoring**: Multi-dimensional credibility assessment (domain, recency, extractability, content)
- **Test Coverage**: 100% test pass rate with real-world golden URLs
- **Cost Optimization**: Smart API usage minimizing costs while maximizing quality

## Quick Links

- **Live API**: http://localhost:8000 (development)
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **Health Check**: http://localhost:8000/v1/health
- **Frontend**: http://localhost:3000 (development)

## Development Workflow

1. **Plan** -> Review specifications and break down tasks
2. **Build** -> Implement features with comprehensive testing
3. **Test** -> Validate functionality and integration
4. **Document** -> Update documentation and examples
5. **Approval** -> Review and approve before moving to next phase

**All phases follow this structured approach for consistent, high-quality development.**
