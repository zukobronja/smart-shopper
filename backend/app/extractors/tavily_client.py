"""
Optimized Tavily API client following best practices for SmartShopper
Implements two-step process, async operations, and LangChain integration
"""
from typing import List, Dict, Any, Optional
import logging
import asyncio
from asyncio import Semaphore
from datetime import datetime, timezone
import re
from urllib.parse import urlparse

from tavily import AsyncTavilyClient
from langchain_tavily import TavilySearch, TavilyExtract
from pydantic import BaseModel

from app.config import settings
from app.extractors.domain_config import get_search_params_for_intent, get_domain_quality_score

logger = logging.getLogger(__name__)


class TavilyConfig(BaseModel):
    """Configuration for Tavily operations"""
    search_depth: str = "basic"  # "basic" for dev, "advanced" for prod
    max_results: int = 10  # Conservative default
    max_concurrent: int = 3  # Rate limiting
    enable_fallback: bool = False  # Skip crawl in dev
    extract_timeout_sec: int = 60  # Extraction timeout per batch
    fallback_timeout_sec: int = 30  # Crawl timeout for fallback
    fallback_max_depth: int = 1  # Depth for crawl fallback
    fallback_max_urls: int = 3  # Number of low-coverage URLs to crawl
    coverage_threshold: float = 0.60
    query_max_length: int = 400
    # Phase 2 enhancements
    enable_intent_optimization: bool = True  # Use intent-based parameters
    enable_quality_filter: bool = False  # Filter URLs by domain quality
    min_domain_quality: float = 0.6  # Minimum domain quality score
    # Phase 3 enhancements
    enable_map_api: bool = False  # Use Map API for site discovery
    map_max_depth: int = 2  # Map crawl depth
    map_max_results: int = 50  # Maximum URLs from Map API


