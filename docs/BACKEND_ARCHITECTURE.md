# SmartShopper Backend Architecture

**Tavily Engineering Assignment - Clean MVP Implementation**

## Executive Summary

SmartShopper backend is designed as a **Tavily-first** product search platform using LangGraph multi-agent architecture. The system prioritizes Tavily's search and extraction capabilities over traditional web scraping, implementing best practices for cost efficiency, reliability, and performance.

## Architecture Principles

### 1. Tavily-First Strategy
- **Primary Data Source**: Tavily Search → Extract pipeline
- **Fallback Strategy**: Crawl only when extract coverage < 60%
- **Cost Optimization**: Two-step process (search → extract) vs single-step
- **Quality Assurance**: Domain credibility scoring + coverage validation

### 2. Clean Agent Separation
- **Single Responsibility**: Each agent has one clear purpose
- **Minimal State**: Shared state only for essential workflow data
- **Error Boundaries**: Graceful degradation when agents fail
- **Testing Isolation**: Each agent can be tested independently

### 3. MVP Scope Control
- **Core Functionality**: Search, extract, rank, persist
- **Deferred Features**: RSS workers, advanced analytics, notifications
- **Quick Demo**: End-to-end search in <10 seconds
- **Scalable Foundation**: Easy to extend without architectural changes

## Backend System Diagram (ASCII)
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

### RSS Feed Ingestion Overview
- **Goal**: Enrich the product corpus with fresh deals and reviews sourced from curated RSS feeds.
- **Execution Model**: Background worker (FastAPI lifespan task or dedicated worker service) polling feeds on a schedule.
- **Persistence**: Two collections—`rss_feeds` (registry) and `rss_items` (normalized entries with linkage metadata).
- **Pipeline Hooks**: New RSS items can trigger downstream extraction or notification workflows.

```
+------------------+      +-------------------------+      +-----------------------+
| RSS Feed Registry|----->| Poller & Fetcher Worker |----->| Item Normalizer       |
| (rss_feeds)      |      | (async schedule)        |      | (dedupe, classify)    |
+------------------+      +-----------+-------------+      +-----------+-----------+
                                         |                            |
                                         v                            v
                                +--------+--------+         +--------+--------+
                                | Embedding Jobs  |         | Link to Agents  |
                                | (OpenAI/MiniLM) |         | (enqueue tasks) |
                                +--------+--------+         +--------+--------+
                                         |                            |
                                         v                            |
                                +--------+--------+                   |
                                | Persistence     |<------------------+
                                | (rss_items)     |
                                +--------+--------+
                                         |
                                         v
                                +--------+--------+
                                | Atlas Vector    |
                                | Index (MongoDB) |
                                +--------+--------+
                                         |
                                         v
                                +--------+--------+
                                | MongoDB Vector  |
                                | Retrieval Nodes |
                                +--------+--------+
                                         |
                                         v
                                +--------+--------+
                                | Notification /  |
                                | Analytics Hooks |
                                +-----------------+
```

- **Key Steps**:
  1. Scheduler selects due feeds based on `next_poll_at`, `poll_interval`, and health status.
  2. Fetcher respects ETag/Last-Modified headers and retries with exponential backoff on failure.
  3. Normalizer hashes GUID + link to avoid duplicates and extracts core metadata (title, summary, link, published_at, source).
  4. Classifier tags items (category, intent) and optionally enqueues LangGraph jobs for deeper extraction.
  5. Metrics/logging capture latency, failure counts, and item yield for observability and alerting.

