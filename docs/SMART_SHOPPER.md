# SmartShopper – Implementation Blueprint

SmartShopper helps users find the **best products, prices, and deals** by combining a hybrid web retrieval strategy (trusted sites + Tavily), LLM-powered extraction/synthesis (OpenAI GPT-4o-mini), MongoDB Atlas (with Vector Search), an RSS deals pipeline, and real-time notifications (email/Discord, WhatsApp later). This document provides the full implementation plan.

---

## 1. Product Scope

**Core Value:** Search for a category (e.g., *“best laptops under €1,000 for programming”*) -> get a **ranked, explainable shortlist** with specs, prices, value assessment, sources, and optional alerts on price drops.

**Primary Users:** Consumers who want **reliable, current, cross-site comparisons and deal alerts**.

---

## 2. High-Level Architecture

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

* **Whitelist domains** (Amazon, BestBuy, Walmart, Target, B\&H, MicroCenter, MediaMarkt, Saturn, Newegg, PCPartPicker; reviews: Wirecutter, CNET, TechRadar, LaptopMag, Tom’s Hardware, DigitalTrends).
* **Tavily** (`search`, `crawl`, `map`, `extract`) for fresh and niche coverage.
* **RSS feeds** (Slickdeals, Pepper network: MyDealz/Dealabs/HotUKDeals, r/buildapcsales, PCPartPicker drops, retailer “deals” feeds).

**Models:**

* **OpenAI GPT-4o-mini** for query parsing, extraction, sentiment, contradiction detection, rationale.
* **Embeddings:**

  * **Default:** OpenAI `text-embedding-3-small` (1536-d).
  * **Optional Local:** `sentence-transformers/all-MiniLM-L6-v2` (384-d, CPU-friendly, cost effective).

---

## 3. Backend Services

### FastAPI modules

* `app/main.py` – app init, routing, middleware.
* `app/auth/` – Google OIDC + email/password.
* `app/api/` – search, results, watches, history.
* `app/agents/` – LangGraph nodes/orchestration.
* `app/db/` – Mongo client, repositories, indexes.
* `app/extractors/` – domain parsers + LLM extractors.
* `app/rss/` – RSS ingestion worker.
* `app/notify/` – email/Discord sender.
* `app/utils/` – currency, units, dedupe, hashing.
* `app/config.py` – env vars (pydantic Settings).

### Key Endpoints

* `/v1/search` – run query.
* `/v1/products/{id}` – product details.
* `/v1/watches` – manage watches.
* `/v1/runs` – query history.
* `/auth/*` – login/register/OAuth/refresh/logout.
* `/v1/export/{run_id}.{md|pdf|csv}` – export results.

### Security

* JWT (access 15m, refresh 7–30d) in HttpOnly Secure cookies.
* CSRF token for state-changing requests.
* Rate limiting (login/register/search).
* Pydantic validation.
* Secrets from env vars.

---

## 4. LangGraph Multi-Agent Pipeline

1. **Orchestrator** – parse user query -> normalized intent string (category, budget, constraints, priorities).
2. **Source Planner** – hybrid: whitelist + Tavily discovery when needed.
3. **Retriever** –

   * WhitelistRetriever: CSS/XPath parsing.
   * TavilyRetriever: `search` -> `map` -> `extract` (preferred) -> `crawl` (fallback).
4. **Credibility Filter** – domain rep, recency, extractability, consensus, affiliate penalty.
5. **Entity Resolver** – canonicalize brand/model/SKU, alias mapping.
6. **Spec Extractor** – schema-based JSON extraction (LLM fallback).
7. **Reviews & Sentiment Agent** – pros, cons, sentiment, contradictions.
8. **Price Aggregator** – listings + RSS -> current price, recent best, floor/ceiling.
9. **Ranker/Recommender** – weighted score of specs, sentiment, price, availability.
10. **Persistence** – store run, outputs, costs.
11. **Exporter/Notifier** – create exports, trigger alerts.

**Ranking formula:**

```
Score = 0.35*SpecFitness + 0.25*Sentiment + 0.30*PriceValue + 0.05*Availability - 0.05*RiskFlags
```

---

## 5. Tavily Integration Best Practices

**Workflow:**

* `search` -> candidate URLs (domain/recency filters).
* `map` -> triage pages, drop low-signal.
* `extract` -> structured data (preferred).
* `crawl` + LLM schema -> fallback if `extract` fails.

**Schemas:**

* **E-commerce:** `{ title, brand, model, sku, gtin, price, currency, availability, was_price?, promo_text?, rating?, review_count?, images[], specs{...} }`
* **Editorial review:** `{ headline, author?, published_at?, verdict_score?, pros[], cons[], summary, recommended_alternatives[] }`

**Credibility score:**

```
0.4*DomainRep + 0.2*Recency + 0.2*Extractability + 0.1*Consensus - 0.05*Affiliate - 0.05*DupDomain
```

**Ops tips:**

* Cache `extract` results by URL hash.
* Limit 2–3 pages per domain, max \~30 per run.
* Short-circuit when you have ≥4 strong e-commerce + ≥2 reviews.
* Maintain golden URLs for test runs.
* Log endpoint used (`search`, `map`, `extract`, `crawl`).

---

## 6. MongoDB Atlas Schema

### Key Collections

* `users` – accounts (Google or email/password).
* `products` – canonical products (with multiple embedding vectors).
* `listings` – individual offers.
* `reviews` – editorial/user reviews.
* `price_history` – time series.
* `rss_items` – normalized deal feed entries.
* `sources` – page audit trail + credibility.
* `runs` – full query traces.
* `watches` – saved alerts.
* `alert_events` – triggered notifications.
* `product_aliases` – helper for entity resolution.
* `goldens` – golden dataset for regression testing.

