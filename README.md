<div align="center">
  <img src="images/smart-shopper-logo.png" alt="SmartShopper Logo" width="200"/>
</div>

# SmartShopper

**AI-Powered Product Search and Comparison Platform**

SmartShopper is a production-ready, full-stack application that leverages advanced AI and web intelligence to help users find the best products, prices, and deals across trusted sources. Built with Tavily API integration, LangGraph multi-agent pipeline, and modern React frontend with glass morphism design.

![SmartShopper Home](images/smartshoper-home.png)


## Overview

SmartShopper helps users find the **best products, prices, and deals** by combining a hybrid web retrieval strategy (trusted sites + Tavily), LLM-powered extraction/synthesis (OpenAI GPT-4o-mini), MongoDB Atlas (with Vector Search), an RSS deals pipeline, and real-time notifications. The system prioritizes Tavily's search and extraction capabilities over traditional web scraping, implementing best practices for cost efficiency, reliability, and performance.

**Core Value:** Search for a category (e.g., *"best laptops under €1,000 for programming"*) -> get a **ranked, explainable shortlist** with specs, prices, value assessment, sources, and optional alerts on price drops.

**Primary Users:** Consumers who want **reliable, current, cross-site comparisons and deal alerts**.

## High-Level Architecture

```
Frontend (React + Tailwind + shadcn/ui + Recharts)
        │
        ▼
Backend API (FastAPI, Python)
        │  ┌───────────────────────────────────────────────────────────────┐
        │  │   LangGraph Multi-Agent Pipeline                              │
        │  │   Orchestrator -> Source Planner -> Retrievers (Whitelist/Tavily)│
        │  │   -> Credibility Filter -> Entity Resolver -> Spec Extractor      │
        │  │   -> Reviews & Sentiment -> Price Aggregator -> Ranker            │
        │  │   -> Persistence -> Exporter/Notifier                            │
        │  └───────────────────────────────────────────────────────────────┘
        │
        ▼
MongoDB Atlas (DB + Atlas Search + Vector Search)
      ├─ products, listings, reviews, price_history
      ├─ rss_items, sources, runs
      ├─ users, oauth_sessions, refresh_tokens, watches, alert_events
      └─ product_aliases (helper), goldens (tests)
```

**Data sources:**

