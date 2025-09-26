# TAVILY EXPLORATION

**SmartShopper × Tavily Integration Guide (with JSON Schemas)**

This document defines how **SmartShopper** integrates with **Tavily** for discovery and structured extraction, and provides **contract schemas** for `extract` results with validation rules, examples, and fallbacks. It complements the main `SMART_SHOPPER` spec.


## TAVILY Documentation & Best Practices

**SmartShopper** leverages Tavily as the primary search and extraction engine. All implementation must follow Tavily best practices.

### Tavily API Reference:
- Introduction: https://docs.tavily.com/documentation/api-reference/introduction
- Search Endpoint: https://docs.tavily.com/documentation/api-reference/endpoint/search
- Extract Endpoint: https://docs.tavily.com/documentation/api-reference/endpoint/extract
- Crawl Endpoint: https://docs.tavily.com/documentation/api-reference/endpoint/crawl
- Map Endpoint: https://docs.tavily.com/documentation/api-reference/endpoint/map
- Usage Monitoring: https://docs.tavily.com/documentation/api-reference/endpoint/usage

### Best Practices (MANDATORY):
- Search: https://docs.tavily.com/documentation/best-practices/best-practices-search
- Extract: https://docs.tavily.com/documentation/best-practices/best-practices-extract
- Crawl: https://docs.tavily.com/documentation/best-practices/best-practices-crawl

### Framework Integrations:
- LangChain: https://docs.tavily.com/documentation/integrations/langchain
- OpenAI Schemas:
  - Base: https://docs.tavily.com/documentation/integrations/openai
  - Search: https://docs.tavily.com/documentation/integrations/openai#search-schema
  - Extract: https://docs.tavily.com/documentation/integrations/openai#extract-schema
  - Map: https://docs.tavily.com/documentation/integrations/openai#map-schema
  - Crawl: https://docs.tavily.com/documentation/integrations/openai#crawl-schema
- Pydantic-AI: https://docs.tavily.com/documentation/integrations/pydantic-ai

---

## 0) Endpoint Strategy (recap)

1. **search** -> candidate URLs (use domain/recency filters, cap per domain).
2. **map** -> triage many URLs; keep `ecom|review` with specs.
3. **extract** -> **preferred** structured extraction to JSON (cheap, robust).
4. **crawl** -> fallback to raw HTML/text; run LLM schema extraction only if `extract` fails or is low-coverage.

Short-circuit once you have **≥4 strong e-commerce** pages and **≥2 credible reviews**.

---

## 1) Extraction Contracts (JSON Schemas)

We version schemas so extractors and validation stay stable across releases.

### 1.1 Schema: `ecom_v1`

Represents a single e-commerce product/offer page.

