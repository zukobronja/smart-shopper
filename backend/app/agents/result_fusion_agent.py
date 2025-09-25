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

        # Filter RSS products for relevance before merging
        filtered_rss = self._filter_rss_for_relevance(rss_products, tavily_products)
        
        seen_keys = set()
        merged: List[Dict[str, Any]] = []

        # Prioritize Tavily results (more reliable for product searches)
        for product in tavily_products + filtered_rss:
            # Fix URL preservation: ensure URL field is properly set
            if not product.get("url") and product.get("source_url"):
                product["url"] = product["source_url"]
            elif not product.get("url") and product.get("link"):
                product["url"] = product["link"]
            
            key = (product.get("title"), product.get("source_url"))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append(product)

        logger.info(f"Fusion: {len(tavily_products)} Tavily + {len(filtered_rss)}/{len(rss_products)} RSS → {len(merged)} merged")
        return merged
    
    def _filter_rss_for_relevance(
        self, 
        rss_products: List[Dict[str, Any]], 
        tavily_products: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter RSS products to only include relevant items for product searches"""
        if not rss_products:
            return []
        
        # Extract product categories from Tavily results to understand search intent
        tavily_categories = set()
        for product in tavily_products:
            category = product.get("category", "")
            if category:
                tavily_categories.add(category.lower())
        
        filtered_rss = []
        for rss_product in rss_products:
            if self._is_rss_product_relevant(rss_product, tavily_categories):
                filtered_rss.append(rss_product)
            else:
                # Log filtered out items for debugging
                title = rss_product.get("title", "Unknown")[:50]
                logger.debug(f"Filtered out irrelevant RSS item: {title}...")
        
        logger.info(f"RSS relevance filter: {len(filtered_rss)}/{len(rss_products)} items kept")
        return filtered_rss
    
    def _is_rss_product_relevant(
        self, 
        rss_product: Dict[str, Any], 
        target_categories: set
    ) -> bool:
        """Check if an RSS product is relevant to the target product categories"""
        title = rss_product.get("title", "").lower()
        specs = rss_product.get("specs", {})
        category = rss_product.get("category", "").lower()
        
        # Get RSS categories and summary for analysis
        rss_categories = specs.get("categories", "").lower() if specs else ""
        rss_summary = specs.get("summary", "").lower() if specs else ""
        
        # If it's categorized as "deals" but not product-specific, it's likely irrelevant
        if "deals" in rss_categories and not any([
            # Check if it's actually a product deal, not just any random deal
            cat in (title + rss_summary) for cat in target_categories
        ]):
            # Check for common non-product deal patterns (expanded list)
            irrelevant_patterns = [
                "shoes", "clothing", "apparel", "desk", "furniture", "tablet", 
                "accessories", "storage", "external", "cable", "charger",
                "smartphone", "phone", "pixel", "iphone", "samsung", "mobile",
                "headphones", "earbuds", "watch", "fitness", "home", "kitchen"
            ]
            
            # If it contains irrelevant patterns and no target category, filter it out
            if any(pattern in (title + rss_summary) for pattern in irrelevant_patterns):
                if not any(cat in (title + rss_summary) for cat in target_categories):
                    return False
        
        # Additional strict filtering for gaming laptop searches
        if target_categories and "laptop" in str(target_categories):
            # Reject obvious non-laptop items
            non_laptop_patterns = [
                "smartphone", "phone", "pixel", "iphone", "5g", "trade-in", 
                "monthly bill", "credit", "plan", "carrier", "t-mobile", "verizon"
            ]
            if any(pattern in (title + rss_summary).lower() for pattern in non_laptop_patterns):
                return False
        
        # Keep if it matches target categories
        if target_categories and any(cat in (title + category + rss_categories + rss_summary) 
                                   for cat in target_categories):
            return True
        
        # Keep if it looks like a genuine product (has price and brand)
        if (rss_product.get("price") and rss_product.get("brand") and 
            not any(pattern in title for pattern in ["shipping", "gift card", "service"])):
            return True
        
        # Default: keep items that seem product-related
        product_indicators = [
            "laptop", "computer", "phone", "tablet", "gaming", "electronics",
            "processor", "memory", "storage", "display", "camera", "battery"
        ]
        
        return any(indicator in (title + rss_summary) for indicator in product_indicators)

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
