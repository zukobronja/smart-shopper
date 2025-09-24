# SmartShopper - Claude Development Context

## Project Overview
SmartShopper is an AI-powered product search and comparison platform built for the **Tavily Engineering Assignment**. The system leverages Tavily as the primary search and extraction engine to find the best products, prices, and deals. Architecture combines Tavily APIs, LangGraph multi-agent pipeline, MongoDB Atlas with vector search, and React frontend.

**Current Status**: Backend architecture restart - cleaning up previous implementation chaos and building clean, professional MVP focused on Tavily integration excellence.

## Architecture
- **Backend**: FastAPI + LangGraph + MongoDB Atlas + Tavily integration
- **Frontend**: React + Vite + Tailwind + shadcn/ui + Recharts  
- **AI**: OpenAI GPT-4o-mini + dual embeddings (OpenAI/MiniLM)
- **Auth**: Google OAuth + email/password with JWT cookies
- **Deployment**: Single Docker container (demo) → Scalable services (production)

## Key Commands

### Backend Development
```bash
# Install from root (includes all dependencies)
uv pip install -e ".[dev]"
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development  
```bash
cd frontend
npm install
npm run dev  # starts on http://localhost:3000
```

### Single Container (Demo Deployment)
```bash
# Build both frontend and backend in Docker
docker build -t smartshopper-demo .
docker run -p 8000:8000 smartshopper-demo
```

### Testing
```bash
# Backend
cd backend
pytest

# Frontend
cd frontend  
npm run lint
npm run type-check
```

### Code Quality
```bash
# Backend
cd backend
ruff check . --fix
black .
mypy .

