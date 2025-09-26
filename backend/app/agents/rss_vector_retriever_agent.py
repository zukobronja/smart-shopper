"""RSS vector retrieval agent."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.agents.state import (
    SmartShopperAgent,
    SmartShopperWorkflowState,
    add_agent_step,
)
from app.config import settings
from app.db.client import mongo_client
from app.rss.embedding_provider import RSSEmbeddingProvider


class RSSVectorRetrieverAgent(SmartShopperAgent):
    name = "RSS Vector Retriever"
    color = SmartShopperAgent.ORANGE

    def __init__(
        self,
        max_results: int = 10,
        freshness_days: int = 14,
        embedding_provider: Optional[RSSEmbeddingProvider] = None,
    ):
        super().__init__()
        self.max_results = max_results
        self.freshness_days = freshness_days
        self._embedding_provider = embedding_provider or RSSEmbeddingProvider()
        self.log(f"Initialized RSSVectorRetrieverAgent with max_results={max_results}, "
                 f"freshness_days={freshness_days}, embeddings_provider={settings.EMBEDDINGS_PROVIDER}")

    async def process(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        start_time = datetime.now(timezone.utc)
        state.setdefault("rss_results", [])

        try:
            query_text = self._extract_query_text(state)
            if not query_text:
                self._record_step(state, start_time, "skipped", 0, "Missing query text")
                return state

            embeddings = await self._embedding_provider.embed_texts([query_text])
            query_vector = self._select_query_vector(embeddings)
            if query_vector is None:
                self._record_step(state, start_time, "skipped", 0, "No embeddings available")
                return state

            pipeline = self._build_pipeline(query_vector)
            results = await self._run_vector_search(pipeline)
            state["rss_results"] = results

            self._record_step(state, start_time, "success", len(results))
            return state
        except Exception as exc:  # pylint: disable=broad-except
            self.log(f"Error retrieving RSS items: {exc}")
            state["rss_results"] = []
            self._record_step(state, start_time, "error", 0, str(exc))
            return state

    def _extract_query_text(self, state: SmartShopperWorkflowState) -> str:
        """
        Extract query text for RSS vector search.
        Use raw query to preserve budget constraints and full user intent.
        """
        # Use raw query to preserve budget constraints and modifiers
        raw_query = state.get("raw_query", "").strip()
        if raw_query:
            return raw_query
        
        # Fallback to normalized query if raw query unavailable
        search_query = state.get("search_query")
        if search_query and getattr(search_query, "normalized_query", None):
            return search_query.normalized_query
        
        return ""

    def _select_query_vector(self, embeddings: Dict[str, List[List[float]]]) -> Optional[List[float]]:
        if settings.EMBEDDINGS_PROVIDER == "openai":
            vectors = embeddings.get("openai") or embeddings.get("minilm")
        else:
            vectors = embeddings.get("minilm") or embeddings.get("openai")
        if not vectors:
            return None
        return vectors[0]

    def _build_pipeline(self, query_vector: List[float]) -> List[Dict[str, Any]]:
        vector_field = (
            "summary_vec_openai_1536"
            if settings.EMBEDDINGS_PROVIDER == "openai"
            else "summary_vec_minilm_384"
        )
        index_name = (
            "rss_summary_openai_idx"
            if settings.EMBEDDINGS_PROVIDER == "openai"
            else "rss_summary_minilm_idx"
        )
        recency_cutoff = datetime.now(timezone.utc) - timedelta(days=self.freshness_days)
        
        # Increase candidates for better semantic relevance
        num_candidates = max(200, self.max_results * 10)
        vector_limit = self.max_results * 3  # Get more results for filtering

        pipeline: List[Dict[str, Any]] = [
            {
                "$vectorSearch": {
                    "index": index_name,
                    "path": vector_field,
                    "queryVector": query_vector,
                    "numCandidates": num_candidates,
                    "limit": vector_limit,
                }
            },
            {
                "$match": {
                    "published_at": {"$gte": recency_cutoff},
                    # Add minimum relevance threshold
                    "$expr": {"$gte": [{"$meta": "vectorSearchScore"}, 0.7]}
                }
            },
            {
                "$project": {
                    "title": 1,
                    "summary": 1,
                    "link": 1,
                    "source_domain": 1,
                    "feed_url": 1,
                    "feed_id": 1,
                    "published_at": 1,
                    "price_amount": 1,
                    "price_currency": 1,
                    "tags": 1,
                    "categories": 1,
                    "_score": {"$meta": "vectorSearchScore"},
                }
            },
            # Additional semantic relevance filtering
            {
                "$sort": {"_score": -1}
            },
            {
                "$limit": self.max_results
            }
        ]
        return pipeline

    async def _run_vector_search(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        collection = mongo_client.database.rss_items
        try:
            cursor = await collection.aggregate(pipeline)
            results: List[Dict[str, Any]] = []
            async for doc in cursor:
                results.append(self._normalize_result(doc))
                if len(results) >= self.max_results:
                    break
            return results
        except Exception as e:
            # Vector search failed - gracefully degrade
            self.log(f"Vector search failed: {e}")
            self.log("Skipping RSS results - using Tavily-only pipeline")
            return []

    def _normalize_result(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": doc.get("title"),
            "summary": doc.get("summary"),
            "link": doc.get("link"),
            "source_domain": doc.get("source_domain"),
            "feed_url": doc.get("feed_url"),
            "feed_id": str(doc.get("feed_id")) if doc.get("feed_id") else None,
            "published_at": doc.get("published_at"),
            "score": doc.get("_score"),
            "price": {
                "amount": doc.get("price_amount"),
                "currency": doc.get("price_currency"),
            },
            "tags": doc.get("tags", []),
            "categories": doc.get("categories", []),
        }

    def _record_step(
        self,
        state: SmartShopperWorkflowState,
        start_time: datetime,
        status: str,
        items_processed: int,
        error_message: Optional[str] = None,
    ) -> None:
        execution_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        add_agent_step(
            state,
            self.name,
            status,
            execution_time,
            items_processed=items_processed,
            cost_usd=0.0,
            error_message=error_message,
        )