* **Whitelist domains** (Amazon, BestBuy, Walmart, Target, B&H, MicroCenter, MediaMarkt, Saturn, Newegg, PCPartPicker; reviews: Wirecutter, CNET, TechRadar, LaptopMag, Tom's Hardware, DigitalTrends).
* **Tavily** (`search`, `crawl`, `map`, `extract`) for fresh and niche coverage.
* **RSS feeds** (Slickdeals, Pepper network: MyDealz/Dealabs/HotUKDeals, r/buildapcsales, PCPartPicker drops, retailer "deals" feeds).

**Models:**

* **OpenAI GPT-4o-mini** for query parsing, extraction, sentiment, contradiction detection, rationale.
* **Embeddings:**
  * **Default:** OpenAI `text-embedding-3-small` (1536-d).
  * **Optional Local:** `sentence-transformers/all-MiniLM-L6-v2` (384-d, CPU-friendly, cost effective).

## Backend System Architecture

```
                           +--------------------+
                           |   Clients (UI/API) |
                           +---------+----------+
                                     |
                                     v
+----------------------+    +--------+---------+    +-----------------------+
| Auth & Session Layer |<-->|  FastAPI Routers |--->| Service Layer / DI     |
+----------+-----------+    +--------+---------+    +-----------+-----------+
           |                               |                     |
           v                               v                     v
+----------+-----------+       +-----------+----------+   +------+-----------+
| JWT Cookie Validator |       |   LangGraph Engine   |   | Background Jobs  |
+----------------------+       +-----------+----------+   | (RSS ingestion)  |
                                              |              +------+-----------+
                                              v                     |
                                     +--------+--------+            |
                                     | Retrieval Hub   |<-----------+
                                     +--------+--------+            |
                                              |  \\               |
                                              |   \\              |
                                              v    v              |
                     +------------------+     |    +-----------------------+
                     | Tavily Retrieval |-----+    | RSS Vector Retrieval  |
                     | (live web nodes) |          | (Atlas vector search) |
                     +--------+---------+          +-----------+-----------+
                              |                                |
                              v                                v
                     +--------+---------+             +--------+---------+
                     | Tavily API       |             | Atlas Vector     |
                     | (search/extract) |             | Index (MongoDB)  |
                     +--------+---------+             +--------+---------+
                              |                                ^
                              v                                |
+----------------------+     +-------------+------+             |
| MongoDB Persistence  |<----| Repository Layer    |<------------+
+----------+-----------+     +-------------+------+             |
           ^                               |                     |
+----------+-----------+                   v                     |
| Notification /       |<------------------+---------------------+
| Analytics Hooks      |
+----------------------+
```

## LangGraph Multi-Agent Pipeline

### Agent Pipeline Flow

```
+------------------------+
| QueryOrchestratorAgent |
+-----------+------------+
            |
            v
+-----------+------------+
| RetrievalSplitterNode  |
+-----------+------------+ \
        /                    \
       /                       \
      v                          v
+-----------+------------+        +-----------------------+
| TavilyRetrieverAgent   |        | RSSVectorRetrieverAgent|
+-----------+------------+        +-----------+-----------+
            |                                 |
            v                                 v
+-----------+------------+        +-----------+-----------+
| CredibilityFilterAgent |        | RSSResultAdapter      |
+-----------+------------+        +-----------+-----------+
            |                                 |
            v                                 |
+-----------+------------+                    |
| SpecExtractorAgent     |                    |
+-----------+------------+                    |
            |                                 |
            v                                 |
+-----------+------------+                    |
| TavilyResultAdapter    |                    |
+-----------+------------+                    |
            |                                 |
            +---+-----------------------------+
                |
                v
+-----------+------------+
| ResultFusionNode       |
+-----------+------------+
            |
            v
+-----------+------------+
| ResultsRankerAgent     |
+-----------+------------+
            |
            v
+-----------+------------+
| Persistence & Response |
+------------------------+
```

**Pipeline Architecture:**

1. **QueryOrchestratorAgent** – parse user query -> normalized intent string (category, budget, constraints, priorities).
2. **RetrievalSplitterNode** – hybrid: whitelist + Tavily discovery when needed.
3. **TavilyRetrieverAgent** –
   * WhitelistRetriever: CSS/XPath parsing.
   * TavilyRetriever: `search` -> `map` -> `extract` (preferred) -> `crawl` (fallback).
4. **CredibilityFilterAgent** – domain rep, recency, extractability, consensus, affiliate penalty.
5. **SpecExtractorAgent** – schema-based JSON extraction (LLM fallback).
6. **ResultsRankerAgent** – weighted score of specs, sentiment, price, availability.
7. **Persistence** – store run, outputs, costs.

**Ranking formula:**

```
Score = 0.35*SpecFitness + 0.25*Sentiment + 0.30*PriceValue + 0.05*Availability - 0.05*RiskFlags
```

![Product Cards](images/smartshoper-cards.png)

## Technology Stack

### Backend Dependencies
- **FastAPI** - High-performance async API framework
- **LangGraph** - Multi-agent workflow orchestration  
- **MongoDB Atlas** - Vector search enabled NoSQL database
- **Tavily Python SDK** - Advanced web search and extraction
- **OpenAI API** - GPT-4o-mini for natural language processing
- **Pydantic** - Data validation and settings management
- **Motor** - Async MongoDB driver

### Frontend Dependencies
- **React 18** + **TypeScript** - Modern component-based UI
- **Vite** - Fast build tooling and development server
- **Custom Glass Morphism CSS** - Professional liquid glass effects
- **Lucide React** - Icon library
- **Responsive Design** - Mobile-first approach

### Key Features

- **Intelligent Search**: Natural language product queries with AI-powered intent detection
- **Smart Ranking**: Multi-criteria scoring system combining relevance, price value, and source credibility  
- **Price Discovery**: Advanced price extraction with multi-currency support (18+ currencies)
- **Favorites System**: Save products with notes, tags, and price alerts
- **Secure Authentication**: Google OAuth integration with JWT session management
- **Professional UI**: Glass morphism design with backdrop filters and smooth animations

![My Favorites](images/smartshoper-myfavorites.png)

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB Atlas account
- Tavily API key
- OpenAI API key
- Google OAuth credentials

### Backend Setup

```bash
# Install dependencies
cd backend
uv pip install -e ".[dev]"

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
# Install dependencies
cd frontend
npm install

# Start development server
npm run dev
```

### Environment Configuration

Create `.env` file in the root directory:

```env
# Environment
ENVIRONMENT=development
DEBUG=true

# External APIs
TAVILY_API_KEY=tvly-...
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Database
MONGO_USER=your-username
MONGO_PASS=your-password
MONGO_CLUSTER_URL=cluster0.mongodb.net
DATABASE_NAME=smartshopper

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Authentication
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Embeddings
EMBEDDINGS_PROVIDER=openai  # "openai" or "minilm"
```

### Production Deployment

**Single Container Build**
```bash
docker build -t smartshopper .
docker run -p 8000:8000 smartshopper
```

**AWS Elastic Beanstalk**
```bash
eb init && eb create && eb deploy
```

## API Endpoints

### Core Search API
- `POST /v1/search` – Execute product search through LangGraph pipeline
- `GET /v1/search/history` – Get user's search history
- `GET /v1/search/{run_id}` – Get specific search details

### Authentication
- `GET /auth/google/login` – Initiate Google OAuth flow
- `GET /auth/google/callback` – Handle OAuth callback
- `GET /auth/me` – Get current user profile
- `POST /auth/logout` – User logout

### Favorites Management
- `POST /v1/favorites` – Add product to favorites
- `GET /v1/favorites` – Get user's favorites with optional filtering
- `PUT /v1/favorites/{id}` – Update favorite details
- `DELETE /v1/favorites/{id}` – Remove favorite

### System
- `GET /health` – Application health check
- `GET /v1/health/workflow` – Workflow health status

## Production Features

### Security & Performance
- **JWT Authentication** with HttpOnly secure cookies
- **Google OAuth Integration** with proper redirect handling
- **Input Validation** with Pydantic models
- **CORS Configuration** for secure cross-origin requests
- **Rate Limiting** (planned implementation)
- **Async Operations** throughout the pipeline
- **Database Indexing** for optimal query performance
- **Vector Search** with dual embedding providers

### Monitoring & Observability
- **Structured Logging** with correlation IDs
- **Health Checks** for all system components
- **Execution Metrics** tracking cost and performance
- **Error Boundaries** with graceful degradation
- **Agent Step Tracking** for complete audit trails

### Data Management
- **Shared Collections** (no user_id): products, listings, reviews, sources
- **Per-User Collections** (access-limited): users, runs, watches, favorites
- **Vector Indexes** for semantic search capabilities
- **RSS Pipeline** for real-time deal ingestion
- **Price History** tracking for trend analysis

## Development

### Code Quality
- **Type Hints** everywhere in Python
- **TypeScript** for frontend type safety
- **Pydantic Models** for data validation
- **Structured Error Handling** throughout
- **Clean Architecture** with dependency injection

### Testing Strategy
- Unit tests with pytest + pytest-asyncio
- Golden URL regression tests
- Mock external API calls
- Database operation testing
- Frontend component testing

## Authors

- **Zuko Bronja** - *Author* - [zuko.bronja@gmail.com](mailto:zuko.bronja@gmail.com)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---