### Hybrid Retrieval with RSS Vectors
- **Motivation**: Provide near-instant answers during search by blending Tavily’s fresh web results with semantically retrieved RSS content; doubles as a demo touchpoint for Atlas vector search.
- **Embedding Strategy**: Dual vectors per item—`summary_vec_openai_1536` and `summary_vec_minilm_384`—mirroring product embeddings. Background jobs generate/update embeddings as part of ingestion.
- **MongoDB Indexing**: Create dedicated Atlas vector indexes (`rss_summary_openai_idx`, `rss_summary_minilm_idx`). Apply recency/category filters in the query to keep results tight.
- **Parallel Query Flow**:
  1. Receive user query → QueryOrchestrator emits Tavily parameters and a text embedding job.
  2. In parallel: (a) TavilyRetriever runs live search/extraction; (b) vector search against `rss_items` using the same query embedding.
  3. Merge results—prioritize Tavily hits for new content, inject RSS items ranked by vector similarity + freshness, dedupe by product/link.
  4. ResultsRankerAgent or a merge policy surfaces RSS items as “latest deal/review” cards alongside Tavily findings.
- **Latency Expectations**: Atlas vector search adds ~100 ms; parallelization ensures overall response time remains dominated by Tavily latency, maintaining demo responsiveness.

### Vector Index Setup Requirements

The RSS vector retrieval functionality requires two Atlas Search vector indexes to be created manually on the `rss_items` collection. These indexes enable semantic search of RSS content alongside Tavily results.

#### Required Vector Indexes

**Index 1: `rss_summary_minilm_idx`**
- **Collection**: `smartshopper.rss_items`
- **Field**: `summary_vec_minilm_384`
- **Dimensions**: 384
- **Similarity**: cosine

**Index 2: `rss_summary_openai_idx`**
- **Collection**: `smartshopper.rss_items`
- **Field**: `summary_vec_openai_1536`
- **Dimensions**: 1536
- **Similarity**: cosine

#### Setup Using MongoDB Compass (Recommended)

1. **Connect MongoDB Compass to your Atlas cluster**
2. **Navigate to the collection**: `smartshopper` database → `rss_items` collection
3. **Go to Search Indexes tab**
4. **Click "Create Search Index"**
5. **Select "JSON Editor"** and use these definitions:

```json
// For rss_summary_minilm_idx
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

// For rss_summary_openai_idx
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

6. **Create both indexes** and wait for them to reach "Ready" status
7. **Verify functionality**: RSS vector search will automatically work once indexes are active

#### Troubleshooting Vector Indexes

**Common Issues:**
- **M0 Free Tier**: Atlas Search not supported - RSS will use Tavily-only mode
- **Index Creation Fails**: Ensure Atlas Search is enabled on your cluster
- **Performance Issues**: Vector indexes may take time to build on large collections
- **"Ready" Status**: Both indexes must show "Ready" status for RSS search to work
- **Missing Collection**: Ensure `rss_items` collection exists before creating indexes

**Graceful Degradation:**
- Without indexes: RSS search gracefully degrades to Tavily-only results
- Index creation failure: Application continues to function normally
- Vector search errors: Automatically falls back to Tavily pipeline

---

## Agent Architecture

### Agent Pipeline Diagram (ASCII)
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

**Parallel Retrieval Flow**
- `RetrievalSplitterNode` duplicates the orchestrated state for Tavily (live web) and RSS (vector-backed) branches.
- `RSSVectorRetrieverAgent` queries MongoDB Atlas vector indexes while `RSSResultAdapter` normalizes hits back into the shared product schema.
- Tavily branch runs `CredibilityFilterAgent` → `SpecExtractorAgent` → `TavilyResultAdapter` to produce aligned structured payloads.
- `ResultFusionNode` merges both streams ahead of ranking and persistence so downstream layers stay agnostic to source.

### Agent 1: QueryOrchestratorAgent
**Purpose**: Parse user queries and determine search strategy

**Input**: Raw user query string
**Output**: Structured search parameters

```python
@dataclass
class QueryResult:
    intent: str  # "product_search", "review_search", "comparison"
    query_terms: List[str]
    filters: Dict[str, Any]  # price_range, category, brand
    search_params: Dict[str, Any]  # for Tavily
```

**Logic**:
- Extract product categories, price ranges, brand preferences
- Determine search intent (product vs review vs comparison)
- Generate optimized Tavily search parameters
- Handle query variations and synonyms

**Dependencies**: OpenAI for query parsing
**Test Strategy**: Golden query dataset with expected outputs

---

### Agent 2: TavilyRetrieverAgent
**Purpose**: Execute Tavily search and extraction following best practices

**Input**: Search parameters from QueryOrchestrator
**Output**: Raw search results + extracted content

```python
@dataclass 
class TavilyResult:
    search_results: List[SearchResult]
    extracted_content: List[ExtractedContent]
    coverage_score: float
    total_credits_used: int
