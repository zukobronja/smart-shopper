"""Adapter agent to normalize RSS vector results into structured products."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.agents.state import (
    SmartShopperAgent,
    SmartShopperWorkflowState,
    add_agent_step,
)


class RSSResultAdapterAgent(SmartShopperAgent):
    """Convert raw RSS vector hits into structured product-like entries."""

    name = "RSS Result Adapter"
    color = SmartShopperAgent.YELLOW

    async def process(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        start_time = datetime.now(timezone.utc)
        rss_results = state.get("rss_results", []) or []

        try:
            adapted_results = [self._adapt_result(item) for item in rss_results if item]
            state["rss_structured_products"] = adapted_results

            self._record_step(state, start_time, "success", len(adapted_results))
            return state
        except Exception as exc:  # pylint: disable=broad-except
            state["rss_structured_products"] = []
            self._record_step(state, start_time, "error", 0, str(exc))
            return state

    def _adapt_result(self, item: Dict[str, Any]) -> Dict[str, Any]:
        title = (item.get("title") or "").strip()
        summary = (item.get("summary") or "").strip()
        price_amount = item.get("price", {}).get("amount") if isinstance(item.get("price"), dict) else item.get("price_amount")
        price_currency = item.get("price", {}).get("currency") if isinstance(item.get("price"), dict) else item.get("price_currency")
        categories = item.get("categories") or []
        primary_category = categories[0] if categories else "general"

        specs = {}
        if summary:
            specs["summary"] = summary
        if categories:
            specs["categories"] = ", ".join(categories)
        tags = item.get("tags") or []
        if tags:
            specs["tags"] = ", ".join(tags)

        adapted = {
            "title": title,
            "brand": self._infer_brand(title),
            "price": price_amount,
            "currency": price_currency,
            "availability": None,
            "category": primary_category,
            "specs": specs,
            "source_url": item.get("link"),
            "source_domain": item.get("source_domain"),
            "extraction_coverage": 0.35 if specs else 0.2,
            "extraction_method": "rss_adapter",
            "images": [],
            "metadata": {
                "feed_url": item.get("feed_url"),
                "feed_id": item.get("feed_id"),
                "score": item.get("score"),
                "published_at": item.get("published_at"),
            },
        }
        return adapted

    def _infer_brand(self, title: str) -> Optional[str]:
        if not title:
            return None
        first_word = title.split()[0]
        if len(first_word) >= 3:
            return first_word
        return None

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
