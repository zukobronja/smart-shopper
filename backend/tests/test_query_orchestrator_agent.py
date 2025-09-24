"""
Comprehensive test suite for QueryOrchestratorAgent
Tests query parsing, state management, and Tavily parameter generation
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.agents.query_orchestrator_agent import QueryOrchestratorAgent, create_query_orchestrator_agent
from app.agents.state import (
    SmartShopperState, 
    SearchQuery, 
    create_initial_state,
    get_state_summary
)


class TestQueryOrchestratorAgent:
    """Test suite for QueryOrchestratorAgent"""

    @pytest.fixture
    def agent(self):
        """Create agent instance for testing"""
        with patch('app.agents.query_orchestrator_agent.ChatOpenAI') as mock_openai:
            mock_llm = MagicMock()
            mock_openai.return_value = mock_llm
            return QueryOrchestratorAgent()

    @pytest.fixture
    def mock_state(self):
        """Create mock state for testing"""
        return create_initial_state(
            raw_query="gaming laptop under $2000",
            user_id="test_user",
            run_id="test_run_123"
        )

    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM response for testing"""
        return json.dumps({
            "normalized_query": "gaming laptop",
            "intent": "product_search",
            "category": "laptop",
            "brand": None,
            "budget_min": None,
            "budget_max": 2000,
            "constraints": ["gaming", "good performance"],
            "priorities": ["performance", "graphics"],
            "region": "US"
        })

    @pytest.mark.asyncio
    async def test_agent_initialization(self, agent):
        """Test agent initializes correctly"""
        assert agent.name == "Query Orchestrator"
        assert agent.color == agent.BLUE
        assert agent.llm is not None
        assert agent.prompt is not None

    @pytest.mark.asyncio
    async def test_successful_query_parsing(self, agent, mock_state, mock_llm_response):
        """Test successful query parsing with valid LLM response"""
        with patch.object(agent.llm, 'ainvoke', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_llm_response
            
            result_state = await agent.process(mock_state)
            
            # Verify search_query was created
            assert result_state["search_query"] is not None
            assert isinstance(result_state["search_query"], SearchQuery)
            
            # Verify parsed fields
            search_query = result_state["search_query"]
            assert search_query.raw_query == "gaming laptop under $2000"
            assert search_query.normalized_query == "gaming laptop"
            assert search_query.intent == "product_search"
            assert search_query.category == "laptop"
            assert search_query.budget_max == 2000
            assert "gaming" in search_query.constraints
            assert "performance" in search_query.priorities
            
            # Verify agent step was recorded
            assert len(result_state["agent_steps"]) == 1
            step = result_state["agent_steps"][0]
            assert step.agent_name == "Query Orchestrator"
            assert step.status == "success"
            assert step.items_processed == 1

    @pytest.mark.asyncio
    async def test_query_parsing_golden_dataset(self):
        """Test agent with golden query dataset"""
        golden_queries = [
            {
                "query": "iPhone 15 Pro Max 256GB",
                "expected": {
                    "intent": "product_search",
                    "category": "smartphone",
                    "brand": "apple"
                }
            },
            {
                "query": "best wireless headphones under $200 2024",
                "expected": {
                    "intent": "product_search", 
                    "category": "headphones",
                    "budget_max": 200
                }
            },
            {
                "query": "MacBook Pro vs Dell XPS 15 comparison",
                "expected": {
                    "intent": "comparison",
                    "category": "laptop"
                }
            },
            {
                "query": "Sony WH-1000XM5 review",
                "expected": {
                    "intent": "review_search",
                    "category": "headphones",
                    "brand": "sony"
                }
            }
        ]

        # Mock OpenAI to return realistic responses
        for test_case in golden_queries:
            with patch('app.agents.query_orchestrator_agent.ChatOpenAI') as mock_openai_class:
                mock_llm = MagicMock()
                mock_openai_class.return_value = mock_llm
                agent = QueryOrchestratorAgent()
                
                # Create realistic response based on expected values
                mock_response = {
                    "normalized_query": test_case["query"].lower(),
                    "intent": test_case["expected"]["intent"],
                    "category": test_case["expected"].get("category"),
                    "brand": test_case["expected"].get("brand"),
                    "budget_min": test_case["expected"].get("budget_min"),
                    "budget_max": test_case["expected"].get("budget_max"),
                    "constraints": [],
                    "priorities": [],
                    "region": "US"
                }
                
                with patch.object(agent.llm, 'ainvoke', new_callable=AsyncMock) as mock_llm_ainvoke:
                    mock_llm_ainvoke.return_value = json.dumps(mock_response)
                    
                    state = create_initial_state(test_case["query"])
                    result = await agent.process(state)
                    
                    search_query = result["search_query"]
                    assert search_query.intent == test_case["expected"]["intent"]
                    
                    if "category" in test_case["expected"]:
                        assert search_query.category == test_case["expected"]["category"]
                    
                    if "brand" in test_case["expected"]:
                        assert search_query.brand == test_case["expected"]["brand"]
                    
                    if "budget_max" in test_case["expected"]:
                        assert search_query.budget_max == test_case["expected"]["budget_max"]

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, agent, mock_state):
        """Test handling of invalid JSON from LLM"""
        with patch.object(agent.llm, 'ainvoke', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "This is not valid JSON"
            
            result_state = await agent.process(mock_state)
            
            # Should create fallback SearchQuery
            assert result_state["search_query"] is not None
            search_query = result_state["search_query"]
            assert search_query.raw_query == "gaming laptop under $2000"
            assert search_query.normalized_query == "gaming laptop under $2000"
            
            # Should record error
            assert len(result_state["agent_steps"]) == 1
            step = result_state["agent_steps"][0]
            assert step.status == "error"
            assert step.error_message is not None

    @pytest.mark.asyncio
    async def test_llm_api_error(self, agent, mock_state):
        """Test handling of LLM API errors"""
        with patch.object(agent.llm, 'ainvoke', new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("OpenAI API Error")
            
            result_state = await agent.process(mock_state)
            
            # Should create fallback SearchQuery
            assert result_state["search_query"] is not None
            search_query = result_state["search_query"]
            assert search_query.raw_query == "gaming laptop under $2000"
            
            # Should record error
            assert len(result_state["agent_steps"]) == 1
            step = result_state["agent_steps"][0]
            assert step.status == "error"
            assert "OpenAI API Error" in step.error_message

    @pytest.mark.asyncio
    async def test_tavily_search_params_generation(self, agent, mock_state, mock_llm_response):
        """Test Tavily search parameters are generated correctly"""
        with patch.object(agent.llm, 'ainvoke', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_llm_response
            
            result_state = await agent.process(mock_state)
            
            # Check that tavily_search_params field exists and is populated
            assert "tavily_search_params" in result_state
            tavily_params = result_state["tavily_search_params"]
            
            # Verify required Tavily parameters
            assert "query" in tavily_params
            assert tavily_params["query"] == "gaming laptop"
            assert tavily_params["search_depth"] == "advanced"
            assert tavily_params["max_results"] == 10

    @pytest.mark.asyncio
    async def test_empty_query_handling(self):
        """Test handling of empty or None query"""
        with patch('app.agents.query_orchestrator_agent.ChatOpenAI') as mock_openai:
            mock_llm = MagicMock()
            mock_openai.return_value = mock_llm
            agent = QueryOrchestratorAgent()
            
            state = create_initial_state("")
            result_state = await agent.process(state)
            
            # Should still create SearchQuery with empty values
            assert result_state["search_query"] is not None
            search_query = result_state["search_query"]
            assert search_query.raw_query == ""

    @pytest.mark.asyncio
    async def test_state_mutation_safety(self, agent, mock_state, mock_llm_response):
        """Test that agent doesn't mutate unexpected state fields"""
        original_run_id = mock_state["run_id"]
        original_user_id = mock_state["user_id"]
        
        with patch.object(agent.llm, 'ainvoke', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_llm_response
            
            result_state = await agent.process(mock_state)
            
            # Verify core state fields weren't changed
            assert result_state["run_id"] == original_run_id
            assert result_state["user_id"] == original_user_id
            assert result_state["raw_query"] == "gaming laptop under $2000"

    @pytest.mark.asyncio
    async def test_agent_execution_timing(self, agent, mock_state, mock_llm_response):
        """Test that execution timing is tracked"""
        with patch.object(agent.llm, 'ainvoke', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_llm_response
            
            start_time = datetime.now()
            result_state = await agent.process(mock_state)
            end_time = datetime.now()
            
            # Check agent step timing
            assert len(result_state["agent_steps"]) == 1
            step = result_state["agent_steps"][0]
            assert step.execution_time_ms > 0
            assert step.execution_time_ms < (end_time - start_time).total_seconds() * 1000

    def test_factory_function(self):
        """Test factory function creates agent correctly"""
        with patch('app.agents.query_orchestrator_agent.ChatOpenAI') as mock_openai:
            mock_llm = MagicMock()
            mock_openai.return_value = mock_llm
            agent = create_query_orchestrator_agent()
            assert isinstance(agent, QueryOrchestratorAgent)
            assert agent.name == "Query Orchestrator"

    @pytest.mark.asyncio
    async def test_prompt_engineering_quality(self, agent):
        """Test that the prompt produces consistent, valid responses"""
        test_queries = [
            "budget smartphone under 300 euros",
            "4K gaming monitor 27 inch",
            "laptop for programming Python Java"
        ]
        
        for query in test_queries:
            # Test that prompt creates valid format request
            prompt_value = agent.prompt.format_prompt(query=query)
            messages = prompt_value.to_messages()
            
            # Verify system message contains schema
            system_msg = messages[0].content
            assert "JSON" in system_msg
            assert "intent" in system_msg
            assert "category" in system_msg
            assert "examples" in system_msg.lower()

    @pytest.mark.asyncio 
    async def test_state_summary_integration(self, agent, mock_state, mock_llm_response):
        """Test integration with state summary functionality"""
        with patch.object(agent.llm, 'ainvoke', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_llm_response
            
            result_state = await agent.process(mock_state)
            summary = get_state_summary(result_state)
            
            # Verify summary includes agent progress
            assert summary["progress"]["agents_completed"] == 1
            assert summary["progress"]["errors"] == 0
            assert summary["progress"]["execution_time_ms"] > 0

    @pytest.mark.asyncio
    async def test_concurrent_agent_execution(self, agent, mock_llm_response):
        """Test that multiple agent instances can run concurrently"""
        import asyncio
        
        async def run_agent_with_query(query: str):
            state = create_initial_state(query)
            with patch.object(agent.llm, 'ainvoke', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = mock_llm_response
                return await agent.process(state)
        
        # Run multiple agents concurrently
        tasks = [
            run_agent_with_query("laptop"),
            run_agent_with_query("smartphone"), 
            run_agent_with_query("headphones")
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 3
        for result in results:
            assert result["search_query"] is not None
            assert len(result["agent_steps"]) == 1
            assert result["agent_steps"][0].status == "success"


# Integration test with actual OpenAI (requires API key)
class TestQueryOrchestratorAgentIntegration:
    """Integration tests with real OpenAI API (optional, requires API key)"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_openai_integration(self):
        """Test with real OpenAI API - only runs if OPENAI_API_KEY is set"""
        import os
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set - skipping integration test")
        
        agent = QueryOrchestratorAgent()
        state = create_initial_state("gaming laptop under $1500 with RTX 4060")
        
        result_state = await agent.process(state)
        
        # Verify real parsing worked
        assert result_state["search_query"] is not None
        search_query = result_state["search_query"]
        assert search_query.intent == "product_search"
        assert search_query.category == "laptop"
        assert "gaming" in search_query.constraints or "gaming" in search_query.normalized_query.lower()
        assert search_query.budget_max == 1500


if __name__ == "__main__":
    # Run tests with: pytest test_query_orchestrator_agent.py -v
    # Run with integration tests: pytest test_query_orchestrator_agent.py -v -m integration
    pytest.main([__file__, "-v"])