```

**Tavily Implementation**:
- **Step 1**: Search with domain filtering and relevance scoring
- **Step 2**: Extract from top URLs (score > 0.5)
- **Parameters**: `search_depth="advanced"`, `extract_depth="advanced"`
- **Cost Control**: Max 5 search results, async extraction
- **Error Handling**: Retry with fallback parameters

**Dependencies**: Tavily Python SDK
**Test Strategy**: Mock Tavily responses for consistent testing

---

### Agent 3: CredibilityFilterAgent  
**Purpose**: Score and filter results by source credibility

**Input**: Raw Tavily results
**Output**: Credibility-scored and filtered results

```python
@dataclass
class CredibilityScore:
    domain_reputation: float  # 0.0-1.0
    recency_score: float     # 0.0-1.0  
    extractability: float    # 0.0-1.0
    final_score: float       # weighted combination
```

**Scoring Algorithm**:
```
final_score = 0.5 * domain_reputation + 
              0.3 * recency_score + 
              0.2 * extractability
```

**Domain Reputation Map**:
- amazon.com: 1.0, bestbuy.com: 0.95, walmart.com: 0.9
- wirecutter.nytimes.com: 0.95, cnet.com: 0.9, techradar.com: 0.85
- Unknown domains: 0.7 (default)

**Dependencies**: Domain configuration, date parsing
**Test Strategy**: Known domains with expected scores

---

### Agent 4: SpecExtractorAgent
**Purpose**: Extract structured product data using Phase 3 hybrid system

**Input**: Credibility-filtered content  
**Output**: Structured product specifications

```python
@dataclass
class ProductSpec:
    title: str
    brand: Optional[str]
    model: Optional[str] 
    price: Optional[float]
    currency: str
    specs: Dict[str, Any]  # category-specific fields
    images: List[str]
    availability: str
```

**Extraction Strategy**:
- **Primary**: Use Tavily extracted structured data
- **Enhancement**: LLM extraction for missing fields
- **Validation**: Schema validation against TAVILY_EXPLORATION.md
- **Coverage**: Require minimum 60% field completion

**Dependencies**: OpenAI for LLM extraction, Pydantic for validation
**Test Strategy**: Golden product pages with expected extractions

---

### Agent 5: ResultsRankerAgent
**Purpose**: Score and rank products by multiple criteria

**Input**: Structured product specifications
**Output**: Ranked product list with scores

```python
@dataclass
class RankedResult:
    product: ProductSpec
    relevance_score: float    # query match
    price_value_score: float  # price competitiveness  
    source_quality_score: float  # credibility
    final_rank_score: float   # weighted combination
```

**Ranking Algorithm**:
```
final_rank = 0.4 * relevance_score +
             0.3 * price_value_score + 
             0.3 * source_quality_score
```

**Dependencies**: Embedding similarity for relevance
**Test Strategy**: Known product sets with expected rankings

---

## Data Flow Architecture

```
User Query
    ↓
QueryOrchestratorAgent → search_params
    ↓
TavilyRetrieverAgent → raw_results + extracted_content
    ↓  
CredibilityFilterAgent → credibility_scored_results
    ↓
SpecExtractorAgent → structured_products
    ↓
ResultsRankerAgent → ranked_product_list
    ↓
MongoDB Persistence → stored_results
    ↓
FastAPI Response → JSON to frontend
```

## State Management

### SmartShopperState (LangGraph Compatible)
```python
class SmartShopperState(TypedDict):
    # Query Processing
    query: str
    intent: str
    search_params: Dict[str, Any]
    
    # Tavily Results  
    raw_search_results: List[Dict]
    extracted_content: List[Dict]
    coverage_score: float
    
    # Processing Results
    credibility_scores: List[Dict]
    structured_products: List[Dict] 
    ranked_results: List[Dict]
    
    # Metadata
    credits_used: int
    processing_time_ms: int
    errors: List[str]