```json
{
  "title": "ecom_v1",
  "type": "object",
  "required": ["url", "domain", "page_type", "product", "offer", "extracted_at"],
  "properties": {
    "schema_version": { "type": "string", "enum": ["ecom_v1"] },
    "url": { "type": "string", "format": "uri" },
    "domain": { "type": "string" },
    "page_type": { "type": "string", "enum": ["ecom"] },

    "product": {
      "type": "object",
      "required": ["title"],
      "properties": {
        "title": { "type": "string" },
        "brand": { "type": ["string", "null"] },
        "model": { "type": ["string", "null"] },
        "sku":   { "type": ["string", "null"] },
        "gtin":  { "type": ["string", "null"], "description": "EAN/UPC/GTIN" },
        "category": { "type": ["string", "null"], "enum": ["laptop","phone","camera",null] },
        "images": { "type": "array", "items": { "type": "string", "format": "uri" } },
        "specs": {
          "type": "object",
          "additionalProperties": true,
          "properties": {
            "cpu": { "type": ["string","null"] },
            "gpu": { "type": ["string","null"] },
            "ram_gb": { "type": ["number","null"] },
            "storage_gb": { "type": ["number","null"] },
            "screen_size_in": { "type": ["number","null"] },
            "resolution": { "type": ["string","null"] },
            "refresh_hz": { "type": ["number","null"] },
            "panel_type": { "type": ["string","null"] },
            "battery_wh": { "type": ["number","null"] },
            "battery_mah": { "type": ["number","null"] },
            "weight_kg": { "type": ["number","null"] },
            "ports": { "type": "array", "items": { "type": "string" } }
          }
        }
      }
    },

    "offer": {
      "type": "object",
      "required": ["price", "currency", "availability"],
      "properties": {
        "price": { "type": ["number","null"] },
        "currency": { "type": ["string","null"], "minLength": 3, "maxLength": 3 },
        "was_price": { "type": ["number","null"] },
        "promo_text": { "type": ["string","null"] },
        "availability": { "type": ["string","null"], "enum": ["in_stock","out_of_stock","preorder","backorder",null] },
        "shipping_cost": { "type": ["number","null"] },
        "delivery_eta": { "type": ["string","null"] },
        "seller": { "type": ["string","null"] },
        "rating": { "type": ["number","null"], "minimum": 0, "maximum": 5 },
        "review_count": { "type": ["integer","null"], "minimum": 0 }
      }
    },

    "content_hash": { "type": ["string","null"] },
    "extracted_at": { "type": "string", "format": "date-time" }
  },
  "additionalProperties": true
}
```

**Coverage rule for `ecom_v1`**

* Must have: `product.title`, `offer.price` OR (`offer.availability` == "out\_of\_stock"), `url`, `domain`.
* For **laptops/phones/cameras**, we expect at least **3 spec fields** (after unit coercion).
* If overall field coverage < **60%**, mark as **low\_coverage** and trigger `crawl` fallback.

---

### 1.2 Schema: `review_v1`

Represents a single editorial/review page.

```json
{
  "title": "review_v1",
  "type": "object",
  "required": ["url", "domain", "page_type", "review", "extracted_at"],
  "properties": {
    "schema_version": { "type": "string", "enum": ["review_v1"] },
    "url": { "type": "string", "format": "uri" },
    "domain": { "type": "string" },
    "page_type": { "type": "string", "enum": ["review"] },

    "review": {
      "type": "object",
      "required": ["headline"],
      "properties": {
        "headline": { "type": "string" },
        "author": { "type": ["string","null"] },
        "published_at": { "type": ["string","null"], "format": "date-time" },
        "updated_at": { "type": ["string","null"], "format": "date-time" },
        "verdict_score": { "type": ["number","null"], "minimum": 0, "maximum": 10 },
        "pros": { "type": "array", "items": { "type": "string" } },
        "cons": { "type": "array", "items": { "type": "string" } },
        "summary": { "type": ["string","null"] },
        "recommended_alternatives": { "type": "array", "items": { "type": "string" } },
        "product_refs": { "type": "array", "items": { "type": "string" } }
      }
    },

    "content_hash": { "type": ["string","null"] },
    "extracted_at": { "type": "string", "format": "date-time" }
  },
  "additionalProperties": true
}
```

**Coverage rule for `review_v1`**

* Must have: `review.headline`, any of `pros|cons|summary`.
* Prefer `published_at` or `updated_at` for **recency**.
* If pros+cons are empty and no summary, mark as **low\_coverage**.

---

## 2) Category Spec Sub-Schemas (hints for LLM / validators)

These are informal but recommended **per-category fields** to enforce during extraction/validation.

### 2.1 Laptops

```
cpu (string), gpu (string), ram_gb (number), storage_gb (number),
screen_size_in (number), resolution (string), refresh_hz (number?),
panel_type (string?), battery_wh (number?), weight_kg (number?),
ports[] (strings)
```

### 2.2 Phones

```
chipset (string), ram_gb (number), storage_gb (number),
display (string or split into size/resolution/refresh),
battery_mah (number), charge_watt (number?),
rear_cameras[] (e.g., 50MP main, 12MP ultrawide), selfie_camera (string?),
weight_g (number?)
```

