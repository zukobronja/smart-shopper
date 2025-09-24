"""
Tests for CredibilityFilterAgent

Comprehensive test suite covering:
- Domain reputation scoring
- Recency scoring with date parsing
- Extractability assessment
- Intent-aware weighting
- Filtering logic and fallback strategies
- Integration with real state data
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from app.agents.credibility_filter_agent import CredibilityFilterAgent
from app.agents.state import create_initial_state


class TestCredibilityFilterAgent:
    
    @pytest.fixture
    def agent(self):
        """Create CredibilityFilterAgent instance"""
        return CredibilityFilterAgent()
    
    @pytest.fixture
    def sample_search_results(self):
        """Sample search results for testing"""
        return [
            {
                "url": "https://www.amazon.com/product/gaming-laptop",
                "title": "Best Gaming Laptop 2024",
                "content": "Gaming laptop with RTX 4070...",
                "score": 0.8,
                "published_date": "2024-01-15"
            },
            {
                "url": "https://www.bestbuy.com/products/laptop-review",
                "title": "Laptop Review and Specs", 
                "content": "Detailed review of laptop specifications...",
                "score": 0.7,
                "published_date": "2023-12-01"
            },
            {
                "url": "https://unknown-site.com/laptop-info",
                "title": "Laptop Information",
                "content": "Basic laptop info...",
                "score": 0.4
                # No published_date
            }
        ]
    
    @pytest.fixture 
    def sample_extracted_content(self):
        """Sample extracted content for testing"""
        return [
            {
                "url": "https://www.amazon.com/product/gaming-laptop",
                "content": "High-quality extracted content with price $1299, specs: 16GB RAM, RTX 4070, Intel i7"
            },
            {
                "url": "https://www.bestbuy.com/products/laptop-review", 
                "content": "Review content with rating 4.5/5, features listed"
            },
            {
                "url": "https://unknown-site.com/laptop-info",
                "content": "No content"  # Poor extraction
            }
        ]
    
    def test_agent_initialization(self, agent):
        """Test agent properly initializes"""
        assert agent.name == "Credibility Filter"
        assert agent.credibility_threshold == 0.4
        assert len(agent.fallback_thresholds) == 3
        assert "product_search" in agent.intent_weights
    
    @pytest.mark.asyncio
    async def test_process_empty_results(self, agent):
        """Test handling of empty search results"""
        state = create_initial_state("test query", "test_run")
        state["raw_search_results"] = []
        
        result_state = await agent.process(state)
        
        assert result_state["credibility_filtered_results"] == []
        assert len(result_state["agent_steps"]) > 0
    
    @pytest.mark.asyncio
    async def test_process_successful_filtering(self, agent, sample_search_results, sample_extracted_content):
        """Test successful filtering with good results"""
        state = create_initial_state("gaming laptop", "test_run")
        state["raw_search_results"] = sample_search_results
        state["extracted_content"] = sample_extracted_content
        
        # Mock search query
        mock_query = MagicMock()
        mock_query.intent = "product_search"
        state["search_query"] = mock_query
        
        result_state = await agent.process(state)
        
        filtered_results = result_state["credibility_filtered_results"]
        assert len(filtered_results) > 0
        
        # Check results have credibility scores
        for result in filtered_results:
            assert "credibility_score" in result
            assert "credibility_breakdown" in result
            assert result["credibility_score"] > 0
    
    def test_calculate_domain_score(self, agent):
        """Test domain reputation scoring"""
        # Test high-quality domains
        assert agent._calculate_domain_score("https://www.amazon.com/product") == 1.0
        assert agent._calculate_domain_score("https://bestbuy.com/item") == 0.95
        
        # Test unknown domain 
        unknown_score = agent._calculate_domain_score("https://unknown-site.com/page")
        assert unknown_score == 0.7  # Default score
        
        # Test malformed URL
        assert agent._calculate_domain_score("not-a-url") == 0.3
        assert agent._calculate_domain_score("") == 0.0
    
    def test_calculate_recency_score(self, agent):
        """Test recency scoring with various dates"""
        # Recent content (within 30 days)
        recent_result = {
            "published_date": (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        }
        assert agent._calculate_recency_score(recent_result) == 1.0
        
        # Older content (1 year old)
        old_result = {
            "published_date": (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        }
        score = agent._calculate_recency_score(old_result)
        assert score == 0.2  # Minimum score
        
        # No date available
        no_date_result = {}
        assert agent._calculate_recency_score(no_date_result) == 0.7  # Default
    
    def test_extract_publication_date(self, agent):
        """Test date extraction from various formats"""
        # ISO format
        result1 = {"published_date": "2024-01-15T10:30:00Z"}
        date1 = agent._extract_publication_date(result1)
        assert date1 is not None
        assert date1.year == 2024
        
        # Date only format
        result2 = {"date": "2024-01-15"}
        date2 = agent._extract_publication_date(result2)
        assert date2 is not None
        
        # URL date extraction
        result3 = {"url": "https://site.com/2024/01/15/article"}
        date3 = agent._extract_publication_date(result3)
        assert date3 is not None
        assert date3.month == 1
        assert date3.day == 15
    
    def test_calculate_extractability_score(self, agent):
        """Test extractability scoring"""
        extraction_lookup = {
            "https://good-extraction.com": {
                "content": "Detailed product info with price $299, specs: 8GB RAM, good features and specifications"
            },
            "https://poor-extraction.com": {
                "content": "No content"
            },
            "https://short-content.com": {
                "content": "Short"
            }
        }
        
        # Good extraction
        good_score = agent._calculate_extractability_score("https://good-extraction.com", extraction_lookup)
        assert good_score > 0.5
        
        # Poor extraction
        poor_score = agent._calculate_extractability_score("https://poor-extraction.com", extraction_lookup)
        assert poor_score == 0.1
        
        # No extraction data
        no_data_score = agent._calculate_extractability_score("https://not-found.com", extraction_lookup)
        assert no_data_score == 0.3
    
    @pytest.mark.asyncio
    async def test_intent_aware_scoring(self, agent, sample_search_results, sample_extracted_content):
        """Test that scoring adapts to search intent"""
        state = create_initial_state("laptop review", "test_run")
        state["raw_search_results"] = sample_search_results
        state["extracted_content"] = sample_extracted_content
        
        # Test product_search intent
        mock_query = MagicMock()
        mock_query.intent = "product_search"
        state["search_query"] = mock_query
        
        scored_product = await agent._score_results(sample_search_results, sample_extracted_content, "product_search")
        
        # Test review_search intent  
        scored_review = await agent._score_results(sample_search_results, sample_extracted_content, "review_search")
        
        # Scores should be different due to different weights
        assert scored_product[0]["credibility_score"] != scored_review[0]["credibility_score"]
    
    def test_apply_filtering_primary_success(self, agent):
        """Test primary filtering when results meet threshold"""
        scored_results = [
            {"credibility_score": 0.8, "url": "high-quality.com"},
            {"credibility_score": 0.6, "url": "medium-quality.com"}, 
            {"credibility_score": 0.2, "url": "low-quality.com"}
        ]
        
        filtered = agent._apply_filtering(scored_results, "product_search")
        
        # Should pass 2 results above 0.4 threshold
        assert len(filtered) == 2
        assert all(r["credibility_score"] >= 0.4 for r in filtered)
    
    def test_apply_filtering_fallback(self, agent):
        """Test fallback filtering when no results meet primary threshold"""
        scored_results = [
            {"credibility_score": 0.35, "url": "best-available.com"},
            {"credibility_score": 0.25, "url": "second-best.com"},
            {"credibility_score": 0.15, "url": "third-best.com"},
            {"credibility_score": 0.05, "url": "worst.com"}
        ]
        
        filtered = agent._apply_filtering(scored_results, "product_search")
        
        # Should trigger fallback and return top 3
        assert len(filtered) <= 3
        assert all("credibility_warning" in r for r in filtered)
    
    def test_apply_filtering_emergency_fallback(self, agent):
        """Test emergency fallback when all scores are very low"""
        scored_results = [
            {"credibility_score": 0.05, "url": "very-low1.com"},
            {"credibility_score": 0.03, "url": "very-low2.com"}
        ]
        
        filtered = agent._apply_filtering(scored_results, "product_search")
        
        # Should return available results with emergency warning
        assert len(filtered) == 2
        assert all("emergency fallback" in r.get("credibility_warning", "").lower() for r in filtered)
    
    @pytest.mark.asyncio
    async def test_error_handling(self, agent):
        """Test graceful error handling"""
        state = create_initial_state("test query", "test_run")
        
        # Malformed search results that cause errors
        state["raw_search_results"] = [{"invalid": "data"}]
        state["extracted_content"] = ["not_a_dict"]  # Invalid format
        
        result_state = await agent.process(state)
        
        # Should gracefully handle errors and pass through original results
        assert "credibility_filtered_results" in result_state
        assert len(result_state["agent_steps"]) > 0
        assert result_state["agent_steps"][-1].status == "error"
    
    @pytest.mark.asyncio 
    async def test_performance_target(self, agent, sample_search_results, sample_extracted_content):
        """Test performance meets <1s target"""
        state = create_initial_state("gaming laptop", "test_run")
        state["raw_search_results"] = sample_search_results * 5  # 15 results
        state["extracted_content"] = sample_extracted_content * 5
        
        mock_query = MagicMock()
        mock_query.intent = "product_search"
        state["search_query"] = mock_query
        
        start_time = datetime.now()
        result_state = await agent.process(state)
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Should complete within 1 second
        assert execution_time < 1.0
        assert len(result_state["credibility_filtered_results"]) > 0


@pytest.mark.integration
class TestCredibilityFilterIntegration:
    """Integration tests with real pipeline data"""
    
    @pytest.mark.asyncio
    async def test_integration_with_tavily_output(self):
        """Test with realistic Tavily output format"""
        agent = CredibilityFilterAgent()
        
        # Realistic Tavily search results format
        state = create_initial_state("best gaming laptop 2024", "integration_test")
        state["raw_search_results"] = [
            {
                "url": "https://www.techradar.com/reviews/best-gaming-laptops-2024",
                "title": "Best gaming laptops 2024: top picks for every budget",
                "content": "Our comprehensive guide to the best gaming laptops...",
                "score": 0.89,
                "published_date": "2024-01-10T14:30:00Z"
            },
            {
                "url": "https://www.amazon.com/dp/B0C123456",
                "title": "ASUS ROG Strix G15 Gaming Laptop",
                "content": "Gaming laptop with AMD Ryzen 7, NVIDIA RTX 4060...",
                "score": 0.76
            }
        ]
        
        state["extracted_content"] = [
            {
                "url": "https://www.techradar.com/reviews/best-gaming-laptops-2024",
                "content": "Comprehensive review covering price ranges from $800 to $2500, specifications including RAM, GPU, CPU comparisons"
            },
            {
                "url": "https://www.amazon.com/dp/B0C123456", 
                "content": "Product specifications: 16GB DDR4 RAM, NVIDIA GeForce RTX 4060, AMD Ryzen 7 7735HS, 512GB SSD, price $1299"
            }
        ]
        
        # Mock search query
        mock_query = MagicMock()
        mock_query.intent = "product_search"
        state["search_query"] = mock_query
        
        result_state = await agent.process(state)
        
        # Verify integration
        filtered_results = result_state["credibility_filtered_results"]
        assert len(filtered_results) == 2  # Both should pass filtering
        
        # Check Amazon result has high score (domain reputation)
        amazon_result = next(r for r in filtered_results if "amazon.com" in r["url"])
        assert amazon_result["credibility_score"] > 0.7
        
        # Check TechRadar result has good score (review domain + recent)
        techradar_result = next(r for r in filtered_results if "techradar.com" in r["url"])
        assert techradar_result["credibility_score"] > 0.6
        
        # Verify credibility breakdown is present
        for result in filtered_results:
            assert "credibility_breakdown" in result
            breakdown = result["credibility_breakdown"]
            assert "domain_score" in breakdown
            assert "recency_score" in breakdown
            assert "extractability_score" in breakdown