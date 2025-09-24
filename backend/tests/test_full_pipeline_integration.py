"""
Full 5-Agent Pipeline Integration Test

Tests the complete SmartShopper pipeline end-to-end:
QueryOrchestrator → TavilyRetriever → CredibilityFilter → SpecExtractor → ResultsRanker

This validates that:
1. All agents work together seamlessly
2. State is properly passed between agents
3. Data transformations are correct
4. Final ranking produces meaningful results
"""
import pytest
import asyncio
from unittest.mock import patch, Mock, AsyncMock
from datetime import datetime

from app.agents.query_orchestrator_agent import QueryOrchestratorAgent
from app.agents.tavily_retriever_agent import TavilyRetrieverAgent
from app.agents.credibility_filter_agent import CredibilityFilterAgent
from app.agents.spec_extractor_agent import SpecExtractorAgent
from app.agents.results_ranker_agent import ResultsRankerAgent
from app.agents.state import create_initial_state


class TestFullPipelineIntegration:
    """Test complete 5-agent pipeline integration"""
    
    def setup_method(self):
        """Set up agents for testing"""
        self.orchestrator = QueryOrchestratorAgent()
        self.retriever = TavilyRetrieverAgent()
        self.credibility_filter = CredibilityFilterAgent()
        self.spec_extractor = SpecExtractorAgent()
        self.ranker = ResultsRankerAgent()
    
    @pytest.mark.asyncio
    async def test_full_pipeline_laptop_search(self):
        """Test complete pipeline with laptop search query"""
        
        # Create initial state
        state = create_initial_state("gaming laptop under $2000")
        
        # Mock external API calls to avoid real API usage during testing
        with patch('app.agents.query_orchestrator_agent.ChatOpenAI') as mock_openai_orchestrator, \
             patch('app.agents.tavily_retriever_agent.OptimizedTavilyClient') as mock_tavily, \
             patch('app.agents.spec_extractor_agent.ChatOpenAI') as mock_openai_spec, \
             patch('app.agents.results_ranker_agent.OpenAIEmbeddings') as mock_embeddings, \
             patch('app.agents.results_ranker_agent.ChatOpenAI') as mock_openai_ranker:
            
            # Mock QueryOrchestratorAgent LLM
            mock_llm_orchestrator = AsyncMock()
            mock_llm_orchestrator.ainvoke = AsyncMock(return_value=type('Response', (), {
                'content': '''
                {
                    "intent": "product_search",
                    "category": "laptop",
                    "budget_max": 2000,
                    "query_terms": ["gaming", "laptop"],
                    "search_queries": ["gaming laptop under $2000", "RTX gaming laptop budget"],
                    "tavily_params": {
                        "max_results": 8,
                        "include_domains": ["amazon.com", "bestbuy.com", "newegg.com"],
                        "search_depth": "advanced"
                    }
                }
                '''
            })())
            mock_openai_orchestrator.return_value = mock_llm_orchestrator
            
            # Mock TavilyRetrieverAgent client
            mock_client = Mock()
            mock_client.search.return_value = {
                "results": [
                    {
                        "url": "https://amazon.com/gaming-laptop-asus",
                        "title": "ASUS ROG Strix Gaming Laptop",
                        "content": "High-performance gaming laptop with RTX 3060",
                        "score": 0.85
                    },
                    {
                        "url": "https://bestbuy.com/msi-gaming-laptop",
                        "title": "MSI Gaming Laptop GF65",
                        "content": "Affordable gaming laptop with RTX 3050",
                        "score": 0.78
                    }
                ]
            }
            mock_client.extract.return_value = [
                {
                    "url": "https://amazon.com/gaming-laptop-asus",
                    "title": "ASUS ROG Strix Gaming Laptop",
                    "content": """
                    ASUS ROG Strix G15 Gaming Laptop Specifications:
                    - Processor: AMD Ryzen 7 5800H
                    - Graphics: NVIDIA GeForce RTX 3060 6GB
                    - RAM: 16 GB DDR4
                    - Storage: 512 GB NVMe SSD
                    - Display: 15.6" Full HD (1920x1080) 144Hz
                    - Weight: 2.3 kg
                    - Price: $1,599.99
                    """,
                    "success": True
                },
                {
                    "url": "https://bestbuy.com/msi-gaming-laptop",
                    "title": "MSI Gaming Laptop GF65",
                    "content": """
                    MSI GF65 Thin Gaming Laptop Features:
                    - Processor: Intel Core i5-10500H
                    - Graphics: NVIDIA GeForce RTX 3050 4GB
                    - RAM: 8 GB DDR4
                    - Storage: 256 GB NVMe SSD
                    - Display: 15.6" Full HD IPS 144Hz
                    - Weight: 1.86 kg
                    - Price: $899.99
                    """,
                    "success": True
                }
            ]
            mock_tavily.return_value = mock_client
            
            # Mock SpecExtractorAgent LLM
            mock_llm_spec = AsyncMock()
            mock_llm_spec.ainvoke = AsyncMock(return_value=type('Response', (), {
                'content': '{"warranty": "1 year", "connectivity": "Wi-Fi 6, Bluetooth 5.0"}'
            })())
            mock_openai_spec.return_value = mock_llm_spec
            
            # Mock ResultsRankerAgent embeddings
            mock_embeddings_instance = Mock()
            mock_embeddings_instance.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
            mock_embeddings.return_value = mock_embeddings_instance
            
            # Mock ResultsRankerAgent LLM
            mock_llm_ranker = AsyncMock()
            mock_llm_ranker.ainvoke = AsyncMock(return_value=type('Response', (), {
                'content': 'Top gaming laptop choice with excellent performance and competitive pricing.'
            })())
            mock_openai_ranker.return_value = mock_llm_ranker
            
            # Execute full pipeline
            
            # Step 1: Query Orchestrator
            state = await self.orchestrator.process(state)
            
            # Verify orchestrator results
            assert state.get("search_query") is not None
            search_query = state["search_query"]
            assert search_query["intent"] == "product_search"
            assert search_query["category"] == "laptop"
            assert search_query["budget_max"] == 2000
            
            # Step 2: Tavily Retriever
            state = await self.retriever.process(state)
            
            # Verify retriever results
            assert "raw_search_results" in state
            assert "extracted_content" in state
            assert len(state["raw_search_results"]) == 2
            assert len(state["extracted_content"]) == 2
            
            # Step 3: Credibility Filter
            state = await self.credibility_filter.process(state)
            
            # Verify credibility filter results
            assert "credibility_filtered_results" in state
            filtered_results = state["credibility_filtered_results"]
            assert len(filtered_results) > 0
            
            # All results should have credibility scores
            for result in filtered_results:
                assert "credibility_score" in result
                assert 0.0 <= result["credibility_score"] <= 1.0
            
            # Step 4: Spec Extractor
            state = await self.spec_extractor.process(state)
            
            # Verify spec extractor results
            assert "structured_products" in state
            structured_products = state["structured_products"]
            assert len(structured_products) > 0
            
            # All products should have structured data
            for product in structured_products:
                assert "title" in product
                assert "category" in product
                assert "specs" in product
                assert "extraction_coverage" in product
                assert product["extraction_coverage"] > 0.0
            
            # Step 5: Results Ranker
            state = await self.ranker.process(state)
            
            # Verify ranker results
            assert "ranked_products" in state
            ranked_products = state["ranked_products"]
            assert len(ranked_products) > 0
            
            # Products should be properly ranked
            ranks = [p["rank"] for p in ranked_products]
            assert ranks == list(range(1, len(ranked_products) + 1))  # 1, 2, 3, ...
            
            # Final scores should be in descending order
            final_scores = [p["final_score"] for p in ranked_products]
            assert final_scores == sorted(final_scores, reverse=True)
            
            # All products should have complete ranking data
            for product in ranked_products:
                assert "rank" in product
                assert "final_score" in product
                assert "scores" in product
                assert "explanation" in product
                assert 0.0 <= product["final_score"] <= 1.0
                assert len(product["explanation"]) > 0
            
            # Verify agent execution tracking
            assert len(state["agent_steps"]) == 5  # All 5 agents executed
            agent_names = [step.agent_name for step in state["agent_steps"]]
            expected_names = [
                "Query Orchestrator",
                "Tavily Retriever", 
                "Credibility Filter",
                "Spec Extractor",
                "Results Ranker"
            ]
            assert agent_names == expected_names
            
            # All agents should have completed successfully
            for step in state["agent_steps"]:
                assert step.status == "success"
                assert step.execution_time_ms >= 0
    
    @pytest.mark.asyncio
    async def test_pipeline_state_consistency(self):
        """Test that state remains consistent throughout pipeline"""
        
        state = create_initial_state("MacBook Pro")
        initial_run_id = state["run_id"]
        initial_raw_query = state["raw_query"]
        
        # Mock all external calls
        with patch('app.agents.query_orchestrator_agent.ChatOpenAI') as mock_openai, \
             patch('app.agents.tavily_retriever_agent.OptimizedTavilyClient') as mock_tavily, \
             patch('app.agents.spec_extractor_agent.ChatOpenAI') as mock_spec_llm, \
             patch('app.agents.results_ranker_agent.OpenAIEmbeddings') as mock_embeddings:
            
            # Mock minimal responses
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=type('Response', (), {
                'content': '{"intent": "product_search", "category": "laptop", "query_terms": ["macbook"], "tavily_params": {"max_results": 5}}'
            })())
            mock_openai.return_value = mock_llm
            
            mock_client = Mock()
            mock_client.search.return_value = {"results": []}
            mock_client.extract.return_value = []
            mock_tavily.return_value = mock_client
            
            mock_spec_llm.return_value = mock_llm
            
            mock_embeddings_instance = Mock()
            mock_embeddings_instance.aembed_query = AsyncMock(return_value=[0.1, 0.2])
            mock_embeddings.return_value = mock_embeddings_instance
            
            # Execute all agents
            state = await self.orchestrator.process(state)
            state = await self.retriever.process(state)
            state = await self.credibility_filter.process(state)
            state = await self.spec_extractor.process(state)
            state = await self.ranker.process(state)
            
            # Verify state consistency
            assert state["run_id"] == initial_run_id
            assert state["raw_query"] == initial_raw_query
            
            # Verify state evolution
            assert state.get("search_query") is not None
            assert "raw_search_results" in state
            assert "extracted_content" in state
            assert "credibility_filtered_results" in state
            assert "structured_products" in state
            assert "ranked_products" in state
    
    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self):
        """Test pipeline behavior when individual agents encounter errors"""
        
        state = create_initial_state("test query")
        
        # Test orchestrator failure
        with patch('app.agents.query_orchestrator_agent.ChatOpenAI') as mock_openai:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(side_effect=Exception("API Error"))
            mock_openai.return_value = mock_llm
            
            state = await self.orchestrator.process(state)
            
            # Should have error in agent steps
            assert len(state["agent_steps"]) == 1
            assert state["agent_steps"][0].status == "error"
            assert "API Error" in state["agent_steps"][0].error_message
    
    @pytest.mark.asyncio
    async def test_pipeline_with_comparison_intent(self):
        """Test pipeline with comparison search intent"""
        
        state = create_initial_state("iPhone vs Samsung Galaxy camera")
        
        # Mock for comparison intent
        with patch('app.agents.query_orchestrator_agent.ChatOpenAI') as mock_openai, \
             patch('app.agents.tavily_retriever_agent.OptimizedTavilyClient') as mock_tavily, \
             patch('app.agents.spec_extractor_agent.ChatOpenAI') as mock_spec_llm:
            
            # Mock comparison intent response
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=type('Response', (), {
                'content': '''
                {
                    "intent": "comparison",
                    "category": "smartphone",
                    "query_terms": ["iPhone", "Samsung", "Galaxy", "camera"],
                    "search_queries": ["iPhone camera vs Samsung Galaxy camera"],
                    "tavily_params": {"max_results": 6}
                }
                '''
            })())
            mock_openai.return_value = mock_llm
            mock_spec_llm.return_value = mock_llm
            
            # Mock search results
            mock_client = Mock()
            mock_client.search.return_value = {
                "results": [
                    {
                        "url": "https://example.com/iphone-review",
                        "title": "iPhone 15 Pro Camera Review",
                        "content": "iPhone camera analysis",
                        "score": 0.9
                    }
                ]
            }
            mock_client.extract.return_value = [
                {
                    "url": "https://example.com/iphone-review",
                    "title": "iPhone 15 Pro Camera Review",
                    "content": "iPhone 15 Pro camera features: 48MP main sensor, 3x telephoto, Night mode",
                    "success": True
                }
            ]
            mock_tavily.return_value = mock_client
            
            # Execute pipeline
            state = await self.orchestrator.process(state)
            state = await self.retriever.process(state)
            state = await self.credibility_filter.process(state)
            state = await self.spec_extractor.process(state)
            
            # Mock embeddings for ranker
            with patch('app.agents.results_ranker_agent.OpenAIEmbeddings') as mock_embeddings:
                mock_embeddings_instance = Mock()
                mock_embeddings_instance.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
                mock_embeddings.return_value = mock_embeddings_instance
                
                state = await self.ranker.process(state)
            
            # Verify comparison intent was preserved
            search_query = state.get("search_query")
            assert search_query is not None
            assert search_query["intent"] == "comparison"
            
            # Verify final results exist
            assert "ranked_products" in state
    
    @pytest.mark.asyncio
    async def test_pipeline_performance_tracking(self):
        """Test that pipeline properly tracks performance metrics"""
        
        state = create_initial_state("test product search")
        
        # Mock all external calls for fast execution
        with patch('app.agents.query_orchestrator_agent.ChatOpenAI') as mock_openai, \
             patch('app.agents.tavily_retriever_agent.OptimizedTavilyClient') as mock_tavily, \
             patch('app.agents.spec_extractor_agent.ChatOpenAI') as mock_spec_llm, \
             patch('app.agents.results_ranker_agent.OpenAIEmbeddings') as mock_embeddings:
            
            # Set up all mocks
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=type('Response', (), {
                'content': '{"intent": "product_search", "tavily_params": {"max_results": 3}}'
            })())
            mock_openai.return_value = mock_llm
            mock_spec_llm.return_value = mock_llm
            
            mock_client = Mock()
            mock_client.search.return_value = {"results": []}
            mock_client.extract.return_value = []
            mock_tavily.return_value = mock_client
            
            mock_embeddings_instance = Mock()
            mock_embeddings_instance.aembed_query = AsyncMock(return_value=[0.1])
            mock_embeddings.return_value = mock_embeddings_instance
            
            # Record start time
            start_time = datetime.now()
            
            # Execute full pipeline
            state = await self.orchestrator.process(state)
            state = await self.retriever.process(state)
            state = await self.credibility_filter.process(state)
            state = await self.spec_extractor.process(state)
            state = await self.ranker.process(state)
            
            # Record end time
            end_time = datetime.now()
            total_time_ms = (end_time - start_time).total_seconds() * 1000
            
            # Verify performance tracking
            assert state["execution_time_ms"] > 0
            assert state["execution_time_ms"] <= total_time_ms * 2  # Allow for some overhead
            assert state["total_cost_usd"] >= 0.0
            
            # Each agent should have recorded execution time
            for step in state["agent_steps"]:
                assert step.execution_time_ms >= 0
                assert hasattr(step, 'metadata')


# Fixtures for async testing
@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "-s", "--tb=short"])