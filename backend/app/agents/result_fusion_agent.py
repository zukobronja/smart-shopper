"""Agent that merges Tavily structured products with RSS-adapted items."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.agents.state import (
    SmartShopperAgent,
    SmartShopperWorkflowState,
    add_agent_step,
)
import logging

logger = logging.getLogger(__name__)


class ResultFusionAgent(SmartShopperAgent):
    """Combine structured products from different retrieval branches."""

    name = "Result Fusion"
    color = SmartShopperAgent.GREEN

    async def process(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        start_time = datetime.now(timezone.utc)
        try:
            tavily_products = state.get("structured_products", []) or []
            rss_products = state.get("rss_structured_products", []) or []

            fused = self._merge_products(tavily_products, rss_products)
            state["structured_products"] = fused

            logger.info(
                "result_fusion_completed",
                extra={
                    "tavily_count": len(tavily_products),
                    "rss_count": len(rss_products),
                    "fused_count": len(fused),
                },
            )

            self._record_step(state, start_time, "success", len(fused))
            return state
        except Exception as exc:  # pylint: disable=broad-except
            self._record_step(state, start_time, "error", 0, str(exc))
            return state

    def _merge_products(
        self,
        tavily_products: List[Dict[str, Any]],
        rss_products: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not rss_products:
            return tavily_products
        if not tavily_products:
            return rss_products

        seen_keys = set()
        merged: List[Dict[str, Any]] = []

        for product in tavily_products + rss_products:
            key = (product.get("title"), product.get("source_url"))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append(product)

        return merged

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
