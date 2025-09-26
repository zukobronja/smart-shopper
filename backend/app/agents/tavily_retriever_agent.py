"""
TavilyRetriever Agent for LangGraph Pipeline
Implements optimized Tavily integration with two-step process and best practices
Integrates with QueryOrchestratorAgent output and follows BACKEND_ARCHITECTURE.md
"""
from typing import Dict, Any
from datetime import datetime

from app.agents.state import SmartShopperAgent, SmartShopperWorkflowState, add_agent_step
from app.extractors.tavily_client import create_dev_client, create_prod_client
from app.config import settings


class TavilyRetrieverAgent(SmartShopperAgent):
    """
    Tavily Retriever Agent using optimized two-step process
    
    Architecture Position:
    QueryOrchestrator → RetrievalSplitter → TavilyRetriever (parallel with RSSVectorRetriever)
    → CredibilityFilter → SpecExtractor → TavilyResultAdapter → ResultFusion → ResultsRanker
    
    Runs in parallel with RSSVectorRetrieverAgent via RetrievalSplitterNode
    """
    
    name = "Tavily Retriever"
    color = SmartShopperAgent.MAGENTA
    
    def __init__(self, use_production_config: bool = False):
        super().__init__()
        
        # Choose configuration based on TAVILY_CONFIG override or environment
        tavily_config = settings.TAVILY_CONFIG.lower()
        
        if tavily_config == "production" or (tavily_config == "auto" and (use_production_config or settings.ENVIRONMENT == "production")):
            self.tavily_client = create_prod_client()
            self.log(f"Initialized with production configuration (TAVILY_CONFIG={settings.TAVILY_CONFIG})")
        else:
            self.tavily_client = create_dev_client()
            self.log(f"Initialized with development configuration (TAVILY_CONFIG={settings.TAVILY_CONFIG})")
    
    async def process(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """
        Main processing method for LangGraph pipeline
        Integrates with QueryOrchestratorAgent output and executes Tavily two-step process
        """
        start_time = datetime.now()
        self.log("Starting Tavily search and extraction")
        
        try:
            # Get search query from QueryOrchestratorAgent
            search_query = state.get("search_query")
            tavily_params = state.get("tavily_search_params", {})
            
            if not search_query:
                raise ValueError("Missing search_query from QueryOrchestratorAgent")
            
            # Extract parameters
            query = tavily_params.get("query", search_query.normalized_query)
            intent = search_query.intent
            category = search_query.category
            
            self.log(f"Processing query: '{query}' (intent: {intent}, category: {category})")
            
            # Execute Tavily two-step process
            # Note: max_results is configured at client level, not per-request
            tavily_results = await self.tavily_client.two_step_process(
                query=query,
                intent=intent
            )
            
            # Update state following BACKEND_ARCHITECTURE.md contract
            # Extract the actual results list from search_results dict
            search_results_dict = tavily_results.get("search_results", {})
            state["raw_search_results"] = search_results_dict.get("results", []) if isinstance(search_results_dict, dict) else []
            state["extracted_content"] = tavily_results.get("extracted_data", [])
            state["coverage_score"] = tavily_results.get("overall_coverage", 0.0)
            
            # Track execution metrics
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            credits_used = tavily_results.get("credits_used", 0)
            items_processed = len(tavily_results.get("extracted_data", []))
            
            # Record successful execution
            add_agent_step(
                state,
                self.name,
                "success",
                execution_time,
                items_processed=items_processed,
                cost_usd=credits_used * 0.001  # Approximate cost
            )
            
            self.log(f"Successfully processed: {len(state['raw_search_results'])} search results, "
                    f"{len(state['extracted_content'])} extractions, "
                    f"coverage: {state['coverage_score']:.2f}")
            
            return state
            
        except Exception as e:
            self.log(f"Error in Tavily processing: {e}")
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Record failed execution
            add_agent_step(
                state,
                self.name,
                "error",
                execution_time,
                error_message=str(e)
            )
            
            # Graceful degradation - initialize empty results
            state.setdefault("raw_search_results", [])
            state.setdefault("extracted_content", [])
            state.setdefault("coverage_score", 0.0)
            
            return state
    
    async def test_configuration(self) -> Dict[str, Any]:
        """Test method for validating Tavily configuration"""
        self.log("Testing Tavily configuration")
        
        try:
            config_info = {
                "client_type": type(self.tavily_client).__name__,
                "config": self.tavily_client.config.model_dump(),
                "api_key_available": bool(self.tavily_client.api_key),
                "agent_name": self.name
            }
            
            self.log("Configuration test successful")
            return config_info
            
        except Exception as e:
            self.log(f"Configuration test failed: {e}")
            return {"error": str(e), "success": False}


# Factory functions for different use cases
def create_tavily_agent(use_production: bool = False) -> TavilyRetrieverAgent:
    """Create TavilyRetrieverAgent with appropriate configuration"""
    return TavilyRetrieverAgent(use_production_config=use_production)


def create_dev_tavily_agent() -> TavilyRetrieverAgent:
    """Create agent optimized for development and testing"""
    return TavilyRetrieverAgent(use_production_config=False)


def create_prod_tavily_agent() -> TavilyRetrieverAgent:
    """Create agent optimized for production use"""
    return TavilyRetrieverAgent(use_production_config=True)