### 2.3 Cameras

```
sensor_size (string), megapixels (number), mount (string),
video_bitrate (string or number?), stabilization (string/bool),
weight_g (number), battery_life (string/number?)
```

> Coerce units: **GB, Wh, Hz, mAh, inches, kg, g**; normalize decimals.

---

## 3) Coverage Metric & Fallback Logic

**Coverage score** = (# non-null extracted fields) / (# expected fields).

* For `ecom_v1`: weigh `offer.price|availability`, `product.title`, and **3+ key specs** higher.
* If `< 0.60` -> mark **low\_coverage: true**; call `crawl` and run LLM schema extraction; then **merge** (prefer concrete numeric fields from either).

**Merging strategy:**

* Prefer fields with numeric values from either extractor.
* For text fields, prefer `extract`; fallback to LLM.
* Keep a `merge_notes` object in memory (not persisted) for debugging.

---

## 4) Example Calls & Payloads

### 4.1 `extract` request (e-commerce)

```json
{
  "url": "https://www.example-retailer.com/product/xyz",
  "schema": "ecom_v1",
  "locale": "en-US",
  "hints": { "category": "laptop" }
}
```

**Expected response (abridged)**

```json
{
  "schema_version": "ecom_v1",
  "url": "https://www.example-retailer.com/product/xyz",
  "domain": "example-retailer.com",
  "page_type": "ecom",
  "product": {
    "title": "ASUS ROG Zephyrus G14 (2024)",
    "brand": "ASUS",
    "model": "ROG Zephyrus G14",
    "sku": "GA402-XYZ",
    "gtin": "4711081888888",
    "category": "laptop",
    "images": ["https://.../g14.png"],
    "specs": {
      "cpu": "Ryzen 9 8945HS",
      "gpu": "RTX 4070",
      "ram_gb": 32,
      "storage_gb": 1024,
      "screen_size_in": 14,
      "resolution": "2560x1600",
      "refresh_hz": 120,
      "battery_wh": 73,
      "weight_kg": 1.6,
      "ports": ["USB-C", "HDMI 2.1"]
    }
  },
  "offer": {
    "price": 1799.99,
    "currency": "USD",
    "was_price": 1999.99,
    "promo_text": "Back-to-school",
    "availability": "in_stock",
    "shipping_cost": 0,
    "delivery_eta": "2-3 days",
    "seller": "Example Retailer",
    "rating": 4.6,
    "review_count": 203
  },
  "content_hash": "sha256:abc123...",
  "extracted_at": "2025-09-19T11:07:00Z"
}
```

### 4.2 `extract` request (review)

```json
{
  "url": "https://www.example-review.com/laptops/asus-g14-review",
  "schema": "review_v1",
  "locale": "en-US"
}
```

**Expected response (abridged)**

```json
{
  "schema_version": "review_v1",
  "url": "https://www.example-review.com/laptops/asus-g14-review",
  "domain": "example-review.com",
  "page_type": "review",
  "review": {
    "headline": "ASUS ROG Zephyrus G14 (2024) Review: Portable Power",
    "author": "Jane Doe",
    "published_at": "2025-05-11T00:00:00Z",
    "verdict_score": 9.0,
    "pros": ["Excellent performance", "Great battery life"],
    "cons": ["Runs warm under load"],
    "summary": "A compact powerhouse ideal for devs and creators.",
    "recommended_alternatives": ["Razer Blade 14"],
    "product_refs": ["ASUS ROG Zephyrus G14 (2024)"]
  },
  "content_hash": "sha256:def456...",
  "extracted_at": "2025-09-19T11:08:00Z"
}
```

---

## 5) Persistence Mapping (Mongo)

* **`listings`** ← from `ecom_v1.offer` + `product`.

  * `source_type: "tavily"`, `url`, `domain`, `price`, `currency`, `availability`, `rating`, `review_count`, `promo_text`, `delivery_eta`, `content_hash`, `extracted_at`, `first_seen`, `last_seen`.

* **`products`** (canonical) ← `product` block after **Entity Resolver** merges brand/model/SKU & specs.

  * Update `specs` (coerced units), `aliases`, and embeddings.

* **`reviews`** ← from `review_v1.review`.

  * `domain`, `url`, `headline`, `published_at`, `verdict_score`, `pros`, `cons`, `summary`, `extracted_at`.

* **`sources`**

  * `{ url, domain, page_type, tavily_endpoint:"extract|crawl", credibility:{...}, product_id?, related_ids:[], captured_at }`

* **`runs.steps`**

  * `{ node:"Retriever/Tavily", urls_considered:n, endpoint_mix:{extract:x,crawl:y}, time_ms }`

---

## 6) Validation & Unit Coercion

* **Normalize units**:

  * RAM/storage to **GB**, battery to **Wh** (or **mAh** for phones, keep both fields), screen to **inches**, weight to **kg**, refresh to **Hz**.
* **Currency**: 3-letter ISO (EUR, USD, GBP).
* **Null policy**: absent or unknown -> `null` (never invent).
* **Date parsing**: ISO-8601.
* **Sanity checks** (drop outliers unless confirmed by ≥2 sources):

  * Laptop RAM in \[4, 128], battery\_wh in \[30, 120], weight\_kg in \[0.7, 3.5].
* **Coverage flag**: add transient `low_coverage: true` in processing step (not stored) to trigger fallback.

---

## 7) Credibility Score (post-extraction)

```
cred.final = 0.4*domain_rep
           + 0.2*recency
           + 0.2*extractability
           + 0.1*consensus
           - 0.05*affiliate_penalty
           - 0.05*dup_domain_penalty
```

* **domain\_rep**: curated map (Wirecutter 0.95, CNET 0.9, TechRadar 0.85, Amazon PDP 0.75, random blog 0.3).
* **recency**: 1.0 if <30 days, linear decay to 0.2 after 18 months.
* **extractability**: proportion of required fields present.
* **consensus**: +0.05 if multiple credible sources agree on key specs/price.
* **affiliate\_penalty**: −0.1 for heavy affiliate templates.
* **dup\_domain\_penalty**: cap 2–3 pages/domain.

Store the expanded breakdown in **`sources.credibility`**.

---

## 8) Fallback via `crawl` + LLM

If `extract` fails or coverage < 0.60:

1. `crawl(url)` to get cleaned HTML/text.
2. Run LLM extraction (prompted to emit `ecom_v1` or `review_v1`).
3. **Merge** with any partial `extract` data.
4. Re-compute **coverage** and **credibility**.

---

## 9) Regionalization

* Prefer localized domains (e.g., `.de`, `.co.uk`) given user region.
* Keep both **raw price** and **normalized price** (store rate used; normalization happens in app layer when ranking/displaying).
* For VAT differences, annotate `region` in `listings`.

---

## 10) Versioning & Change Management

* **Schema versions** (`schema_version`): `ecom_v1`, `review_v1`.
* When updating fields, create `ecom_v2`/`review_v2`, don’t break old data.
* Keep a **CHANGELOG**:

```
## 2025-09-19
- Add `battery_mah` to ecom specs for phones
- Tighten coverage rule: require 3+ spec fields for laptops/phones/cameras
```

* Add a **schema registry** module in code (`app/extractors/schemas.py`) exporting Pydantic models for validation.

---

## 11) Quick Dev Checklist

* [ ] Implement `extract_ecom(url)` and `extract_review(url)` wrappers.
* [ ] Validate payloads against the JSON schemas (Pydantic).
* [ ] Unit tests with **golden URLs** (per domain).
* [ ] Coverage computation + fallback path to `crawl`.
* [ ] Persistence mapping to `listings`, `products`, `reviews`, `sources`.
* [ ] Credibility scoring + domain cap.
* [ ] Logs: endpoint timing, coverage %, failures by domain.