**Vector Search:**

* **OpenAI embeddings** (1536-d): `title_vec_openai_1536`, `spec_vec_openai_1536`.
* **MiniLM embeddings** (384-d): `title_vec_minilm_384`, `spec_vec_minilm_384`.
* Maintain **dual indexes** so provider can switch by config.

---

## 7. RSS Pipeline

* Ingest every 5–10 min: parse -> normalize -> resolve product ID -> upsert.
* Dedupe by `(title|price|domain)` hash.
* Append matched prices to `price_history`.
* Join RSS + listings at query time for value analysis.

---

## 8. Frontend (React)

**Stack:** React + Vite, TailwindCSS, shadcn/ui, React Router, Axios, Recharts.

**Components:**

* Auth: Login, Register, Profile.
* Search: `SearchBar`, pipeline progress stepper.
* Results:

  * `ComparisonTable` (specs, price, sentiment).
  * `RecommendationCard` (top picks).
  * `SourcesList` (credibility + links).
  * `PriceHistoryChart` (sparkline).
  * `WatchToggle`.
* History: past queries and results.

---

## 9. Authentication

* **Google OAuth (OIDC)** with PKCE.
* **Email/password** with Argon2id hashing + email verification.
* JWT in cookies (access + refresh).
* Collections: `users`, `oauth_sessions`, `refresh_tokens`, `email_verification_tokens`, `password_reset_tokens`.
* Endpoints: `/auth/google/start`, `/auth/google/callback`, `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/refresh`, `/auth/verify`, `/auth/forgot`, `/auth/reset`, `/me`.

---

## 10. Notifications

* Users save watches on products or queries.
* Conditions: price below X, % drop ≥ Y, in stock, new review.
* Worker checks watches every 5–10 min.
* On trigger: create `alert_events` and send notifications.
* Channels:

  * Email (SES/SendGrid).
  * Discord (webhook POST).
  * WhatsApp (future via Twilio).

---

## 11. Local Embeddings Option (CPU)

**Model:** `sentence-transformers/all-MiniLM-L6-v2` (384-d).

* **Use cases:**

  * Default for development (no cost).
  * Possible in production if latency is acceptable on AWS EB `t2.micro/m2.micro` CPU.

* **Implementation:**

  * Abstraction: `EmbeddingProvider` with `OpenAIEmbedder` and `MiniLMEmbedder`.
  * Config flag: `SMARTSHOPPER_EMBEDDINGS_PROVIDER=openai|minilm`.
  * Dual-write embeddings into Mongo: both OpenAI (1536) and MiniLM (384).
  * Two vector indexes in Atlas; switch by provider.

* **Deployment on EB:**

  * Bake model into Docker image (avoid runtime download).
  * Limit Torch CPU threads (`torch.set_num_threads(1)`).
  * Warm model at startup.
  * Batch embedding (e.g., 32 items).

* **Fallback:**

  * If MiniLM fails (OOM/latency), switch config to OpenAI.
  * Store both vectors so switching is instant.

* **Performance:**

  * Titles/spec strings are short -> MiniLM runs well on CPU.
  * Cache query embeddings for repeat searches.
  * Monitor precision\@3 vs OpenAI baseline.

---

## 12. Data Ownership & Sharing

### Shared (global cache, no user ID)

* `products`, `listings`, `reviews`, `price_history`, `rss_items`, `sources`, `product_aliases`, `goldens`

### Per-user (private, access-limited)

* `users`, `oauth_sessions`, `refresh_tokens`, `runs`, `watches`, `alert_events`

**Principles:**

* Shared collections **never store user identifiers**.
* Per-user data always filtered by `user_id` in API queries.
* Users may export/delete their data (`/v1/me/export`, `/v1/me/delete`).
* Optional “incognito search” skips saving to `runs`.
* Token collections use TTL indexes (24–48h).
* PII minimized: only store email + optional Discord webhook.

**Third-party flows:**

* OpenAI: receives only page content/snippets (no PII).
* Tavily: receives search queries/URLs.
* Email provider: gets recipient email + product alert text.
* Discord webhook: receives alert payload (no PII).

---

## 13. Deployment

* **Backend**: FastAPI on AWS Elastic Beanstalk.
* **DB**: MongoDB Atlas (vector search enabled).
* **Frontend**: React -> AWS Amplify or S3+CloudFront.
* **Workers**: RSS ingest + alert evaluator.
* **Secrets**: stored as AWS EB environment vars.
* **Email**: SES or SendGrid.

---

## 14. Observability & Testing

* **Logging**: structured JSON logs with request IDs.
* **Tracing**: store node timings in `runs.steps`.
* **Metrics**: extraction success rate, source diversity, latency, token usage.
* **Golden tests**: \~50–200 queries in `goldens` collection to catch regressions.
* **Security**: rate limit, CSRF, email verification, strong hashing.

---

## 15. Roadmap (Post-MVP)

* WhatsApp alerts (Twilio).
* Browser extension for on-site comparisons.
* More categories/spec schemas.
* Community deal signals (votes).
* Personalization (prioritize battery vs performance, etc.).
* SSO integration (Keycloak/Auth0).

---

## 16. Definition of Done (MVP)

* User login (Google/email).
* Query -> ranked product list with specs, prices, sentiment, sources.
* Product detail with price history.
* Watches + notifications (email/Discord).
* RSS + Tavily integration running.
* Mongo collections + vector index created.
* Deployment on AWS + MongoDB Atlas.
* Docs and short demo recording.

