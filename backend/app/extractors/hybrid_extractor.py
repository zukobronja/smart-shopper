"""
Hybrid extraction system: Tavily (preferred) + LLM fallback (when coverage is low)
Implements the coverage-based fallback strategy from TAVILY_EXPLORATION.md
"""
from typing import Dict, Any, List, Optional, Tuple
import logging
from app.extractors.tavily_client import SmartShopperTavilyClient
from app.extractors.llm_extractor import LLMExtractor
from app.extractors.schemas import SchemaValidator, EcomV1, ReviewV1
from app.extractors.credibility_scorer import CredibilityScorer

logger = logging.getLogger(__name__)

class HybridExtractor:
    """
    Hybrid extraction system implementing coverage-based fallback strategy
    
    Strategy:
    1. Try Tavily extract first (preferred - cheaper, faster)
    2. Validate schema and compute coverage
    3. If coverage < 0.60, try LLM fallback on raw crawl content
    4. Merge results intelligently
    """
    
    def __init__(self, tavily_api_key: Optional[str] = None, openai_api_key: Optional[str] = None):
        self.tavily_client = SmartShopperTavilyClient(api_key=tavily_api_key)
        self.llm_extractor = LLMExtractor(api_key=openai_api_key)
        self.schema_validator = SchemaValidator()
        self.credibility_scorer = CredibilityScorer()
        
        # Coverage threshold from TAVILY_EXPLORATION.md
        self.coverage_threshold = 0.60
        
    def extract_product_data(
        self,
        urls: List[str],
        schema_type: str = "ecom_v1"
    ) -> List[Dict[str, Any]]:
        """
        Extract product data with hybrid approach
        
        Args:
            urls: List of URLs to extract from
            schema_type: "ecom_v1" or "review_v1"
            
        Returns:
            List of extracted and validated data objects
        """
        results = []
        
        for url in urls:
            try:
                result = self._extract_single_url(url, schema_type)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Failed to extract from {url}: {e}")
                continue
        
        return results
    
    def _extract_single_url(self, url: str, schema_type: str) -> Optional[Dict[str, Any]]:
        """Extract data from a single URL with fallback strategy"""
        
        logger.info(f"Starting hybrid extraction for {url}")
        
        # Step 1: Try Tavily extract first
        tavily_result = self._try_tavily_extract(url)
        
        if tavily_result:
            # Step 2: Validate and check coverage
            try:
                if schema_type == "ecom_v1":
                    model, coverage, is_low_coverage = self.schema_validator.validate_ecom(tavily_result)
                elif schema_type == "review_v1":
                    model, coverage, is_low_coverage = self.schema_validator.validate_review(tavily_result)
                else:
                    raise ValueError(f"Unknown schema type: {schema_type}")
                
                logger.info(f"Tavily extraction coverage: {coverage:.2f}")
                
                # Step 3: If coverage is good, return Tavily result
                if not is_low_coverage:
                    logger.info(f"Good coverage from Tavily, using direct result")
                    result = model.model_dump()
                    
                    # Add credibility score
                    credibility = self.credibility_scorer.score_source(
                        url, result, {"coverage": coverage}
                    )
                    result["credibility_score"] = credibility
                    
                    return result
                
                # Step 4: Coverage is low, try LLM fallback
                logger.info(f"Low coverage ({coverage:.2f}), trying LLM fallback")
                
            except Exception as e:
                logger.warning(f"Tavily schema validation failed: {e}, trying LLM fallback")
                tavily_result = None
        
        # Step 5: LLM fallback (either because Tavily failed or low coverage)
        llm_result = self._try_llm_fallback(url, schema_type)
        
        if not llm_result:
            logger.error(f"Both Tavily and LLM extraction failed for {url}")
            return None
        
        # Step 6: If we have both results, merge them
        if tavily_result and llm_result:
            logger.info("Merging Tavily and LLM results")
            merged_result = self.llm_extractor.merge_extractions(
                tavily_result, llm_result, schema_type
            )
            
            # Validate merged result
            try:
                if schema_type == "ecom_v1":
                    model, coverage, is_low_coverage = self.schema_validator.validate_ecom(merged_result)
                else:
                    model, coverage, is_low_coverage = self.schema_validator.validate_review(merged_result)
                
                logger.info(f"Merged result coverage: {coverage:.2f}")
                result = model.model_dump()
                
                # Add credibility score for merged result
                credibility = self.credibility_scorer.score_source(
                    url, result, {"coverage": coverage, "merged": True}
                )
                result["credibility_score"] = credibility
                
                return result
                
            except Exception as e:
                logger.error(f"Merged result validation failed: {e}")
                return llm_result
        
        # Step 7: Only LLM result available
        try:
            if schema_type == "ecom_v1":
                model, coverage, is_low_coverage = self.schema_validator.validate_ecom(llm_result)
            else:
                model, coverage, is_low_coverage = self.schema_validator.validate_review(llm_result)
            
            logger.info(f"LLM-only result coverage: {coverage:.2f}")
            result = model.model_dump()
            
            # Add credibility score for LLM-only result
            credibility = self.credibility_scorer.score_source(
                url, result, {"coverage": coverage, "llm_only": True}
            )
            result["credibility_score"] = credibility
            
            return result
            
        except Exception as e:
            logger.error(f"LLM result validation failed: {e}")
            return llm_result  # Return raw LLM result as last resort
    
    def _try_tavily_extract(self, url: str) -> Optional[Dict[str, Any]]:
        """Try Tavily structured extraction"""
        try:
            logger.info(f"Trying Tavily extract for {url}")
            
            # Use Tavily's extract method for structured data
            results = self.tavily_client.extract_structured([url])
            
            if results and len(results) > 0:
                result = results[0]
                logger.info(f"Tavily extract returned data for {url}")
                return result
            else:
                logger.info(f"Tavily extract returned no results for {url}")
                return None
                
        except Exception as e:
            logger.warning(f"Tavily extract failed for {url}: {e}")
            return None
    
    def _try_llm_fallback(self, url: str, schema_type: str) -> Optional[Dict[str, Any]]:
        """Try LLM extraction on crawled content"""
        try:
            logger.info(f"Trying LLM fallback for {url}")
            
            # First crawl the URL to get raw content
            domain = self.tavily_client._extract_domain(url)
            crawl_result = self.tavily_client.crawl_fallback(url)
            
            if not crawl_result or not crawl_result.get("raw_content"):
                logger.warning(f"Failed to crawl content for {url}")
                return None
            
            raw_content = crawl_result["raw_content"]
            logger.info(f"Crawled {len(raw_content)} characters from {url}")
            
            # Extract using LLM
            if schema_type == "ecom_v1":
                result = self.llm_extractor.extract_ecom_fallback(
                    content=raw_content,
                    url=url,
                    domain=domain
                )
            elif schema_type == "review_v1":
                result = self.llm_extractor.extract_review_fallback(
                    content=raw_content,
                    url=url,
                    domain=domain
                )
            else:
                logger.error(f"Unknown schema type: {schema_type}")
                return None
            
            if result:
                logger.info(f"LLM extraction successful for {url}")
                return result
            else:
                logger.warning(f"LLM extraction failed for {url}")
                return None
                
        except Exception as e:
            logger.error(f"LLM fallback failed for {url}: {e}")
            return None
    
    def extract_and_rank_by_credibility(
        self,
        urls: List[str],
        schema_type: str = "ecom_v1"
    ) -> List[Dict[str, Any]]:
        """
        Extract data from URLs and return ranked by credibility score
        
        Args:
            urls: List of URLs to extract from
            schema_type: "ecom_v1" or "review_v1"
            
        Returns:
            List of extracted data ranked by credibility (highest first)
        """
        # Extract data from all URLs
        results = self.extract_product_data(urls, schema_type)
        
        if not results:
            return []
        
        # Sort by credibility score (highest first)
        ranked_results = sorted(
            results,
            key=lambda x: x.get("credibility_score", {}).get("overall_score", 0.0),
            reverse=True
        )
        
        logger.info(f"Ranked {len(ranked_results)} results by credibility")
        if ranked_results:
            top_score = ranked_results[0].get("credibility_score", {}).get("overall_score", 0.0)
            logger.info(f"Top credibility score: {top_score:.3f}")
        
        return ranked_results
    
    def get_extraction_stats(self) -> Dict[str, Any]:
        """Get statistics about extraction performance"""
        # This could be enhanced to track success rates, coverage distributions, etc.
        return {
            "coverage_threshold": self.coverage_threshold,
            "extraction_methods": ["tavily_extract", "llm_fallback"],
            "merge_strategy": "intelligent_field_selection",
            "credibility_scoring": self.credibility_scorer.get_scoring_summary()
        }