```

**Key Principles**:
- Minimal state: Only essential workflow data
- JSON serializable: Compatible with LangGraph requirements
- Clear typing: TypedDict for IDE support and validation
- Error tracking: Graceful error accumulation

## Technology Stack

### Core Dependencies
```python
# API Framework
fastapi = "^0.104.1"
uvicorn = "^0.24.0"

# AI/ML Pipeline  
langgraph = "^0.0.55"
langchain-openai = "^0.0.2"
tavily-python = "^0.3.3"

# Database
motor = "^3.3.2"  # Async MongoDB
pymongo = "^4.6.0"

# Data Processing
pydantic = "^2.5.0"
numpy = "^1.24.3"

# Auth & Security
python-jose[cryptography] = "^3.3.0"
passlib[bcrypt] = "^1.7.4"
```

### Configuration Management
```python
class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # APIs
    TAVILY_API_KEY: str
    OPENAI_API_KEY: str
    
    # Database
    MONGODB_URL: str
    DATABASE_NAME: str = "smartshopper"
    
    # Auth
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    
    # Performance
    MAX_CONCURRENT_REQUESTS: int = 10
    TAVILY_RATE_LIMIT: int = 100  # per minute
```

## Database Schema

### Collections Design

**Shared Collections** (no user_id):
```python
# products: Canonical product records
{
    "_id": ObjectId,
    "title": str,
    "brand": str,
    "model": str, 
    "category": str,
    "specs": Dict[str, Any],
    "title_embedding": List[float],  # 384-d MiniLM
    "created_at": datetime,
    "updated_at": datetime
}

# listings: Individual offers/prices
{
    "_id": ObjectId,
    "product_id": ObjectId,
    "url": str,
    "domain": str,
    "price": float,
    "currency": str,
    "availability": str,
    "credibility_score": float,
    "first_seen": datetime,
    "last_seen": datetime
}

# sources: URL audit trail
{
    "_id": ObjectId,
    "url": str,
    "domain": str,
    "page_type": str,  # "ecom", "review"
    "tavily_endpoint": str,  # "search", "extract"
    "credibility_score": float,
    "last_crawled": datetime
}
```

**Per-User Collections** (filtered by user_id):
```python
# runs: Query history
{
    "_id": ObjectId,
    "user_id": ObjectId,
    "query": str,
    "intent": str,
    "results_count": int,
    "credits_used": int,
    "processing_time_ms": int,
    "created_at": datetime
}
```

### Indexes Strategy
```python
# Vector search for products
products.create_index([("title_embedding", "2dsphere")])

# Query optimization
listings.create_index([("product_id", 1), ("price", 1)])
sources.create_index([("domain", 1), ("credibility_score", -1)])
runs.create_index([("user_id", 1), ("created_at", -1)])
```

## API Endpoints

### Core Search API
```python
@router.post("/v1/search")
async def search_products(
    request: SearchRequest,
    current_user: User = Depends(get_current_user)
) -> SearchResponse:
    """Execute product search through LangGraph pipeline"""
    
@router.get("/v1/products/{product_id}")
async def get_product(product_id: str) -> ProductResponse:
    """Get detailed product information"""
    
@router.get("/v1/runs")
async def get_search_history(
    current_user: User = Depends(get_current_user)
) -> List[RunResponse]:
    """Get user's search history"""
```

### Authentication
```python
@router.post("/auth/login")
async def login(credentials: LoginRequest) -> AuthResponse:
    """Email/password or Google OAuth login"""
    
@router.post("/auth/register") 
async def register(user_data: RegisterRequest) -> AuthResponse:
    """User registration with email verification"""
    
