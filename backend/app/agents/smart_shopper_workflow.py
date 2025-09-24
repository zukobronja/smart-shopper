"""
SmartShopper LangGraph Workflow Implementation

Production-ready workflow orchestrating the 5-agent pipeline:
QueryOrchestrator → TavilyRetriever → CredibilityFilter → SpecExtractor → ResultsRanker

This workflow provides:
- Structured state management with LangGraph compatibility
- Error handling and graceful degradation
- Performance monitoring and cost tracking
- Conditional routing based on coverage and quality thresholds
- Complete audit trail for debugging and analytics
"""
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator
import logging

from langgraph.graph import StateGraph, END

from .state import (
    SmartShopperWorkflowState,
    create_initial_state,
    add_agent_step,
    get_state_summary,
    SearchQuery,
)
from .query_orchestrator_agent import QueryOrchestratorAgent
from .tavily_retriever_agent import TavilyRetrieverAgent
from .credibility_filter_agent import CredibilityFilterAgent
from .spec_extractor_agent import SpecExtractorAgent
from .results_ranker_agent import ResultsRankerAgent
from .rss_vector_retriever_agent import RSSVectorRetrieverAgent
from .rss_result_adapter import RSSResultAdapterAgent
from .result_fusion_agent import ResultFusionAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SmartShopperWorkflow:
    """
    LangGraph workflow orchestrating SmartShopper's 5-agent pipeline
    
    Architecture:
    1. QueryOrchestrator: Parse user query into structured parameters
    2. TavilyRetriever: Search and extract content from Tavily API
    3. CredibilityFilter: Score and filter results by source credibility
    4. SpecExtractor: Extract structured product specifications
    5. ResultsRanker: Rank products using multi-criteria scoring
    
    Features:
    - Error boundaries with graceful degradation
    - Performance monitoring and cost tracking
    - Conditional routing based on quality thresholds
    - WebSocket support for real-time updates
    - Complete execution audit trail
    """
    
    def __init__(self):
        """Initialize the workflow with all agents"""
        self.orchestrator = QueryOrchestratorAgent()
        self.retriever = TavilyRetrieverAgent()
        self.rss_retriever = RSSVectorRetrieverAgent()
        self.rss_adapter = RSSResultAdapterAgent()
        self.credibility_filter = CredibilityFilterAgent()
        self.spec_extractor = SpecExtractorAgent()
        self.ranker = ResultsRankerAgent()
        self.result_fusion = ResultFusionAgent()
        
        # Create the workflow graph
        self.graph = self._create_workflow_graph()
        self.app = self.graph.compile()
        
        logger.info("STARTING: SmartShopperWorkflow initialized with 5-agent pipeline")
    
    def _create_workflow_graph(self) -> StateGraph:
        """Create the LangGraph workflow structure"""
        workflow = StateGraph(SmartShopperWorkflowState)
        
        # Add agent nodes
        workflow.add_node("query_orchestrator", self._orchestrator_node)
        workflow.add_node("retrieval_splitter", self._retrieval_splitter_node)
        workflow.add_node("rss_vector_retriever", self._rss_vector_node)
        workflow.add_node("rss_result_adapter", self._rss_result_adapter_node)
        workflow.add_node("tavily_retriever", self._retriever_node)
        workflow.add_node("credibility_filter", self._credibility_filter_node)
        workflow.add_node("spec_extractor", self._spec_extractor_node)
        workflow.add_node("result_fusion", self._result_fusion_node)
        workflow.add_node("results_ranker", self._ranker_node)
        
        # Add conditional nodes for error handling
        workflow.add_node("handle_no_results", self._handle_no_results_node)
        workflow.add_node("handle_low_coverage", self._handle_low_coverage_node)
        
        # Define the main flow
        workflow.set_entry_point("query_orchestrator")
        workflow.add_edge("query_orchestrator", "retrieval_splitter")
        workflow.add_edge("retrieval_splitter", "rss_vector_retriever")
        workflow.add_edge("rss_vector_retriever", "rss_result_adapter")
        workflow.add_edge("rss_result_adapter", "tavily_retriever")
        
        # Conditional routing after retrieval
        workflow.add_conditional_edges(
            "tavily_retriever",
            self._check_retrieval_quality,
            {
                "proceed": "credibility_filter",
                "no_results": "handle_no_results",
                "low_coverage": "handle_low_coverage"
            }
        )
        
        # Main pipeline flow
        workflow.add_edge("credibility_filter", "spec_extractor")
        workflow.add_edge("spec_extractor", "result_fusion")
        workflow.add_edge("result_fusion", "results_ranker")
        workflow.add_edge("results_ranker", END)
        
        # Error handling flows
        workflow.add_edge("handle_no_results", END)
        workflow.add_edge("handle_low_coverage", "credibility_filter")
        
        return workflow
    
    async def _orchestrator_node(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """Execute QueryOrchestrator agent with error handling"""
        start_time = time.time()
        
        try:
            logger.info(f"PROCESSING: Starting query orchestration for: '{state['raw_query']}'")
            
            # Update state with agent processing
            updated_state = await self.orchestrator.process(state)
            
            # Track execution
            execution_time = int((time.time() - start_time) * 1000)
            search_query_obj = updated_state.get("search_query")
            if isinstance(search_query_obj, SearchQuery):
                query_intent = search_query_obj.intent
            elif isinstance(search_query_obj, dict):
                query_intent = search_query_obj.get("intent", "unknown")
            else:
                query_intent = "unknown"

            add_agent_step(
                updated_state,
                "QueryOrchestrator",
                "success",
                execution_time,
                items_processed=1,
                metadata={"query_intent": query_intent}
            )
            
            # await self._send_websocket_update(updated_state, "query_parsed") # Removed for SSE
            
            return updated_state
            
        except Exception as e:
            logger.error(f"QueryOrchestrator failed: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            add_agent_step(state, "QueryOrchestrator", "error", execution_time, error_message=str(e))
            state["errors"].append(f"QueryOrchestrator: {str(e)}")
            return state

    async def _retrieval_splitter_node(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """Fan out state for both Tavily and RSS retrieval branches."""
        logger.info("SPLITTING: Dispatching to RSS and Tavily retrievers")
        # await self._send_websocket_update(state, "retrieval_split") # Removed for SSE
        return state

    async def _rss_vector_node(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """Execute RSS vector retrieval."""
        logger.info("RETRIEVING: Running RSS vector search")
        updated_state = await self.rss_retriever.process(state)
        # await self._send_websocket_update(updated_state, "rss_results_ready") # Removed for SSE
        return updated_state

    async def _rss_result_adapter_node(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """Normalize RSS results into structured entries."""
        logger.info("ADAPTING: Converting RSS results for fusion")
        updated_state = await self.rss_adapter.process(state)
        # await self._send_websocket_update(updated_state, "rss_adapted") # Removed for SSE
        return updated_state
    
    async def _retriever_node(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """Execute TavilyRetriever agent with error handling"""
        start_time = time.time()
        
        try:
            logger.info("SEARCHING: Starting Tavily search and extraction")
            
            updated_state = await self.retriever.process(state)
            
            # Track execution with cost
            execution_time = int((time.time() - start_time) * 1000)
            add_agent_step(
                updated_state,
                "TavilyRetriever",
                "success",
                execution_time,
                items_processed=len(updated_state.get("raw_search_results", [])),
                cost_usd=0.0,  # Tavily costs handled in retriever
                metadata={
                    "coverage_score": updated_state.get("coverage_score", 0),
                    "search_results": len(updated_state.get("raw_search_results", [])),
                    "extracted_content": len(updated_state.get("extracted_content", []))
                }
            )
            
            # await self._send_websocket_update(updated_state, "content_retrieved") # Removed for SSE
            
            return updated_state
            
        except Exception as e:
            logger.error(f"ERROR: TavilyRetriever failed: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            add_agent_step(state, "TavilyRetriever", "error", execution_time, error_message=str(e))
            state["errors"].append(f"TavilyRetriever: {str(e)}")
            return state
    
    async def _credibility_filter_node(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """Execute CredibilityFilter agent with error handling"""
        start_time = time.time()
        
        try:
            logger.info("FILTERING: Starting credibility filtering and scoring")
            
            updated_state = await self.credibility_filter.process(state)
            
            execution_time = int((time.time() - start_time) * 1000)
            add_agent_step(
                updated_state,
                "CredibilityFilter",
                "success",
                execution_time,
                items_processed=len(updated_state.get("credibility_filtered_results", [])),
                metadata={
                    "filtered_results": len(updated_state.get("credibility_filtered_results", [])),
                    "avg_credibility": self._calculate_avg_credibility(updated_state.get("credibility_filtered_results", []))
                }
            )
            
            # await self._send_websocket_update(updated_state, "credibility_filtered") # Removed for SSE
            
            return updated_state
            
        except Exception as e:
            logger.error(f"ERROR: CredibilityFilter failed: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            add_agent_step(state, "CredibilityFilter", "error", execution_time, error_message=str(e))
            state["errors"].append(f"CredibilityFilter: {str(e)}")
            return state
    
    async def _spec_extractor_node(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """Execute SpecExtractor agent with error handling"""
        start_time = time.time()
        
        try:
            logger.info("EXTRACTING: Starting product specification extraction")
            
            updated_state = await self.spec_extractor.process(state)
            
            execution_time = int((time.time() - start_time) * 1000)
            add_agent_step(
                updated_state,
                "SpecExtractor",
                "success",
                execution_time,
                items_processed=len(updated_state.get("structured_products", [])),
                metadata={
                    "structured_products": len(updated_state.get("structured_products", [])),
                    "avg_extraction_coverage": self._calculate_avg_extraction_coverage(updated_state.get("structured_products", []))
                }
            )
            
            # await self._send_websocket_update(updated_state, "specs_extracted") # Removed for SSE
            
            return updated_state
            
        except Exception as e:
            logger.error(f"ERROR: SpecExtractor failed: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            add_agent_step(state, "SpecExtractor", "error", execution_time, error_message=str(e))
            state["errors"].append(f"SpecExtractor: {str(e)}")
            return state

    async def _result_fusion_node(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """Merge Tavily-derived structured products with RSS-adapted items."""
        logger.info("FUSING: Merging Tavily and RSS product candidates")
        updated_state = await self.result_fusion.process(state)
        # await self._send_websocket_update(updated_state, "results_fused") # Removed for SSE
        return updated_state

    async def _ranker_node(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """Execute ResultsRanker agent with error handling"""
        start_time = time.time()
        
        try:
            logger.info("RANKING: Starting intelligent product ranking")
            
            updated_state = await self.ranker.process(state)
            
            execution_time = int((time.time() - start_time) * 1000)
            add_agent_step(
                updated_state,
                "ResultsRanker",
                "success",
                execution_time,
                items_processed=len(updated_state.get("ranked_products", [])),
                cost_usd=self._estimate_ranking_cost(updated_state.get("ranked_products", [])),
                metadata={
                    "ranked_products": len(updated_state.get("ranked_products", [])),
                    "avg_final_score": self._calculate_avg_final_score(updated_state.get("ranked_products", []))
                }
            )
            
            # await self._send_websocket_update(updated_state, "ranking_complete") # Removed for SSE
            
            return updated_state
            
        except Exception as e:
            logger.error(f"ERROR: ResultsRanker failed: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            add_agent_step(state, "ResultsRanker", "error", execution_time, error_message=str(e))
            state["errors"].append(f"ResultsRanker: {str(e)}")
            return state
    
    def _check_retrieval_quality(self, state: SmartShopperWorkflowState) -> str:
        """Conditional routing based on retrieval quality"""
        raw_results = state.get("raw_search_results", [])
        coverage_score = state.get("coverage_score", 0.0)
        
        if len(raw_results) == 0:
            logger.warning("WARNING: No search results found - routing to error handler")
            return "no_results"
        
        if coverage_score < 0.3:
            logger.warning(f"WARNING: Low coverage score ({coverage_score:.2f}) - attempting recovery")
            return "low_coverage"
        
        logger.info(f"SUCCESS: Good retrieval quality - coverage: {coverage_score:.2f}, results: {len(raw_results)}")
        return "proceed"
    
    async def _handle_no_results_node(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """Handle case where no search results are found"""
        logger.warning("NO_RESULTS: No results found - returning empty result set")
        
        state["warnings"].append("No search results found for the given query")
        state["ranked_products"] = []
        
        add_agent_step(
            state,
            "ErrorHandler",
            "success",
            0,
            items_processed=0,
            metadata={"error_type": "no_results"}
        )
        
        # await self._send_websocket_update(state, "no_results_found") # Removed for SSE
        return state
    
    async def _handle_low_coverage_node(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """Handle case where coverage is low but some results exist"""
        coverage = state.get("coverage_score", 0.0)
        logger.warning(f"WARNING: Low coverage ({coverage:.2f}) - proceeding with available data")
        
        state["warnings"].append(f"Low content coverage ({coverage:.1%}) - results may be incomplete")
        
        add_agent_step(
            state,
            "ErrorHandler",
            "success",
            0,
            items_processed=0,
            metadata={"error_type": "low_coverage", "coverage_score": coverage}
        )
        
        # await self._send_websocket_update(state, "low_coverage_warning") # Removed for SSE
        return state
    
    # Removed _send_websocket_update as it's replaced by direct yielding in execute_stream

    def _calculate_avg_credibility(self, results: List[Dict]) -> float:
        """Calculate average credibility score"""
        if not results:
            return 0.0
        scores = [r.get("credibility_score", 0) for r in results]
        return sum(scores) / len(scores)
    
    def _calculate_avg_extraction_coverage(self, products: List[Dict]) -> float:
        """Calculate average extraction coverage"""
        if not products:
            return 0.0
        coverages = [p.get("extraction_coverage", 0) for p in products]
        return sum(coverages) / len(coverages)
    
    def _calculate_avg_final_score(self, products: List[Dict]) -> float:
        """Calculate average final ranking score"""
        if not products:
            return 0.0
        scores = [p.get("final_score", 0) for p in products]
        return sum(scores) / len(scores)
    
    def _estimate_ranking_cost(self, products: List[Dict]) -> float:
        """Estimate API costs for ranking (embeddings + LLM calls)"""
        # Rough estimate: $0.001 per product for embeddings + $0.01 for top 3 explanations
        base_cost = len(products) * 0.001
        explanation_cost = min(3, len(products)) * 0.01
        return base_cost + explanation_cost
    
    async def execute(
        self,
        raw_query: str,
        user_id: Optional[str] = None,
        websocket_manager: Optional[Any] = None,
        job_id: Optional[str] = None
    ) -> SmartShopperWorkflowState:
        """
        Execute the complete SmartShopper workflow
        
        Args:
            raw_query: User's search query
            user_id: Optional user identifier
            websocket_manager: Optional WebSocket manager for real-time updates
            job_id: Optional job identifier for WebSocket updates
        
        Returns:
            SmartShopperWorkflowState: Final state with ranked products
        """
        start_time = time.time()
        
        # Create initial state
        initial_state = create_initial_state(
            raw_query=raw_query,
            user_id=user_id,
            websocket_manager=websocket_manager,
            job_id=job_id
        )
        
        logger.info(f"STARTING: Starting SmartShopper workflow for query: '{raw_query}'")
        
        try:
            # Execute the workflow
            final_state = await self.app.ainvoke(initial_state)
            
            # Calculate final metrics
            total_time = int((time.time() - start_time) * 1000)
            final_state["execution_time_ms"] = total_time
            
            # Log completion
            logger.info(f"SUCCESS: Workflow completed in {total_time}ms")
            logger.info(f"METRICS: Results: {len(final_state.get('ranked_products', []))} products ranked")
            logger.info(f"COST: Total cost: ${final_state.get('total_cost_usd', 0):.4f}")
            
            # Workflow completed successfully
            
            return final_state
            
        except Exception as e:
            logger.error(f"ERROR: Workflow execution failed: {e}")
            
            # Create error state
            error_state = initial_state
            error_state["errors"].append(f"WorkflowExecution: {str(e)}")
            error_state["execution_time_ms"] = int((time.time() - start_time) * 1000)
            
            # Error state prepared for return
            
            return error_state


# Global workflow instance
_workflow_instance: Optional[SmartShopperWorkflow] = None


def get_workflow() -> SmartShopperWorkflow:
    """Get or create the global workflow instance"""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = SmartShopperWorkflow()
    return _workflow_instance


async def execute_search_workflow(
    raw_query: str,
    user_id: Optional[str] = None,
    websocket_manager: Optional[Any] = None,
    job_id: Optional[str] = None
) -> SmartShopperWorkflowState:
    """
    Convenience function to execute the SmartShopper workflow
    
    Args:
        raw_query: User's search query
        user_id: Optional user identifier
        websocket_manager: Optional WebSocket manager for real-time updates
        job_id: Optional job identifier for WebSocket updates
    
    Returns:
        SmartShopperWorkflowState: Final state with ranked products
    """
    workflow = get_workflow()
    return await workflow.execute(
        raw_query=raw_query,
        user_id=user_id,
        websocket_manager=websocket_manager,
        job_id=job_id
    )