# Frontend
cd frontend
npm run lint:fix
```

## Important Files & Directories

### Core Documents (Single Sources of Truth)
- `docs/SMART_SHOPPER.md` - Complete system specification and implementation blueprint
- `docs/TAVILY_EXPLORATION.md` - Tavily integration schemas, coverage rules, validation
- `docs/MASTER_PROMPT.md` - Development guidelines and workflow

### Planning & Implementation documents
docs containes core docuemnts mentioned above, and also plan and other relevant projects documenst such as:
- `docs/TASKS.md` - plan of implementation. Always check this file and update it regularly after each implementation.
- `docs/TAVILY_IMPROVEMENT_PLAN.md` - comprehensive Tavily integration improvements based on best practices analysis
- `docs/README.md` - brief description of docs and soem basic information

### Important document - Architecture
- `docs/BACKEND_ARCHITECTURE.md` - Complete backend architecture specification with agent pipeline, data flow, and deployment strategies


### Backend Structure
```
backend/
├── app/
│   ├── main.py           # FastAPI app entry point
│   ├── config.py         # Settings (Pydantic)
│   ├── auth/            # Google OIDC + email/password
│   ├── api/             # REST endpoints (/v1/search, /v1/products, etc.)
│   ├── agents/          # LangGraph multi-agent pipeline
│   ├── db/              # MongoDB client, repositories, indexes
│   ├── extractors/      # Domain parsers + LLM extractors
│   ├── rss/             # RSS ingestion worker
│   ├── notify/          # Email/Discord sender
│   └── utils/           # Currency, units, dedupe, hashing
└── pyproject.toml       # Dependencies and tooling
```

### Frontend Structure
```
frontend/
├── src/
│   ├── components/      # React components
│   ├── pages/          # Route components
│   ├── services/       # API client
│   ├── hooks/          # Custom React hooks
│   ├── utils/          # Helper functions
│   └── types/          # TypeScript types
├── package.json
└── vite.config.ts
```

## Development Workflow

1. **Always explain what you're going to do next and request approval**
2. **Keep PR-sized chunks**: focused, testable, and easy to review
3. **Update TASKS.md** checklist after each milestone
4. **Write docs** in `/docs` for API contracts, schemas, deployment guides
5. **Follow Tavily best practices** from TAVILY_EXPLORATION.md

## Environment Variables

### Backend (.env)
```
ENVIRONMENT=development
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=smartshopper
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini  # or "gpt-4o", "gpt-3.5-turbo", etc.
TAVILY_API_KEY=tvly-...
JWT_SECRET_KEY=your-secret-key-change-in-production
EMBEDDINGS_PROVIDER=minilm  # or "openai"
EMAIL_PROVIDER=console      # or "ses", "sendgrid"
```

### Frontend (.env.local)
```
VITE_API_BASE_URL=http://localhost:8000
```

## Database Schema (MongoDB Atlas)

### Shared Collections (no user_id)
- `products` - Canonical products with dual embeddings
- `listings` - Individual offers/prices  
- `reviews` - Editorial reviews
- `price_history` - Time series data
- `rss_items` - RSS feed entries
- `sources` - Page audit trail + credibility
- `product_aliases` - Entity resolution helper

### Per-User Collections (access-limited by user_id)  
- `users` - Account data
- `runs` - Query history  
- `watches` - Saved alerts
- `alert_events` - Notification history

## Clean Architecture (Post-Restart)

**Previous Implementation Issues**:
- Mixed HTTP scraping + Tavily approaches causing conflicts
- Anti-bot protection making HTTP scraping unreliable 
- Chaotic state management and incomplete agent implementations
- Conflicting schemas and overlapping responsibilities

**New Clean Architecture (Tavily-First)**:
1. **Query Orchestrator** - Parse user query → intent + parameters
2. **Tavily Retriever** - Search → Extract → Coverage validation  
3. **Credibility Filter** - Domain scoring + recency + extractability
4. **Spec Extractor** - Structured data extraction using Phase 3 system
5. **Results Ranker** - Multi-criteria scoring and ranking
6. **MongoDB Persistence** - Store products, listings, reviews, traces
7. **RSS Worker** (Background) - Populate real-time deal data

## Tech Stack Details

### Backend Dependencies
- FastAPI, Pydantic, Motor (async MongoDB)
- LangChain, LangGraph, Tavily-Python
- OpenAI, sentence-transformers, torch
- JWT auth, Argon2id hashing
- Structured logging, email providers

### Frontend Dependencies  
- React 18, React Router, React Hook Form
- Radix UI, Tailwind, shadcn/ui components
- Recharts for data visualization
- Axios for API calls, Zod for validation

## Coding Standards

### Python
- Type hints everywhere
- Pydantic models for validation  
- Dependency injection for services
- Structured JSON logging
- 88 char line length (Black)

### TypeScript/React
- Functional components with hooks
- Clean API client separation
- Consistent error handling
- Accessible UI components

## Testing Strategy

### Backend
- Unit tests with pytest + pytest-asyncio
- Golden URL regression tests  
- Mock external API calls
- Test database operations

### Frontend
- Component testing
- API integration tests
- E2E user flows
- Accessibility testing

## Security Checklist
- JWT in HttpOnly Secure cookies
- CSRF tokens for mutations
- Rate limiting on auth/search
- Email verification flow
- Secrets in env vars only
- Input validation everywhere

## Performance Considerations
- Dual embedding vectors (OpenAI 1536-d + MiniLM 384-d)
- Atlas Vector Search indexes
- Request caching layers  
- Async/await everywhere
- Batch processing for embeddings
- Connection pooling

## Deployment Notes

### Demo Deployment (Single Container)
- **Container**: Frontend + Backend in single Docker image on AWS Elastic Beanstalk
- **Database**: MongoDB Atlas (vector search enabled)
- **Workers**: Background jobs run in same container
- **Secrets**: EB environment variables
- **Email**: SES or SendGrid

### Future Production Deployment
- **Frontend**: React → AWS Amplify or S3+CloudFront  
- **Backend**: Dedicated AWS Elastic Beanstalk service
- **Workers**: Separate EB environment for RSS ingest + alert evaluator

## Quick References

### Tavily Integration
- Prefer `extract` over `crawl` (cheaper, more structured)
- Coverage threshold: 0.60 minimum
- Credibility scoring: domain rep + recency + extractability
- Cache results by URL hash
- Short-circuit at ≥4 ecom + ≥2 reviews

### MongoDB Patterns
```python
# Dual vector search
await products.aggregate([
    {"$vectorSearch": {
        "index": "title_vec_openai_1536" if settings.EMBEDDINGS_PROVIDER == "openai" else "title_vec_minilm_384",
        "path": "title_vec_openai_1536" if settings.EMBEDDINGS_PROVIDER == "openai" else "title_vec_minilm_384", 
        "queryVector": query_embedding,
        "numCandidates": 100,
        "limit": 20
    }}
])
```

### Error Handling Patterns
```python
# Backend
from app.utils.exceptions import SmartShopperException
raise SmartShopperException("Tavily extraction failed", details={...})

# Frontend  
try {
  const result = await api.search(query)
} catch (error) {
  toast.error(error.message)
}
```
ACTION: ALways on start, or on restart check files in docs, check curretn implementation to get context.
IMPORTANT: Act as top professinal. You are Princila Solution Architect/Engineer/Developer, you are also great fron-end Designer and developer, capable to deisgn and develop cutting edge and modern applciations. DO NOT BE YES-MAN! Propose the best solutions.
Remember: **Explain → Propose → Ask approval** for every step! Implement testabel chiunhs that I can follow implemntaiton.
Coding: Do not add flashy icons in code such as ❌, or similar.