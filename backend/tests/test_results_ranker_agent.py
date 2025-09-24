"""
Unit Tests for ResultsRankerAgent

Comprehensive testing of all ranking components:
- SemanticRelevanceScorer (embedding + keyword fallback)
- PriceValueScorer (competitive analysis)
- QualityAssessmentScorer (credibility + completeness)
- RankingExplainer (template + LLM hybrid)
- ResultsRankerAgent (full integration)
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from app.agents.results_ranker_agent import (
    ResultsRankerAgent,
    SemanticRelevanceScorer,
    PriceValueScorer,
    QualityAssessmentScorer,
    RankingExplainer
)
from app.agents.state import create_initial_state, SearchQuery


class TestSemanticRelevanceScorer:
    """Test semantic relevance scoring with different embedding strategies"""
    
    def setup_method(self):
        self.scorer = SemanticRelevanceScorer()
    
    @pytest.mark.asyncio
    async def test_calculate_relevance_keyword_fallback(self):
        """Test keyword-based relevance when embeddings unavailable"""
        # Mock embedding failure to test fallback
        self.scorer.openai_embeddings = None
        self.scorer.sentence_model = None
        
        query = "gaming laptop under $2000"
        product = {
            "title": "ASUS ROG Strix Gaming Laptop",
            "brand": "ASUS",
            "category": "laptop",
            "specs": {"processor": "Intel i7", "graphics": "RTX 3060"}
        }
        
        relevance = await self.scorer.calculate_relevance(query, product)
        
        # Should have reasonable relevance due to keyword matches
        assert 0.0 <= relevance <= 1.0
        assert relevance > 0.3  # Good match should score reasonably
    
    @pytest.mark.asyncio
    async def test_calculate_relevance_exact_match(self):
        """Test perfect keyword match scenario"""
        query = "MacBook Pro"
        product = {
            "title": "Apple MacBook Pro M3",
            "brand": "Apple",
            "category": "laptop"
        }
        
        relevance = await self.scorer.calculate_relevance(query, product)
        assert relevance > 0.7  # Should score high for exact match
    
    @pytest.mark.asyncio
    async def test_calculate_relevance_no_match(self):
        """Test completely unrelated products"""
        query = "gaming laptop"
        product = {
            "title": "Kitchen Blender for Smoothies",
            "brand": "Vitamix",
            "category": "kitchen"
        }
        
        relevance = await self.scorer.calculate_relevance(query, product)
        assert relevance < 0.3  # Should score low for unrelated products
    
    def test_create_product_text(self):
        """Test product text creation for search"""
        product = {
            "title": "MacBook Pro M3",
            "brand": "Apple",
            "category": "laptop",
            "specs": {
                "processor": "M3 chip",
                "memory": "16GB",
                "storage": "512GB SSD"
            }
        }
        
        text = self.scorer._create_product_text(product)
        
        assert "MacBook Pro M3" in text
        assert "Apple" in text
        assert "laptop" in text
        assert "M3 chip" in text
        assert "16GB" in text
    
    def test_keyword_similarity_calculation(self):
        """Test keyword similarity algorithm"""
        query = "gaming laptop RTX"
        product_text = "ASUS Gaming Laptop with RTX 3060"
        
        similarity = self.scorer._calculate_keyword_similarity(query, product_text)
        
        # Should have good similarity (gaming, laptop, RTX all match)
        assert similarity > 0.5
        assert similarity <= 1.0
    
    def test_cosine_similarity(self):
        """Test cosine similarity calculation"""
        vec1 = [1.0, 0.0, 1.0]
        vec2 = [0.0, 1.0, 1.0]
        
        similarity = self.scorer._cosine_similarity(vec1, vec2)
        assert 0.0 <= similarity <= 1.0
    
    @pytest.mark.asyncio 
    @patch('app.agents.results_ranker_agent.OpenAIEmbeddings')
    async def test_openai_embeddings_integration(self, mock_embeddings_class):
        """Test OpenAI embeddings integration"""
        # Mock OpenAI embeddings
        mock_embeddings = Mock()
        mock_embeddings.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
        mock_embeddings_class.return_value = mock_embeddings
        
        # Create scorer with mocked OpenAI
        with patch('app.agents.results_ranker_agent.settings') as mock_settings:
            mock_settings.EMBEDDINGS_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"
            
            scorer = SemanticRelevanceScorer()
            scorer.openai_embeddings = mock_embeddings
            
            query = "gaming laptop"
            product_text = "ASUS gaming laptop"
            
            similarity = await scorer._calculate_embedding_similarity_openai(query, product_text)
            
            assert 0.0 <= similarity <= 1.0
            assert mock_embeddings.aembed_query.call_count == 2


class TestPriceValueScorer:
    """Test price value scoring and competitive analysis"""
    
    def setup_method(self):
        self.scorer = PriceValueScorer()
    
    def test_calculate_value_score_competitive(self):
        """Test value score calculation with competitive context"""
        # Target product - mid-range price
        product = {"title": "Test Laptop", "price": 1500, "specs": {"memory": "16GB"}}
        
        # Category context - various prices
        category_products = [
            {"title": "Budget Laptop", "price": 800},
            {"title": "Mid Laptop", "price": 1500}, 
            {"title": "Premium Laptop", "price": 2500}
        ]
        
        value_score = self.scorer.calculate_value_score(product, category_products)
        
        # Mid-range price should get reasonable score
        assert 0.0 <= value_score <= 1.0
        assert 0.3 < value_score < 0.8  # Not cheapest, not most expensive
    
    def test_calculate_value_score_best_deal(self):
        """Test value score for cheapest option"""
        product = {"title": "Budget Laptop", "price": 800}
        
        category_products = [
            {"title": "Budget Laptop", "price": 800},
            {"title": "Mid Laptop", "price": 1500},
            {"title": "Premium Laptop", "price": 2500}
        ]
        
        value_score = self.scorer.calculate_value_score(product, category_products)
        
        # Cheapest should score high
        assert value_score > 0.7
    
    def test_calculate_value_score_no_price(self):
        """Test handling of products without price"""
        product = {"title": "Test Product"}
        category_products = [{"title": "Other", "price": 1000}]
        
        value_score = self.scorer.calculate_value_score(product, category_products)
        
        # Should return neutral score for missing price
        assert value_score == 0.5
    
    def test_extract_price_direct(self):
        """Test direct price extraction"""
        product = {"price": 1499.99}
        price = self.scorer._extract_price(product)
        assert price == 1499.99
    
    def test_extract_price_from_specs(self):
        """Test price extraction from specs"""
        product = {
            "specs": {
                "price": "$1,299.99",
                "memory": "16GB"
            }
        }
        price = self.scorer._extract_price(product)
        assert price == 1299.99
    
    def test_extract_price_missing(self):
        """Test handling of missing price"""
        product = {"title": "Test Product"}
        price = self.scorer._extract_price(product)
        assert price is None
    
    def test_percentile_rank_calculation(self):
        """Test percentile rank calculation"""
        values = [100, 200, 300, 400, 500]
        
        # Test different positions
        assert self.scorer._get_percentile_rank(100, values) == 0.1  # 10th percentile
        assert self.scorer._get_percentile_rank(300, values) == 0.5  # 50th percentile
        assert self.scorer._get_percentile_rank(500, values) == 0.9  # 90th percentile
    
    def test_feature_adjustment(self):
        """Test feature-based price adjustment"""
        product = {
            "specs": {
                "processor": "i7",
                "memory": "32GB", 
                "storage": "1TB SSD",
                "graphics": "RTX 4060",
                "display": "4K"
            }
        }
        
        category_products = [
            {"specs": {"processor": "i5", "memory": "8GB"}},  # 2 specs
            {"specs": {"processor": "i7", "memory": "16GB", "storage": "512GB"}}  # 3 specs
        ]
        
        adjustment = self.scorer._calculate_feature_adjustment(product, category_products)
        
        # Product has more features, should get positive adjustment
        assert adjustment >= 0.0
        assert adjustment <= 0.2
    
    def test_deal_boost_calculation(self):
        """Test deal/discount detection"""
        product = {
            "price": 1200,
            "specs": {
                "was_price": "$1500",
                "processor": "i7"
            }
        }
        
        boost = self.scorer._calculate_deal_boost(product)
        
        # Should detect 20% discount and give boost
        assert boost > 0.0
        assert boost <= 0.2


class TestQualityAssessmentScorer:
    """Test product quality assessment"""
    
    def setup_method(self):
        self.scorer = QualityAssessmentScorer()
    
    def test_assess_quality_high_credibility(self):
        """Test quality assessment for high-credibility product"""
        product = {
            "title": "MacBook Pro M3",
            "brand": "Apple",
            "price": 2499,
            "category": "laptop",
            "credibility_score": 0.95,
            "specs": {
                "processor": "M3 Pro",
                "memory": "16GB",
                "storage": "512GB",
                "display": "16-inch Retina",
                "battery": "22 hours"
            }
        }
        
        quality = self.scorer.assess_quality(product)
        
        # High credibility + complete specs should score well
        assert quality > 0.8
        assert quality <= 1.0
    
    def test_assess_quality_low_credibility(self):
        """Test quality assessment for low-credibility product"""
        product = {
            "title": "Unknown Laptop",
            "credibility_score": 0.3,
            "specs": {"processor": "Unknown"}
        }
        
        quality = self.scorer.assess_quality(product)
        
        # Low credibility + incomplete specs should score poorly
        assert quality < 0.6
    
    def test_completeness_score_full_data(self):
        """Test completeness scoring for complete product"""
        product = {
            "title": "Complete Product",
            "brand": "Apple",
            "price": 1999,
            "category": "laptop",
            "specs": {
                "spec1": "value1",
                "spec2": "value2",
                "spec3": "value3",
                "spec4": "value4",
                "spec5": "value5",
                "spec6": "value6",
                "spec7": "value7",
                "spec8": "value8",
                "spec9": "value9",
                "spec10": "value10"
            }
        }
        
        completeness = self.scorer._calculate_completeness_score(product)
        
        # Should score high for complete data
        assert completeness > 0.9
    
    def test_completeness_score_minimal_data(self):
        """Test completeness scoring for minimal product"""
        product = {"title": "Basic Product"}
        
        completeness = self.scorer._calculate_completeness_score(product)
        
        # Should score low for minimal data
        assert completeness < 0.5
    
    def test_maturity_score_indicators(self):
        """Test maturity scoring with various indicators"""
        product = {
            "specs": {
                "award": "Best Laptop 2024",
                "version": "Generation 3",
                "certified": "Energy Star"
            }
        }
        
        maturity = self.scorer._calculate_maturity_score(product)
        
        # Should get boost for positive indicators
        assert maturity > 0.5


class TestRankingExplainer:
    """Test explanation generation system"""
    
    def setup_method(self):
        self.explainer = RankingExplainer()
    
    @pytest.mark.asyncio
    async def test_generate_explanation_template(self):
        """Test template-based explanation generation"""
        # Mock LLM to None to force template mode
        self.explainer.llm = None
        
        product = {
            "title": "MacBook Pro M3 16-inch",
            "brand": "Apple",
            "price": 2499,
            "category": "laptop"
        }
        
        scores = {
            "relevance": 0.9,
            "value": 0.6,
            "quality": 0.85,
            "final_score": 0.78
        }
        
        explanation = await self.explainer.generate_explanation(
            product, scores, 1, "gaming laptop"
        )
        
        assert "MacBook Pro M3 16-inch" in explanation
        assert "Top Choice" in explanation or "#1" in explanation
        assert len(explanation) > 10  # Should be meaningful
    
    def test_template_explanation_ranking(self):
        """Test template explanations for different ranks"""
        product = {"title": "Test Product", "price": 1000}
        scores = {"relevance": 0.7, "value": 0.8, "quality": 0.6, "final_score": 0.7}
        
        # Test rank 1
        exp1 = self.explainer._generate_template_explanation(product, scores, 1, "test")
        assert "Top Choice" in exp1
        
        # Test rank 2
        exp2 = self.explainer._generate_template_explanation(product, scores, 2, "test")
        assert "#2" in exp2
        
        # Test rank 5
        exp5 = self.explainer._generate_template_explanation(product, scores, 5, "test")
        assert "#5" in exp5
    
    @pytest.mark.asyncio
    @patch('app.agents.results_ranker_agent.ChatOpenAI')
    async def test_llm_enhancement(self, mock_chat_class):
        """Test LLM-enhanced explanations"""
        # Mock LLM response
        mock_response = Mock()
        mock_response.content = "Enhanced explanation with specific details about the product."
        
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_chat_class.return_value = mock_llm
        
        explainer = RankingExplainer()
        explainer.llm = mock_llm
        
        product = {"title": "Test Product", "brand": "TestBrand"}
        scores = {"relevance": 0.8, "value": 0.7, "quality": 0.9, "final_score": 0.8}
        
        enhanced = await explainer._enhance_with_llm(
            "Template explanation", product, scores, "test query", []
        )
        
        assert enhanced == "Enhanced explanation with specific details about the product."
        assert mock_llm.ainvoke.called


class TestResultsRankerAgent:
    """Test the main ResultsRankerAgent integration"""
    
    def setup_method(self):
        self.agent = ResultsRankerAgent()
    
    @pytest.mark.asyncio
    async def test_process_empty_products(self):
        """Test handling of empty product list"""
        state = create_initial_state("test query")
        state["structured_products"] = []
        
        result_state = await self.agent.process(state)
        
        assert result_state["ranked_products"] == []
        assert len(result_state["agent_steps"]) == 1
        assert result_state["agent_steps"][0].status == "skipped"
    
    @pytest.mark.asyncio
    async def test_process_single_product(self):
        """Test ranking a single product"""
        state = create_initial_state("gaming laptop")
        state["search_query"] = SearchQuery(
            raw_query="gaming laptop",
            normalized_query="gaming laptop",
            intent="product_search"
        )
        state["structured_products"] = [{
            "title": "ASUS ROG Gaming Laptop",
            "brand": "ASUS",
            "price": 1599,
            "category": "laptop",
            "credibility_score": 0.9,
            "specs": {
                "processor": "Intel i7",
                "memory": "16GB",
                "graphics": "RTX 3060"
            }
        }]
        
        # Mock embeddings to avoid API calls
        with patch.object(self.agent.relevance_scorer, 'calculate_relevance', return_value=0.8):
            result_state = await self.agent.process(state)
        
        assert len(result_state["ranked_products"]) == 1
        
        ranked_product = result_state["ranked_products"][0]
        assert ranked_product["rank"] == 1
        assert "scores" in ranked_product
        assert "final_score" in ranked_product
        assert "explanation" in ranked_product
        assert 0.0 <= ranked_product["final_score"] <= 1.0
    
    @pytest.mark.asyncio
    async def test_process_multiple_products_ranking(self):
        """Test proper ranking order with multiple products"""
        state = create_initial_state("laptop")
        state["search_query"] = SearchQuery(
            raw_query="laptop",
            normalized_query="laptop", 
            intent="product_search"
        )
        
        # Create products with different characteristics
        state["structured_products"] = [
            {
                "title": "Budget Laptop Basic",
                "brand": "Generic",
                "price": 500,
                "category": "laptop",
                "credibility_score": 0.6,
                "specs": {"processor": "Celeron", "memory": "4GB"}
            },
            {
                "title": "Premium Gaming Laptop",
                "brand": "ASUS",
                "price": 2000,
                "category": "laptop", 
                "credibility_score": 0.95,
                "specs": {
                    "processor": "Intel i9",
                    "memory": "32GB",
                    "graphics": "RTX 4070",
                    "storage": "1TB SSD",
                    "display": "4K 17-inch"
                }
            },
            {
                "title": "MacBook Pro M3",
                "brand": "Apple",
                "price": 2499,
                "category": "laptop",
                "credibility_score": 1.0,
                "specs": {
                    "processor": "M3 Pro",
                    "memory": "18GB",
                    "storage": "512GB SSD",
                    "display": "16-inch Retina"
                }
            }
        ]
        
        # Mock relevance scoring to focus on other factors
        relevance_scores = [0.7, 0.9, 0.8]  # Gaming laptop scores highest for "laptop" query
        with patch.object(
            self.agent.relevance_scorer, 
            'calculate_relevance', 
            side_effect=relevance_scores
        ):
            result_state = await self.agent.process(state)
        
        ranked_products = result_state["ranked_products"]
        
        # Should have all products ranked
        assert len(ranked_products) == 3
        
        # Check ranking order (ranks should be 1, 2, 3)
        ranks = [p["rank"] for p in ranked_products]
        assert ranks == [1, 2, 3]
        
        # Top product should have highest final_score
        final_scores = [p["final_score"] for p in ranked_products]
        assert final_scores == sorted(final_scores, reverse=True)
        
        # All products should have explanations
        for product in ranked_products:
            assert len(product["explanation"]) > 0
    
    def test_group_by_category(self):
        """Test product grouping by category"""
        products = [
            {"title": "Laptop 1", "category": "laptop"},
            {"title": "Phone 1", "category": "smartphone"},
            {"title": "Laptop 2", "category": "laptop"},
            {"title": "Blender 1", "category": "kitchen"}
        ]
        
        groups = self.agent._group_by_category(products)
        
        assert len(groups) == 3
        assert len(groups["laptop"]) == 2
        assert len(groups["smartphone"]) == 1
        assert len(groups["kitchen"]) == 1
    
    @pytest.mark.asyncio
    async def test_calculate_product_scores(self):
        """Test individual product score calculation"""
        product = {
            "title": "Test Laptop",
            "brand": "TestBrand",
            "price": 1500,
            "category": "laptop",
            "credibility_score": 0.8,
            "specs": {"processor": "i7", "memory": "16GB"}
        }
        
        category_products = [product]  # Single product for simplicity
        
        with patch.object(self.agent.relevance_scorer, 'calculate_relevance', return_value=0.7):
            scores = await self.agent._calculate_product_scores(
                product, "laptop", "product_search", category_products
            )
        
        assert "relevance" in scores
        assert "value" in scores
        assert "quality" in scores
        assert "final_score" in scores
        
        # All scores should be in valid range
        for score in scores.values():
            assert 0.0 <= score <= 1.0
    
    def test_get_intent_weights(self):
        """Test intent-aware weight calculation"""
        # Test product_search intent
        weights = self.agent._get_intent_weights("product_search", "laptop")
        assert abs(sum(weights.values()) - 1.0) < 0.001  # Should sum to ~1.0
        assert weights["relevance"] > 0.3  # Should emphasize relevance
        
        # Test comparison intent
        comp_weights = self.agent._get_intent_weights("comparison", "laptop")
        assert comp_weights["quality"] > weights["quality"]  # Should emphasize quality more
        
        # Test review_search intent
        review_weights = self.agent._get_intent_weights("review_search", "laptop")
        assert review_weights["quality"] > comp_weights["quality"]  # Should emphasize quality most
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling and graceful degradation"""
        state = create_initial_state("test")
        state["structured_products"] = [{"title": "Test Product"}]  # Minimal product
        
        # Should handle missing fields gracefully
        result_state = await self.agent.process(state)
        
        assert len(result_state["ranked_products"]) == 1
        assert result_state["agent_steps"][-1].status in ["success", "error"]


# Integration fixtures for async testing
@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])