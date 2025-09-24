"""
CredibilityFilterAgent for SmartShopper Pipeline

Filters and scores search results by source credibility using multi-factor analysis:
- Domain Reputation (50%): Authority and trustworthiness of the source domain
- Recency Score (30%): Content freshness with exponential decay  
- Extractability (20%): Quality of data extraction from Tavily

Architecture Position: TavilyRetriever → CredibilityFilter → SpecExtractor
"""
import re
import math
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

from app.agents.state import SmartShopperAgent, SmartShopperWorkflowState, add_agent_step
from app.extractors.domain_config import get_domain_quality_score


class CredibilityFilterAgent(SmartShopperAgent):
    """
    Filters and scores search results by source credibility
    
    Scoring Algorithm:
    final_score = 0.5 * domain_reputation + 0.3 * recency + 0.2 * extractability
    
    Intent-Aware Weighting:
    - product_search: Emphasizes domain reputation (e-commerce authority)
    - review_search: Emphasizes recency + domain (fresh reviews from trusted sources)  
    - comparison: Emphasizes extractability (structured comparison data)
    """
    
    name = "Credibility Filter"
    color = SmartShopperAgent.CYAN
    
    def __init__(self):
        super().__init__()
        self.credibility_threshold = 0.4
        self.fallback_thresholds = [0.3, 0.2, 0.1]  # Progressive fallback
        self.min_results_fallback = 3
        
        # Intent-based weight adjustments
        self.intent_weights = {
            "product_search": {"domain": 0.6, "recency": 0.25, "extractability": 0.15},
            "review_search": {"domain": 0.45, "recency": 0.35, "extractability": 0.20}, 
            "comparison": {"domain": 0.4, "recency": 0.25, "extractability": 0.35},
            "general": {"domain": 0.5, "recency": 0.3, "extractability": 0.2}  # Default
        }
        self.log("Initialized CredibilityFilterAgent")
    
    async def process(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """
        Main processing method for credibility filtering
        """
        start_time = datetime.now()
        self.log("Starting credibility filtering and scoring")
        
        try:
            # Extract input data
            raw_search_results = state.get("raw_search_results", [])
            extracted_content = state.get("extracted_content", [])
            search_query = state.get("search_query")
            
            if not raw_search_results:
                self.log("No search results to filter")
                state["credibility_filtered_results"] = []
                return self._record_execution(state, start_time, 0, "success")
            
            intent = search_query.intent if search_query else "general"
            self.log(f"Processing {len(raw_search_results)} results for intent: {intent}")
            
            # Score and filter results
            scored_results = await self._score_results(raw_search_results, extracted_content, intent)
            filtered_results = self._apply_filtering(scored_results, intent)
            
            # Update state
            state["credibility_filtered_results"] = filtered_results
            
            # Log results
            passed_count = len(filtered_results)
            avg_score = sum(r.get("credibility_score", 0) for r in filtered_results) / max(passed_count, 1)
            self.log(f"Filtered to {passed_count} results (avg score: {avg_score:.3f})")
            
            return self._record_execution(state, start_time, passed_count, "success")
            
        except Exception as e:
            self.log(f"Error in credibility filtering: {e}")
            # Graceful degradation - pass through original results
            state["credibility_filtered_results"] = state.get("raw_search_results", [])
            return self._record_execution(state, start_time, 0, "error", str(e))
    
    async def _score_results(
        self, 
        search_results: List[Dict[str, Any]], 
        extracted_content: List[Dict[str, Any]],
        intent: str
    ) -> List[Dict[str, Any]]:
        """
        Score each result using multi-factor credibility analysis
        """
        # Create lookup for extracted content by URL
        extraction_lookup = {item.get("url", ""): item for item in extracted_content}
        
        scored_results = []
        weights = self.intent_weights.get(intent, self.intent_weights["general"])
        
        for result in search_results:
            url = result.get("url", "")
            
            # Calculate individual scores
            domain_score = self._calculate_domain_score(url)
            recency_score = self._calculate_recency_score(result)
            extractability_score = self._calculate_extractability_score(url, extraction_lookup)
            
            # Calculate weighted final score
            final_score = (
                weights["domain"] * domain_score +
                weights["recency"] * recency_score + 
                weights["extractability"] * extractability_score
            )
            
            # Add credibility metadata to result
            enhanced_result = {
                **result,
                "credibility_score": round(final_score, 3),
                "credibility_breakdown": {
                    "domain_score": round(domain_score, 3),
                    "recency_score": round(recency_score, 3), 
                    "extractability_score": round(extractability_score, 3),
                    "weights_used": weights,
                    "intent": intent
                }
            }
            
            scored_results.append(enhanced_result)
        
        # Sort by credibility score (highest first)
        scored_results.sort(key=lambda x: x["credibility_score"], reverse=True)
        return scored_results
    
    def _calculate_domain_score(self, url: str) -> float:
        """Calculate domain reputation score"""
        if not url:
            return 0.0
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            domain = domain.replace("www.", "")
            return get_domain_quality_score(domain)
        except Exception:
            return 0.3  # Very low score for malformed URLs
    
    def _calculate_recency_score(self, result: Dict[str, Any]) -> float:
        """
        Calculate recency score with exponential decay
        1.0 for content <30 days, exponential decay to 0.2 for older content
        """
        publication_date = self._extract_publication_date(result)
        
        if not publication_date:
            return 0.7  # Default score when date unavailable
        
        # Calculate days since publication
        days_old = (datetime.now(timezone.utc) - publication_date).days
        
        if days_old < 0:
            return 1.0  # Future dates get full score
        elif days_old <= 30:
            return 1.0  # Full score for recent content
        elif days_old <= 365:
            # Exponential decay from 1.0 to 0.2 over 365 days
            decay_factor = math.exp(-days_old / 150)  # Adjust 150 for decay rate
            return max(0.2, decay_factor)
        else:
            return 0.2  # Minimum score for very old content
    
    def _extract_publication_date(self, result: Dict[str, Any]) -> Optional[datetime]:
        """
        Extract publication date from multiple sources
        """
        # Try published_date field first (Tavily standard)
        if "published_date" in result:
            return self._parse_date_string(result["published_date"])
        
        # Try other common date fields
        date_fields = ["date", "timestamp", "pubDate", "created_at", "updated_at"]
        for field in date_fields:
            if field in result and result[field]:
                parsed_date = self._parse_date_string(result[field])
                if parsed_date:
                    return parsed_date
        
        # Try extracting date from URL patterns
        url = result.get("url", "")
        if url:
            url_date = self._extract_date_from_url(url)
            if url_date:
                return url_date
        
        return None
    
    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Parse date string using multiple formats"""
        if not date_str:
            return None
        
        # Common date formats
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",      # ISO format with timezone
            "%Y-%m-%dT%H:%M:%SZ",       # ISO format UTC
            "%Y-%m-%d %H:%M:%S",        # Standard format
            "%Y-%m-%d",                 # Date only
            "%d/%m/%Y",                 # EU format
            "%m/%d/%Y",                 # US format
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                # Add UTC timezone if naive
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        
        return None
    
    def _extract_date_from_url(self, url: str) -> Optional[datetime]:
        """Extract date from URL patterns like /2024/01/15/ or /blog/2024-01-15"""
        try:
            # Pattern for YYYY/MM/DD or YYYY-MM-DD in URLs
            date_pattern = r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})'
            match = re.search(date_pattern, url)
            
            if match:
                year, month, day = map(int, match.groups())
                if 1 <= month <= 12 and 1 <= day <= 31:
                    return datetime(year, month, day, tzinfo=timezone.utc)
        except Exception:
            pass
        
        return None
    
    def _calculate_extractability_score(
        self, 
        url: str, 
        extraction_lookup: Dict[str, Dict[str, Any]]
    ) -> float:
        """
        Calculate extractability score based on Tavily extraction success
        """
        extracted_data = extraction_lookup.get(url, {})
        
        if not extracted_data:
            return 0.3  # Low score if no extraction attempted
        
        # Get content from extracted data
        content = extracted_data.get("content", "")
        
        # If no content in extraction, try to get it from other fields
        if not content or content.strip() in ["", "No content"]:
            # Try alternative content sources
            content = extracted_data.get("text", "") or extracted_data.get("description", "")
        
        # Still no useful content
        if not content or content.strip() in ["", "No content"]:
            # Debug logging
            domain = urlparse(url).netloc if url else "unknown"
            self.log(f"Low extractability for {domain}: content='{content[:50] if content else 'None'}'")
            return 0.1  # Very low score for failed extraction
        
        # Start with base score for having content
        score = 0.4  # Increased base score
        
        # Content length scoring (more granular)
        content_length = len(content.strip())
        if content_length > 500:
            score += 0.3  # Substantial content
        elif content_length > 200:
            score += 0.2  # Moderate content  
        elif content_length > 50:
            score += 0.1  # Some content
        # else: no bonus for very short content
        
        # Boost for structured content indicators
        content_lower = content.lower()
        structured_indicators = [
            "price", "$", "€", "£", "specifications", "features",
            "model", "brand", "review", "rating", "specs", "gb", "ram",
            "cpu", "processor", "storage", "display", "screen", "battery"
        ]
        
        found_indicators = sum(1 for indicator in structured_indicators 
                             if indicator in content_lower)
        
        # Add bonus based on structured content (improved scoring)
        if found_indicators >= 5:
            score += 0.3  # Rich structured content
        elif found_indicators >= 3:
            score += 0.2  # Good structured content
        elif found_indicators >= 1:
            score += 0.1  # Some structured content
        
        return min(1.0, score)
    
    def _apply_filtering(self, scored_results: List[Dict[str, Any]], intent: str) -> List[Dict[str, Any]]:
        """
        Apply credibility filtering with intelligent fallback
        
        Args:
            scored_results: Results with credibility scores
            intent: Search intent (for future intent-specific filtering)
        """
        # Try primary threshold first
        filtered = [r for r in scored_results if r["credibility_score"] >= self.credibility_threshold]
        
        if filtered:
            self.log(f"Passed primary filter (≥{self.credibility_threshold}): {len(filtered)} results")
            return filtered
        
        # Progressive fallback with lower thresholds
        for fallback_threshold in self.fallback_thresholds:
            fallback_filtered = [r for r in scored_results if r["credibility_score"] >= fallback_threshold]
            
            if fallback_filtered:
                # Limit to top N results in fallback mode
                fallback_results = fallback_filtered[:self.min_results_fallback]
                self.log(f"Applied fallback filter (≥{fallback_threshold}): {len(fallback_results)} results")
                
                # Add fallback warning to results
                for result in fallback_results:
                    result["credibility_warning"] = f"Below primary threshold ({self.credibility_threshold})"
                
                return fallback_results
        
        # Last resort: return top 3 results regardless of score
        if scored_results:
            emergency_results = scored_results[:self.min_results_fallback]
            self.log(f"Emergency fallback: returning top {len(emergency_results)} results")
            
            for result in emergency_results:
                result["credibility_warning"] = "Emergency fallback - very low credibility"
            
            return emergency_results
        
        # No results at all
        self.log("No results available after filtering")
        return []
    
    def _record_execution(
        self, 
        state: SmartShopperWorkflowState, 
        start_time: datetime, 
        items_processed: int, 
        status: str,
        error_message: str = None
    ) -> SmartShopperWorkflowState:
        """Record agent execution in state"""
        execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        add_agent_step(
            state,
            self.name,
            status,
            execution_time,
            items_processed=items_processed,
            error_message=error_message
        )
        
        return state


# Factory function for easy instantiation
def create_credibility_filter_agent() -> CredibilityFilterAgent:
    """Create CredibilityFilterAgent instance"""
    return CredibilityFilterAgent()