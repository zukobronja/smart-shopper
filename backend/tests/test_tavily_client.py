"""
Test suite for OptimizedTavilyClient
Tests the optimized Tavily integration with best practices
"""
import pytest
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.extractors.tavily_client import (
    OptimizedTavilyClient, 
    create_dev_client, 
    create_prod_client,
    TavilyConfig
)


class TestOptimizedTavilyClient:
    """Test suite for OptimizedTavilyClient"""
    
    @classmethod
    def setup_class(cls):
        """Set up test class"""
        cls.api_key_available = bool(os.getenv('TAVILY_API_KEY'))
        cls.dev_client = create_dev_client()
        cls.prod_client = create_prod_client()


    def test_query_optimization(self):
        """Test query optimization functionality"""
        test_cases = [
            ("laptop under $1500", "product_search"),
            ("iPhone 15 review", "review_search"), 
            ("MacBook vs ThinkPad performance comparison detailed analysis", "comparison"),
            ("A" * 500, "general")  # Too long query
        ]
        
        for query, intent in test_cases:
            optimized = self.dev_client.optimize_query(query, intent)
            
            # Assertions
            assert len(optimized) <= 400, f"Query too long: {len(optimized)} chars"
            assert optimized.strip() == optimized, "Query should be trimmed"
            
            if intent == "product_search":
                assert any(word in optimized.lower() for word in ["specs", "price", "buy"])
            elif intent == "review_search":
                assert any(word in optimized.lower() for word in ["review", "pros", "cons"])
    
    def test_config_creation(self):
        """Test configuration creation and validation"""
        # Test dev config
        assert self.dev_client.config.search_depth == "basic"
        assert self.dev_client.config.enable_fallback is True
        assert self.dev_client.config.max_results <= 10
        assert self.dev_client.config.extract_timeout_sec >= 60
        assert self.dev_client.config.fallback_max_urls >= 1
        
        # Test prod config  
        assert self.prod_client.config.search_depth == "advanced"
        assert self.prod_client.config.enable_fallback == True
        assert self.prod_client.config.max_results >= 15
        assert self.prod_client.config.extract_timeout_sec >= self.dev_client.config.extract_timeout_sec
    
    def test_coverage_calculation(self):
        """Test coverage score calculation"""
        test_data = [
            {"raw_content": "", "expected_min": 0.0, "expected_max": 0.1},
            {"raw_content": "Price: $999", "expected_min": 0.2, "expected_max": 0.8},
            {"raw_content": "Price: $999. Specifications: Intel i7, 16GB RAM, 1TB SSD", "expected_min": 0.6, "expected_max": 1.0}
        ]
        
        for data in test_data:
            score = self.dev_client._calculate_coverage(data)
            assert data["expected_min"] <= score <= data["expected_max"], \
                f"Coverage score {score} not in range [{data['expected_min']}, {data['expected_max']}]"
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not bool(os.getenv('TAVILY_API_KEY')), reason="No Tavily API key")
    async def test_search_step(self):
        """Test search functionality with real API"""
        query = "ASUS laptop gaming"
        
        result = await self.dev_client.search_step(query, intent="product_search")
        
        assert "results" in result
        assert len(result["results"]) > 0
        assert len(result["results"]) <= self.dev_client.config.max_results
        
        # Check result structure
        first_result = result["results"][0]
        assert "url" in first_result
        assert "title" in first_result
    
    @pytest.mark.asyncio  
    @pytest.mark.skipif(not bool(os.getenv('TAVILY_API_KEY')), reason="No Tavily API key")
    async def test_extract_step(self):
        """Test extraction functionality with real API"""
        # First get some real URLs from search
        search_result = await self.dev_client.search_step("laptop gaming", intent="product_search")
        
        if search_result.get("results"):
            test_urls = [search_result["results"][0]["url"]]
            
            results = await self.dev_client.extract_step(test_urls)
            
            # Results might be empty if extraction fails, but should be a list
            assert isinstance(results, list)
            
            # If we got results, check their structure
            for result in results:
                assert "url" in result
                assert "domain" in result
                assert "coverage_score" in result
                assert "success" in result
                assert isinstance(result["coverage_score"], (int, float))
        else:
            # If no search results, skip the extraction test
            pytest.skip("No search results available for extraction test")
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not bool(os.getenv('TAVILY_API_KEY')), reason="No Tavily API key") 
    async def test_two_step_process(self):
        """Test complete two-step process with real API"""
        query = "laptop gaming under 1500"
        
        result = await self.dev_client.two_step_process(
            query=query,
            intent="product_search",
            max_fallback_urls=2
        )
        
        assert "search_results" in result
        assert "extracted_data" in result
        assert "fallback_data" in result
        assert "total_urls" in result
        assert "config_used" in result
        
        # Verify structure
        assert isinstance(result["extracted_data"], list)
        assert isinstance(result["fallback_data"], list)
        assert isinstance(result["total_urls"], int)
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not bool(os.getenv('TAVILY_API_KEY')), reason="No Tavily API key")
    async def test_langchain_integration(self):
        """Test LangChain wrapper methods"""
        query = "ASUS laptop"
        
        # Test search
        search_results = await self.dev_client.langchain_search(query)
        assert isinstance(search_results, list)
        
        if search_results:
            # Test extract on first URL
            first_url = search_results[0].get("url") if search_results else "https://example.com"
            extract_result = await self.dev_client.langchain_extract(first_url)
            
            assert "url" in extract_result
            assert "status" in extract_result
            assert "method" in extract_result


# Standalone test functions for Jupyter notebook usage
async def notebook_test_basic():
    """Simplified test for notebook execution"""
    print("Notebook Test - OptimizedTavilyClient Basic")
    
    client = create_dev_client()
    
    # Test query optimization
    query = "gaming laptop under $1500 with RTX graphics"
    optimized = client.optimize_query(query, "product_search")
    
    print(f"Original query: {query}")
    print(f"Optimized query: {optimized}")
    print(f"Config: {client.config}")
    
    return client


async def notebook_test_with_api():
    """API test for notebook execution (requires API key)"""
    if not os.getenv('TAVILY_API_KEY'):
        print("No Tavily API key found")
        return None
    
    print("Notebook Test - OptimizedTavilyClient API")
    
    client = create_dev_client()
    
    # Test search
    query = "laptop gaming"
    result = await client.search_step(query, intent="product_search")
    
    print(f"Search results for '{query}': {len(result.get('results', []))} URLs")
    
    return client, result


if __name__ == "__main__":
    # Run basic tests without pytest
    import asyncio
    asyncio.run(notebook_test_basic())