class OptimizedTavilyClient:
    """Optimized Tavily client implementing best practices"""
    
    def __init__(self, api_key: Optional[str] = None, config: Optional[TavilyConfig] = None):
        self.api_key = api_key or settings.TAVILY_API_KEY
        if not self.api_key:
            raise ValueError("Tavily API key is required")
        
        # Use development config by default, can be overridden
        self.config = config or TavilyConfig()
        
        # Async client for raw API access
        self.async_client = AsyncTavilyClient(api_key=self.api_key)
        
        # LangChain tools for LangGraph integration  
        self.search_tool = TavilySearch(
            tavily_api_key=self.api_key,
            max_results=self.config.max_results,
            search_depth=self.config.search_depth,
            include_answer=False,
            include_raw_content=False
        )
        self.extract_tool = TavilyExtract(tavily_api_key=self.api_key)
        
        # Rate limiting
        self.semaphore = Semaphore(self.config.max_concurrent)
        
        logger.info(f"OptimizedTavilyClient initialized with config: {self.config}")
    
    def optimize_query(self, query: str, intent: str = "general") -> str:
        """
        Optimize query following Tavily best practices
        - Keep under 400 characters
        - Add intent-specific modifiers
        - Break complex queries into focused sub-queries
        """
        # Trim whitespace
        query = query.strip()
        
        # Handle empty queries
        if not query:
            return query
        
        # Add intent-specific modifiers
        if intent == "review_search":
            query = f"{query} review pros cons"
        elif intent == "product_search":
            query = f"{query} specs price buy"
        elif intent == "comparison":
            query = f"{query} vs comparison"
        
        # Check length and truncate if needed
        if len(query) > self.config.query_max_length:
            logger.warning(f"Query too long ({len(query)} chars), truncating")
            query = query[:self.config.query_max_length - 3] + "..."
        
        return query
    
    async def search_step(
        self,
        query: str,
        intent: str = "general",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        use_intent_optimization: bool = True
    ) -> Dict[str, Any]:
        """
        Step 1: Search for candidate URLs with intelligent optimization
        """
        optimized_query = self.optimize_query(query, intent)
        
        # Get intelligent search parameters based on intent
        if use_intent_optimization and self.config.enable_intent_optimization:
            search_params = get_search_params_for_intent(intent, query)
            # Override with config-specific values
            search_params["query"] = optimized_query
            search_params["max_results"] = self.config.max_results
            # Use config search_depth if not overridden by intent
            if "search_depth" not in search_params:
                search_params["search_depth"] = self.config.search_depth
        else:
            # Fallback to basic parameters (backwards compatibility)
            search_params = {
                "query": optimized_query,
                "max_results": self.config.max_results,
                "search_depth": self.config.search_depth,
                "include_answer": False,        # Don't waste credits on answers
                "include_raw_content": False,   # Get content via extract instead  
                "topic": self._get_topic_for_intent(intent),  # Specify topic
                "auto_parameters": True         # Let Tavily optimize
            }
        
        # Manual overrides take precedence over intent-based selection
        if include_domains:
            search_params["include_domains"] = include_domains
        if exclude_domains:
            search_params["exclude_domains"] = exclude_domains
        
        logger.info(f"Tavily search: '{optimized_query}' (params: {search_params})")
        
        try:
            async with self.semaphore:  # Rate limiting
                result = await self.async_client.search(**search_params)
            
            logger.info(f"Search returned {len(result.get('results', []))} results")
            return result
            
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            raise
    
    def _filter_urls_by_quality(self, urls: List[str], min_quality_score: float = 0.6) -> List[str]:
        """Filter URLs by domain quality to reduce costs"""
        if not urls:
            return []
        
        url_scores = []
        for url in urls:
            domain = self._extract_domain(url)
            quality_score = get_domain_quality_score(domain)
            url_scores.append((url, quality_score))
        
        # Sort by quality score (highest first)
        url_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Filter by minimum quality and log results
        filtered_urls = [url for url, score in url_scores if score >= min_quality_score]
        
        if len(filtered_urls) < len(urls):
            logger.info(f"URL quality filter: {len(filtered_urls)}/{len(urls)} URLs passed (min_score: {min_quality_score})")
        
        return filtered_urls

    async def extract_step(self, urls: List[str], enable_quality_filter: bool = False) -> List[Dict[str, Any]]:
        """
        Step 2: Extract structured data from URLs with optional quality filtering
        Uses optimized batch processing for improved performance and reduced API costs.
        """
        if not urls:
            return []
        
        # Apply quality filter if enabled
        if enable_quality_filter and self.config.enable_quality_filter:
            urls = self._filter_urls_by_quality(urls, self.config.min_domain_quality)
            if not urls:
                logger.warning("No URLs passed quality filter")
                return []
        
        logger.info(f"Extracting structured data from {len(urls)} URLs using optimized batch processing")
        
        # Use optimized batch processing (up to 20 URLs per batch)
        extracted_results = await self.batch_extract_optimized(urls)
        
        return extracted_results
    
    async def fallback_crawl_step(self, url: str) -> Dict[str, Any]:
        """
        Step 3: Fallback crawling for low-coverage extractions
        """
        if not self.config.enable_fallback:
            logger.info("Crawl fallback disabled in current config")
            return {"url": url, "method": "crawl_disabled", "success": False}
        
        logger.info(f"Crawl fallback for: {url}")
        
        try:
            async with self.semaphore:
                result = await self.async_client.crawl(
                    url=url,
                    max_depth=self.config.fallback_max_depth,
                    format="markdown",
                    timeout=self.config.fallback_timeout_sec
                )
            
            return {
                "url": url,
                "domain": self._extract_domain(url),
                "raw_content": result.get('content', ''),
                "method": "tavily_crawl",
                "crawled_at": datetime.now(timezone.utc).isoformat(),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Crawl failed for {url}: {e}")
            return {
                "url": url,
                "error": str(e),
                "method": "tavily_crawl",
                "success": False
            }
    
    async def two_step_process(
        self,
        query: str,
        intent: str = "general",
        max_fallback_urls: Optional[int] = None,
        **search_kwargs
    ) -> Dict[str, Any]:
        """
        Complete two-step process: search → extract → (optional crawl fallback)
        """
        # Step 1: Search
        search_results = await self.search_step(query, intent, **search_kwargs)
        
        # Extract URLs from search results
        urls = [result.get('url') for result in search_results.get('results', []) if result.get('url')]
        
        if not urls:
            logger.warning("No URLs found in search results")
            return {
                "search_results": search_results,
                "extracted_data": [],
                "fallback_data": [],
                "total_urls": 0
            }
        
        # Step 2: Extract (with optional quality filtering)
        extracted_data = await self.extract_step(urls, enable_quality_filter=True)
        
        # Step 3: Fallback for low coverage (if enabled)
        fallback_data = []
        if self.config.enable_fallback:
            fallback_limit = max_fallback_urls if max_fallback_urls is not None else self.config.fallback_max_urls
            low_coverage_urls = [
                item["url"] for item in extracted_data 
                if item.get("low_coverage", True) and item.get("success", False)
            ][:fallback_limit]  # Limit fallback URLs
            
            if low_coverage_urls:
                logger.info(f"Attempting fallback crawl for {len(low_coverage_urls)} low-coverage URLs")
                fallback_tasks = [self.fallback_crawl_step(url) for url in low_coverage_urls]
                fallback_data = await asyncio.gather(*fallback_tasks, return_exceptions=True)
        
        return {
            "search_results": search_results,
            "extracted_data": extracted_data,
            "fallback_data": fallback_data,
            "total_urls": len(urls),
            "config_used": self.config.model_dump()
        }
    
    # LangChain integration methods for LangGraph
    async def langchain_search(self, query: str, **kwargs) -> List[Dict]:
        """Search using LangChain wrapper for LangGraph compatibility"""
        try:
            optimized_query = self.optimize_query(query)
            results = await self.search_tool.ainvoke({"query": optimized_query, **kwargs})
            return results if isinstance(results, list) else [results]
        except Exception as e:
            logger.error(f"LangChain search failed: {e}")
            return []
    
    async def langchain_extract(self, url: str) -> Dict:
        """Extract using native Tavily client (more reliable than LangChain wrapper)"""
        try:
            # Use native async client instead of LangChain wrapper
            async with self.semaphore:
                result = await self.async_client.extract(
                    urls=[url],
                    extract_depth="advanced",
                    format="markdown"
                )
            
            # Extract content from result
            content = ""
            if result.get('results') and len(result['results']) > 0:
                content = result['results'][0].get('content', '')
            
            return {
                "url": url,
                "raw_content": content,
                "status": "success" if content else "failed",
                "method": "langchain_extract_native"
            }
        except Exception as e:
            logger.error(f"LangChain extract failed for {url}: {e}")
            return {
                "url": url,
                "raw_content": None,
                "status": "failed",
                "error": str(e),
                "method": "langchain_extract_native"
            }
    
    def _get_topic_for_intent(self, intent: str) -> str:
        """Get appropriate topic based on search intent"""
        intent_topic_map = {
            "product_search": "general",
            "review_search": "general", 
            "comparison": "general",
            "news_search": "news",
            "finance_search": "finance"
        }
        return intent_topic_map.get(intent, "general")
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return url
    
    def _calculate_coverage(self, extracted_data: Dict[str, Any]) -> float:
        """
        Calculate extraction coverage score
        This is a placeholder - real implementation will use schema validation
        """
        # Simple heuristic based on content length and structure
        content = extracted_data.get("raw_content", "")
        
        # Handle non-string content gracefully
        if not content or not isinstance(content, str):
            return 0.0
        
        # Basic scoring based on content indicators
        score = 0.0
        
        # Length score (capped at 0.4)
        length_score = min(len(content) / 2000, 0.4)  # Normalize to 2000 chars
        score += length_score
        
        # Structure indicators
        price_indicators = ["$", "€", "£", "price", "cost"] # TODO: support all currencies for global use
        if any(indicator in content.lower() for indicator in price_indicators):
            score += 0.3
        
        spec_indicators = ["specs", "specifications", "features", "ram", "cpu", "storage"]
        if any(indicator in content.lower() for indicator in spec_indicators):
            score += 0.3
        
        return min(score, 1.0)
    
    def triage_urls(
        self,
        search_results: Dict[str, Any],
        target_categories: List[str] = ["ecom", "review"]
    ) -> Dict[str, List[str]]:
        """
        Triage search results into categories (ecom vs review pages)
        Enhanced version with domain intelligence
        
        Args:
            search_results: Results from search_step()
            target_categories: Categories to look for
            
        Returns:
            Dict with categorized URLs
        """
        categorized = {category: [] for category in target_categories}
        
        for result in search_results.get('results', []):
            url = result.get('url', '')
            title = result.get('title', '').lower()
            snippet = result.get('content', '').lower()
            domain = self._extract_domain(url)
            
            # Enhanced categorization using domain intelligence
            from app.extractors.domain_config import TRUSTED_ECOM_DOMAINS, TRUSTED_REVIEW_DOMAINS
            
            # Domain-based categorization (high confidence)
            if any(ecom_domain in domain for ecom_domain in TRUSTED_ECOM_DOMAINS):
                categorized['ecom'].append(url)
                continue
            elif any(review_domain in domain for review_domain in TRUSTED_REVIEW_DOMAINS):
                categorized['review'].append(url)
                continue
            
            # Content-based categorization (fallback)
            ecom_indicators = ['buy', 'price', 'shop', 'store', 'purchase', 'cart', 'checkout']
            review_indicators = ['review', 'test', 'benchmark', 'comparison', 'vs', 'pros', 'cons', 'rating']
            
            text_content = f"{title} {snippet}".lower()
            
            if any(indicator in text_content for indicator in ecom_indicators):
                categorized['ecom'].append(url)
            elif any(indicator in text_content for indicator in review_indicators):
                categorized['review'].append(url)
        
        logger.info(f"Triaged URLs: {len(categorized['ecom'])} ecom, {len(categorized['review'])} review")
        return categorized
    
    async def map_discover_urls(
        self,
        domain: str,
        intent: str = "product_search",
        product_query: str = "",
        max_depth: Optional[int] = None,
        max_results: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Use Tavily Map API to discover URLs on a specific domain
        
        Args:
            domain: Domain to map (e.g., "amazon.com")
            intent: Search intent for targeted discovery
            product_query: Product-specific query for focused mapping
            max_depth: Map crawl depth (defaults to config)
            max_results: Maximum URLs to discover (defaults to config)
        
        Returns:
            List of discovered URLs with metadata
        """
        if not self.config.enable_map_api:
            logger.info("Map API disabled in configuration")
            return []
        
        depth = max_depth or self.config.map_max_depth
        limit = max_results or self.config.map_max_results
        
        logger.info(f"Map API discovery on {domain} (intent: {intent}, depth: {depth})")
        
        try:
            # Build instructions based on intent
            instructions = self._get_map_instructions(intent, product_query)
            
            # Get path patterns based on intent
            select_paths, exclude_paths = self._get_map_path_patterns(intent)
            
            async with self.semaphore:
                result = await self.async_client.map(
                    url=f"https://{domain}",
                    instructions=instructions,
                    max_depth=depth,
                    max_breadth=20,  # Conservative breadth
                    limit=limit,
                    select_paths=select_paths,
                    exclude_paths=exclude_paths
                )
            
            # Process discovered URLs
            urls = result.get('urls', [])
            discovered_urls = []
            
            for url in urls:
                url_data = {
                    "url": url,
                    "domain": domain,
                    "source": "tavily_map",
                    "method": "map_discovery",
                    "intent": intent,
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                    "map_metadata": {
                        "instructions": instructions,
                        "max_depth": depth,
                        "success": True
                    }
                }
                # Add domain quality score
                url_data["domain_quality_score"] = get_domain_quality_score(domain)
                discovered_urls.append(url_data)
            
            logger.info(f"Map API discovered {len(discovered_urls)} URLs on {domain}")
            return discovered_urls
            
        except Exception as e:
            logger.error(f"Map API failed for {domain}: {e}")
            return [{
                "url": f"https://{domain}",
                "domain": domain,
                "source": "tavily_map",
                "method": "map_discovery",
                "intent": intent,
                "error": str(e),
                "discovered_at": datetime.now(timezone.utc).isoformat(),
                "map_metadata": {
                    "success": False
                }
            }]
    
    def _get_map_instructions(self, intent: str, product_query: str = "") -> str:
        """Generate Map API instructions based on intent"""
        base_query = product_query if product_query else "products"
        
        instruction_templates = {
            "product_search": f"Find all {base_query} product pages, listings, and product detail pages",
            "review_search": f"Find all review pages, test articles, and evaluation content about {base_query}",
            "comparison": f"Find all comparison pages and vs articles related to {base_query}",
            "news_search": f"Find all news articles and announcements about {base_query}",
            "general": f"Find all relevant pages related to {base_query}"
        }
        
        return instruction_templates.get(intent, instruction_templates["general"])
    
    def _get_map_path_patterns(self, intent: str) -> tuple[List[str], List[str]]:
        """Get URL path patterns for Map API based on intent"""
        
        pattern_configs = {
            "product_search": {
                "select": [
                    r".*product.*", r".*item.*", r".*p/.*", r".*dp/.*", 
                    r".*buy.*", r".*shop.*", r".*catalog.*", r".*category.*"
                ],
                "exclude": [
                    r".*cart.*", r".*checkout.*", r".*account.*", r".*login.*",
                    r".*register.*", r".*help.*", r".*support.*", r".*contact.*"
                ]
            },
            "review_search": {
                "select": [
                    r".*review.*", r".*test.*", r".*article.*", r".*evaluation.*",
                    r".*comparison.*", r".*vs.*", r".*benchmark.*"
                ],
                "exclude": [
                    r".*comment.*", r".*forum.*", r".*user.*", r".*profile.*",
                    r".*social.*", r".*community.*"
                ]
            },
            "comparison": {
                "select": [
                    r".*comparison.*", r".*vs.*", r".*compare.*", r".*versus.*",
                    r".*best.*", r".*top.*", r".*review.*"
                ],
                "exclude": [
                    r".*product.*", r".*buy.*", r".*shop.*", r".*cart.*"
                ]
            },
            "news_search": {
                "select": [
                    r".*news.*", r".*announcement.*", r".*press.*", r".*blog.*",
                    r".*article.*", r".*update.*"
                ],
                "exclude": [
                    r".*product.*", r".*shop.*", r".*buy.*", r".*review.*"
                ]
            }
        }
        
        config = pattern_configs.get(intent, pattern_configs["product_search"])
        return config["select"], config["exclude"]
    
    async def enhanced_discovery_step(
        self,
        query: str,
        intent: str = "general",
        use_map_api: bool = True,
        target_domains: Optional[List[str]] = None,
        **search_kwargs
    ) -> Dict[str, Any]:
        """
        Enhanced discovery combining Search + Map APIs for comprehensive coverage
        
        Args:
            query: Search query
            intent: Search intent for optimization
            use_map_api: Whether to use Map API for domain discovery
            target_domains: Specific domains to map (optional)
            **search_kwargs: Additional search parameters
        
        Returns:
            Combined results from search and map discovery
        """
        logger.info(f"Enhanced discovery: '{query}' (intent: {intent}, map: {use_map_api})")
        
        all_results = {
            "search_results": {},
            "map_results": [],
            "total_search_urls": 0,
            "total_map_urls": 0,
            "combined_urls": [],
            "discovery_method": "enhanced" if use_map_api else "search_only"
        }
        
        # Step 1: Regular search discovery
        try:
            search_results = await self.search_step(query, intent, **search_kwargs)
            all_results["search_results"] = search_results
            
            search_urls = [
                result.get('url') for result in search_results.get('results', []) 
                if result.get('url')
            ]
            all_results["total_search_urls"] = len(search_urls)
            
            # Add search URLs to combined results
            for url in search_urls:
                all_results["combined_urls"].append({
                    "url": url,
                    "domain": self._extract_domain(url),
                    "source": "tavily_search",
                    "method": "search_discovery",
                    "intent": intent,
                    "discovered_at": datetime.now(timezone.utc).isoformat()
                })
            
        except Exception as e:
            logger.error(f"Search discovery failed: {e}")
            all_results["search_error"] = str(e)
        
        # Step 2: Map API discovery (if enabled)
        if use_map_api and self.config.enable_map_api:
            try:
                # Determine domains to map
                domains_to_map = target_domains or self._get_priority_domains_for_intent(intent)
                
                for domain in domains_to_map[:3]:  # Limit to 3 domains for cost control
                    map_results = await self.map_discover_urls(
                        domain=domain,
                        intent=intent,
                        product_query=query
                    )
                    
                    if map_results:
                        all_results["map_results"].extend(map_results)
                        # Add map URLs to combined results
                        for map_result in map_results:
                            if map_result.get("url") and not map_result.get("error"):
                                all_results["combined_urls"].append(map_result)
                
                all_results["total_map_urls"] = len([
                    r for r in all_results["map_results"] if not r.get("error")
                ])
                
            except Exception as e:
                logger.error(f"Map discovery failed: {e}")
                all_results["map_error"] = str(e)
        
        # Step 3: Deduplicate and sort combined URLs
        all_results["combined_urls"] = self._deduplicate_urls(all_results["combined_urls"])
        all_results["total_unique_urls"] = len(all_results["combined_urls"])
        
        logger.info(f"Enhanced discovery complete: {all_results['total_search_urls']} search + "
                   f"{all_results['total_map_urls']} map = {all_results['total_unique_urls']} unique URLs")
        
        return all_results
    
    def _get_priority_domains_for_intent(self, intent: str) -> List[str]:
        """Get priority domains for Map API based on intent"""
        from app.extractors.domain_config import get_domains_for_intent
        
        # Get top domains for the intent
        domains = get_domains_for_intent(intent)
        
        # Prioritize high-quality domains
        priority_domains = []
        high_quality = ["amazon.com", "bestbuy.com", "wirecutter.nytimes.com", "cnet.com"]
        
        # Add high-quality domains first
        for domain in high_quality:
            if domain in domains and domain not in priority_domains:
                priority_domains.append(domain)
        
        # Add remaining domains
        for domain in domains:
            if domain not in priority_domains:
                priority_domains.append(domain)
        
        return priority_domains[:5]  # Limit to top 5 for performance
    
    def _deduplicate_urls(self, url_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate URLs while preserving metadata"""
        seen_urls = set()
        unique_urls = []
        
        for url_data in url_list:
            url = url_data.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_urls.append(url_data)
        
        # Sort by domain quality score (if available) then by source preference
        def sort_key(item):
            quality_score = item.get("domain_quality_score", 0.5)
            source_priority = {"tavily_map": 3, "tavily_search": 2, "tavily_extract": 1}.get(
                item.get("source", ""), 0
            )
            return (quality_score, source_priority)
        
        unique_urls.sort(key=sort_key, reverse=True)
        return unique_urls
    
    async def batch_extract_optimized(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Extract content in optimal batches following Tavily recommendations
        - Max 20 URLs per request (Tavily limit)
        - Advanced extraction for better quality
        - Proper error handling and logging
        """
        if not urls:
            return []
        
        results = []
        batch_size = 20  # Tavily's maximum URLs per extract request
        
        logger.info(f"Starting optimized batch extraction for {len(urls)} URLs")
        
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(urls) + batch_size - 1) // batch_size
            
            try:
                logger.info(f"Processing batch {batch_num}/{total_batches}: {len(batch)} URLs")
                
                async with self.semaphore:
                    batch_result = await self.async_client.extract(
                        urls=batch,
                        extract_depth="advanced",  # Better quality extraction
                        format="markdown",
                        timeout=self.config.extract_timeout_sec
                    )
                
                batch_results = batch_result.get('results', [])
                
                # Process and validate each result
                for result in batch_results:
                    processed_result = self._process_extraction_result(result, batch_num)
                    if processed_result:
                        results.append(processed_result)
                
                logger.info(f"Batch {batch_num} completed: {len(batch_results)} results processed")
                
            except Exception as e:
                logger.error(f"Batch {batch_num} failed: {e}")
                # Add error placeholders for failed batch
                for url in batch:
                    results.append({
                        "url": url,
                        "domain": self._extract_domain(url),
                        "error": str(e),
                        "success": False,
                        "batch_number": batch_num,
                        "extraction_method": "batch_optimized"
                    })
        
        successful_extractions = len([r for r in results if r.get("success")])
        logger.info(f"Batch extraction complete: {successful_extractions}/{len(urls)} successful")
        
        return results
    
    def _process_extraction_result(self, result: Dict[str, Any], batch_num: int) -> Dict[str, Any]:
        """Process and enrich extraction result from batch"""
        url = result.get('url', '')
        if not url:
            return None
        
        domain = self._extract_domain(url)
        content = result.get('content', '')
        
        processed_result = {
            "url": url,
            "domain": domain,
            "raw_content": content,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "method": "batch_optimized",
            "batch_number": batch_num,
            "success": bool(content),
            "extraction_method": "tavily_extract_advanced"
        }
        
        # Calculate coverage and quality scores
        if content:
            coverage = self._calculate_coverage(processed_result)
            domain_quality = get_domain_quality_score(domain)
            
            processed_result.update({
                "coverage_score": coverage,
                "domain_quality_score": domain_quality,
                "low_coverage": coverage < self.config.coverage_threshold,
                "overall_quality_score": (coverage * 0.7) + (domain_quality * 0.3)
            })
        else:
            processed_result.update({
                "coverage_score": 0.0,
                "domain_quality_score": get_domain_quality_score(domain),
                "low_coverage": True,
                "overall_quality_score": get_domain_quality_score(domain) * 0.3
            })
        
        return processed_result
    
    def score_url_quality(self, url: str, metadata: Optional[Dict[str, Any]] = None) -> float:
        """
        Intelligent URL scoring for cost optimization
        
        Multi-factor scoring system:
        - Tavily relevance score (40%)
        - Domain reputation (30%) 
        - Content snippet relevance (20%)
        - URL structure quality (10%)
        
        Returns score between 0.0 and 1.0
        """
        if not metadata:
            metadata = {}
        
        score = 0.0
        
        # Factor 1: Tavily relevance score (40%)
        tavily_score = metadata.get('score', 0.5)
        if isinstance(tavily_score, (int, float)):
            score += tavily_score * 0.4
        else:
            score += 0.2  # Default if no score
        
        # Factor 2: Domain reputation (30%)
        domain_score = get_domain_quality_score(self._extract_domain(url))
        score += domain_score * 0.3
        
        # Factor 3: Content snippet relevance (20%)
        snippet_score = self._score_content_snippet(metadata.get('content', ''))
        score += snippet_score * 0.2
        
        # Factor 4: URL structure quality (10%)
        structure_score = self._score_url_structure(url)
        score += structure_score * 0.1
        
        return min(score, 1.0)
    
    def _score_content_snippet(self, content: str) -> float:
        """Score content snippet relevance for product searches"""
        if not content:
            return 0.3
        
        content_lower = content.lower()
        score = 0.3  # Base score
        
        # Positive indicators for product content
        product_indicators = [
            'product', 'price', 'buy', 'review', 'specs', 'features',
            'model', 'brand', 'rating', 'purchase', 'available'
        ]
        
        # Count positive indicators
        indicator_count = sum(1 for indicator in product_indicators if indicator in content_lower)
        score += min(indicator_count * 0.1, 0.5)  # Max 0.5 bonus
        
        # Negative indicators (spam, irrelevant content)
        negative_indicators = [
            'login', 'register', 'cart', 'checkout', 'account', 'privacy',
            'terms', 'error', '404', 'not found'
        ]
        
        # Reduce score for negative indicators
        negative_count = sum(1 for indicator in negative_indicators if indicator in content_lower)
        score -= negative_count * 0.2
        
        return max(0.0, min(score, 1.0))
    
    def _score_url_structure(self, url: str) -> float:
        """Score URL structure for product relevance"""
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            score = 0.5  # Base score
            
            # Positive URL patterns for products
            positive_patterns = [
                r'/product/', r'/item/', r'/p/', r'/dp/', 
                r'/buy/', r'/shop/', r'/catalog/', r'/detail/'
            ]
            
            for pattern in positive_patterns:
                if re.search(pattern, path):
                    score += 0.3
                    break
            
            # Negative URL patterns
            negative_patterns = [
                r'/cart/', r'/checkout/', r'/account/', r'/login/',
                r'/register/', r'/help/', r'/support/', r'/legal/'
            ]
            
            for pattern in negative_patterns:
                if re.search(pattern, path):
                    score -= 0.4
                    break
            
            # Bonus for clean product URLs
            if re.search(r'/[a-zA-Z0-9-]+$', path):  # Clean product slug
                score += 0.2
            
            return max(0.0, min(score, 1.0))
            
        except Exception:
            return 0.4  # Neutral score if parsing fails
    
    def filter_and_prioritize_urls(
        self,
        discovery_results: Dict[str, Any],
        max_extraction_urls: int = 15,
        min_quality_score: float = 0.4
    ) -> List[Dict[str, Any]]:
        """
        Intelligent URL filtering and prioritization for cost optimization
        
        Args:
            discovery_results: Results from enhanced_discovery_step()
            max_extraction_urls: Maximum URLs to extract (cost control)
            min_quality_score: Minimum quality threshold
        
        Returns:
            Filtered and ranked URLs ready for extraction
        """
        all_urls = discovery_results.get("combined_urls", [])
        
        if not all_urls:
            logger.warning("No URLs to filter from discovery results")
            return []
        
        # Score all URLs
        scored_urls = []
        for url_data in all_urls:
            url = url_data.get("url", "")
            if not url:
                continue
            
            # Create metadata for scoring
            metadata = {
                "score": url_data.get("tavily_score", 0.5),
                "content": url_data.get("content", ""),
                "title": url_data.get("title", ""),
                "source": url_data.get("source", "unknown")
            }
            
            # Calculate quality score
            quality_score = self.score_url_quality(url, metadata)
            
            # Apply minimum threshold
            if quality_score >= min_quality_score:
                url_data["quality_score"] = quality_score
                scored_urls.append(url_data)
        
        # Sort by quality score (descending)
        scored_urls.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
        
        # Apply maximum URL limit
        filtered_urls = scored_urls[:max_extraction_urls]
        
        logger.info(f"URL filtering: {len(all_urls)} → {len(scored_urls)} passed threshold → "
                   f"{len(filtered_urls)} selected for extraction")
        
        return filtered_urls
    
    async def optimized_three_step_process(
        self,
        query: str,
        intent: str = "general",
        max_extraction_urls: int = 15,
        min_quality_score: float = 0.4,
        **search_kwargs
    ) -> Dict[str, Any]:
        """
        Optimized three-step process with intelligent filtering:
        1. Enhanced Discovery (Search + Map API)
        2. Intelligent URL Filtering 
        3. Targeted Extraction
        
        Args:
            query: Search query
            intent: Search intent for optimization
            max_extraction_urls: Maximum URLs to extract (cost control)
            min_quality_score: Minimum quality threshold for URLs
            **search_kwargs: Additional search parameters
        
        Returns:
            Complete results with optimization metrics
        """
        logger.info(f"Optimized three-step process: '{query}' (intent: {intent})")
        
        # Step 1: Enhanced Discovery
        discovery_results = await self.enhanced_discovery_step(
            query=query,
            intent=intent,
            **search_kwargs
        )
        
        # Step 2: Intelligent URL Filtering
        filtered_urls = self.filter_and_prioritize_urls(
            discovery_results=discovery_results,
            max_extraction_urls=max_extraction_urls,
            min_quality_score=min_quality_score
        )
        
        # Step 3: Targeted Extraction (only on filtered URLs)
        extraction_urls = [url_data["url"] for url_data in filtered_urls]
        extracted_data = await self.extract_step(extraction_urls, enable_quality_filter=False)
        
        # Merge filtering metadata with extraction results
        for extracted_item in extracted_data:
            extracted_url = extracted_item.get("url", "")
            # Find corresponding filtered URL data
            for filtered_item in filtered_urls:
                if filtered_item["url"] == extracted_url:
                    extracted_item["filtering_metadata"] = {
                        "quality_score": filtered_item.get("quality_score", 0),
                        "discovery_source": filtered_item.get("source", "unknown"),
                        "filtered_rank": filtered_urls.index(filtered_item) + 1
                    }
                    break
        
        # Calculate optimization metrics
        optimization_metrics = self._calculate_optimization_metrics(
            discovery_results, filtered_urls, extracted_data
        )
        
        # Step 4: Optional fallback for low coverage (if enabled)
        fallback_data = []
        if self.config.enable_fallback:
            low_coverage_items = [
                item for item in extracted_data 
                if item.get("low_coverage", True) and item.get("success", False)
            ][:3]  # Limit fallback URLs
            
            if low_coverage_items:
                logger.info(f"Attempting fallback crawl for {len(low_coverage_items)} low-coverage URLs")
                fallback_tasks = [
                    self.fallback_crawl_step(item["url"]) for item in low_coverage_items
                ]
                fallback_data = await asyncio.gather(*fallback_tasks, return_exceptions=True)
        
        return {
            "discovery_results": discovery_results,
            "filtered_urls": filtered_urls,
            "extracted_data": extracted_data,
            "fallback_data": fallback_data,
            "optimization_metrics": optimization_metrics,
            "config_used": self.config.model_dump(),
            "process_method": "optimized_three_step"
        }
    
    def _calculate_optimization_metrics(
        self,
        discovery_results: Dict[str, Any],
        filtered_urls: List[Dict[str, Any]], 
        extracted_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate optimization and cost savings metrics"""
        
        total_discovered = discovery_results.get("total_unique_urls", 0)
        total_filtered = len(filtered_urls)
        total_extracted = len([item for item in extracted_data if item.get("success")])
        
        # Calculate savings
        extraction_cost_saved = max(0, total_discovered - total_filtered)
        cost_reduction_percentage = (extraction_cost_saved / max(total_discovered, 1)) * 100
        
        # Quality metrics
        avg_quality_score = 0.0
        if filtered_urls:
            avg_quality_score = sum(
                url_data.get("quality_score", 0) for url_data in filtered_urls
            ) / len(filtered_urls)
        
        return {
            "urls_discovered": total_discovered,
            "urls_filtered": total_filtered,
            "urls_extracted": total_extracted,
            "extraction_calls_saved": extraction_cost_saved,
            "cost_reduction_percentage": round(cost_reduction_percentage, 1),
            "average_quality_score": round(avg_quality_score, 3),
            "filtering_efficiency": round((total_filtered / max(total_discovered, 1)) * 100, 1),
            "extraction_success_rate": round((total_extracted / max(total_filtered, 1)) * 100, 1)
        }


# Factory functions for different environments
def create_dev_client() -> OptimizedTavilyClient:
    """Create client optimized for development"""
    config = TavilyConfig(
        search_depth="basic",
        max_results=6,
        max_concurrent=1,
        enable_fallback=True,
        extract_timeout_sec=90,
        fallback_timeout_sec=45,
        fallback_max_depth=1,
        fallback_max_urls=3,
        # Phase 2: Conservative settings for development
        enable_intent_optimization=True,   # Test new features
        enable_quality_filter=False,       # Don't filter in dev for testing
        min_domain_quality=0.5,            # Lower threshold for dev
        # Phase 3: Conservative Map API settings for development
        enable_map_api=False,              # Disable expensive Map API in dev
        map_max_depth=1,                   # Shallow mapping for testing
        map_max_results=10                 # Limited results in dev
    )
    return OptimizedTavilyClient(config=config)


def create_prod_client() -> OptimizedTavilyClient:
    """Create client optimized for production"""
    config = TavilyConfig(
        search_depth="advanced",
        max_results=20,
        max_concurrent=5,
        enable_fallback=True,
        extract_timeout_sec=120,
        fallback_timeout_sec=60,
        fallback_max_depth=2,
        fallback_max_urls=5,
        coverage_threshold=0.60,
        # Phase 2: Aggressive optimization for production
        enable_intent_optimization=True,   # Full intent-based optimization
        enable_quality_filter=True,        # Filter low-quality domains
        min_domain_quality=0.7,            # Higher quality threshold
        # Phase 3: Full Map API integration for production
        enable_map_api=True,               # Enable comprehensive discovery
        map_max_depth=2,                   # Deeper mapping for coverage
        map_max_results=50                 # More results for comprehensive discovery
    )
    return OptimizedTavilyClient(config=config)