@router.get("/auth/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """Get current user profile"""
```

## Error Handling Strategy

### Exception Hierarchy
```python
class SmartShopperException(Exception):
    def __init__(self, message: str, details: Dict = None):
        self.message = message
        self.details = details or {}

class TavilyAPIException(SmartShopperException):
    pass

class ExtractionException(SmartShopperException): 
    pass

class DatabaseException(SmartShopperException):
    pass
```

### Error Response Format
```python
{
    "error": {
        "type": "TavilyAPIException",
        "message": "Tavily rate limit exceeded",
        "details": {
            "credits_remaining": 0,
            "reset_time": "2024-01-01T12:00:00Z"
        }
    },
    "request_id": "req_123456"
}
```

## Testing Strategy

### Unit Testing
```python
# Agent isolation testing
def test_query_orchestrator_intent_detection():
    agent = QueryOrchestratorAgent()
    result = agent.process("gaming laptop under $2000")
    assert result.intent == "product_search"
    assert "laptop" in result.query_terms
    assert result.filters["price_max"] == 2000

# Tavily integration testing (mocked)
def test_tavily_retriever_with_mocks():
    with patch('tavily.TavilyClient') as mock_client:
        # Test agent behavior with controlled responses
        pass
```

### Integration Testing  
```python
# End-to-end pipeline testing
async def test_full_search_pipeline():
    state = SmartShopperState(query="MacBook Pro M3")
    result = await run_search_pipeline(state)
    assert len(result["ranked_results"]) > 0
    assert result["credits_used"] > 0
```

### Performance Testing
```python
# Load testing with concurrent requests
async def test_concurrent_search_performance():
    tasks = [search_products("laptop") for _ in range(10)]
    results = await asyncio.gather(*tasks)
    assert all(r.processing_time_ms < 10000 for r in results)
```

## Deployment Architecture

### Single Container (MVP Demo)
```dockerfile
FROM python:3.11-slim

# Install dependencies
COPY pyproject.toml .
RUN pip install .

# Copy application
COPY app/ app/
COPY frontend/dist/ static/

# Run FastAPI with static file serving
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Configuration
```bash
# Production environment variables
ENVIRONMENT=production
MONGODB_URL=mongodb+srv://...atlas.mongodb.net/
TAVILY_API_KEY=tvly-prod-...
OPENAI_API_KEY=sk-prod-...
JWT_SECRET_KEY=secure-random-key
```

## Monitoring & Observability

### Structured Logging
```python
import structlog

logger = structlog.get_logger()

# In agents
logger.info(
    "tavily_search_completed",
    query=query,
    results_count=len(results),
    credits_used=credits,
    processing_time_ms=elapsed_ms
)
```

### Metrics Collection
```python
# Track key business metrics
- search_requests_per_minute
- tavily_credits_consumed_per_hour  
- average_search_processing_time
- extraction_success_rate
- user_satisfaction_scores
```

### Health Checks
```python
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "services": {
            "mongodb": await check_mongodb_connection(),
            "tavily": await check_tavily_api(),
            "openai": await check_openai_api()
        }
    }
```

---

## Implementation Phases

### Phase 1: Core Pipeline (Week 1)
- [ ] QueryOrchestratorAgent implementation
- [ ] TavilyRetrieverAgent with best practices
- [ ] Basic CredibilityFilterAgent  
- [ ] Simple SpecExtractorAgent
- [ ] ResultsRankerAgent MVP
- [ ] LangGraph workflow integration

### Phase 2: Persistence & API (Week 1)
- [ ] MongoDB collections and indexes
- [ ] FastAPI endpoints for search
- [ ] Authentication system (JWT + Google OAuth)
- [ ] Error handling and logging
- [ ] Basic monitoring

### Phase 3: Frontend Integration (Week 2) 
- [ ] React search interface
- [ ] Results display with ranking
- [ ] User authentication flow
- [ ] Search history
- [ ] Responsive design

### Phase 4: Production Readiness (Week 2)
- [ ] Docker containerization  
- [ ] AWS Elastic Beanstalk deployment
- [ ] MongoDB Atlas setup
- [ ] Performance optimization
- [ ] Demo video and documentation

---

This architecture prioritizes **simplicity, reliability, and Tavily integration excellence** over complex features. The MVP focuses on delivering a working product search experience that demonstrates Tavily's capabilities effectively.
