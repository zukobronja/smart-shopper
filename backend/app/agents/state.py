"""
SmartShopper Multi-Agent State Management

Defines the shared state structure for the LangGraph multi-agent pipeline.
All state objects use Pydantic for validation and TypedDict for LangGraph compatibility.
Includes base agent class with colored logging functionality.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, TypedDict
from pydantic import BaseModel, Field


class SmartShopperAgent:
    """
    Base class for all SmartShopper agents
    Provides colored logging and common functionality
    """
    
    # Foreground colors for agent identification
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    ORANGE = '\033[38;5;208m'
    
    # Background color
    BG_BLACK = '\033[40m'
    
    # Reset code to return to default color
    RESET = '\033[0m'
    
    name: str = "Base Agent"
    color: str = WHITE
    
    def log(self, message: str):
        """
        Log message with agent identification and color coding
        """
        color_code = self.BG_BLACK + self.color
        formatted_message = f"[{self.name}] {message}"
        print(color_code + formatted_message + self.RESET)
    
    async def process(self, state: 'SmartShopperWorkflowState') -> 'SmartShopperWorkflowState':
        """
        Main processing method - to be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement process method")


class SearchQuery(BaseModel):
    """Parsed and normalized search query"""
    raw_query: str
    normalized_query: str
    intent: str = "product_search"
    category: Optional[str] = None
    brand: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    constraints: List[str] = Field(default_factory=list)
    priorities: List[str] = Field(default_factory=list)
    region: str = "US"  # Default to US market


# Future Development: Advanced data models for Phase 2
# See docs/FUTURE_DEVELOPMENT.md for production schema evolution

# class ProductSpec(BaseModel):
#     """Product specification data (Phase 2)"""
#     title: str
#     brand: Optional[str] = None
#     sku: Optional[str] = None
#     gtin: Optional[str] = None
#     specs: Dict[str, Any] = Field(default_factory=dict)

# class PriceOffer(BaseModel):
#     """Price and availability information (Phase 2)"""
#     price: Optional[float] = None
#     shipping_cost: Optional[float] = None
#     seller: Optional[str] = None

# class SourceInfo(BaseModel):
#     """Source credibility and metadata (Phase 2)"""
#     url: str
#     domain: str
#     credibility_score: float = 0.0


# Future Development: Advanced data models for Phase 2
# See docs/FUTURE_DEVELOPMENT.md for production schema evolution

# class ProductListing(BaseModel):
#     """Complete product listing with specs and offer (Phase 2)"""
#     product: ProductSpec
#     offer: PriceOffer
#     source: SourceInfo

# class ReviewData(BaseModel):
#     """Editorial review information (Phase 2)"""
#     headline: str
#     verdict_score: Optional[float] = None
#     pros: List[str] = Field(default_factory=list)
#     cons: List[str] = Field(default_factory=list)

# class Review(BaseModel):
#     """Complete review with source info (Phase 2)"""
#     review: ReviewData
#     source: SourceInfo


class AgentStepResult(BaseModel):
    """Individual agent execution result"""
    agent_name: str
    status: str  # "success", "error", "skipped"
    execution_time_ms: int
    items_processed: int = 0
    cost_usd: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SmartShopperWorkflowState(TypedDict):
    """
    MVP State object for the 5-agent SmartShopper LangGraph workflow.
    
    This simplified state schema matches our current working implementation:
    QueryOrchestrator → TavilyRetriever → CredibilityFilter → SpecExtractor → ResultsRanker
    
    State Evolution (MVP Pipeline):
    1. Input -> raw_query, user_id, run_id
    2. QueryOrchestrator -> search_query populated
    3. TavilyRetriever -> raw_search_results, extracted_content, coverage_score populated
    4. CredibilityFilter -> credibility_filtered_results populated
    5. SpecExtractor -> structured_products populated
    6. ResultsRanker -> ranked_products populated
    """
    # Input (required at start)
    raw_query: str
    user_id: Optional[str]
    run_id: str
    
    # Query Processing (populated by QueryOrchestrator)
    search_query: Optional[SearchQuery]
    
    # Tavily Retrieval (populated by TavilyRetriever)
    raw_search_results: List[Dict[str, Any]]
    extracted_content: List[Dict[str, Any]]
    coverage_score: float
    
    # Credibility Filtering (populated by CredibilityFilter)
    credibility_filtered_results: List[Dict[str, Any]]
    
    # Spec Extraction (populated by SpecExtractor)
    structured_products: List[Dict[str, Any]]
    
    # RSS Retrieval (populated by RSSVectorRetriever)
    rss_results: List[Dict[str, Any]]
    rss_structured_products: List[Dict[str, Any]]
    
    # Final Results (populated by ResultsRanker)
    ranked_products: List[Dict[str, Any]]
    
    # Execution Tracking (updated by all agents)
    agent_steps: List[AgentStepResult]
    total_cost_usd: float
    execution_time_ms: int
    
    # Error Handling (updated by any agent on issues)
    errors: List[str]
    warnings: List[str]
    
    # Optional: WebSocket for real-time updates
    websocket_manager: Optional[Any]
    job_id: Optional[str]


def create_initial_state(
    raw_query: str,
    user_id: Optional[str] = None,
    run_id: Optional[str] = None,
    websocket_manager: Optional[Any] = None,
    job_id: Optional[str] = None
) -> SmartShopperWorkflowState:
    """
    Create an initial state object for the SmartShopper MVP workflow.
    
    Args:
        raw_query: The user's search query
        user_id: Optional user identifier
        run_id: Optional run identifier (generated if not provided)
        websocket_manager: Optional WebSocket manager for real-time updates
        job_id: Optional job identifier for WebSocket updates
    
    Returns:
        SmartShopperWorkflowState: Initialized state object for MVP pipeline
    """
    import uuid
    
    if not run_id:
        run_id = str(uuid.uuid4())
    
    return SmartShopperWorkflowState(
        # Input
        raw_query=raw_query,
        user_id=user_id,
        run_id=run_id,
        
        # Query Processing
        search_query=None,
        
        # Tavily Retrieval
        raw_search_results=[],
        extracted_content=[],
        coverage_score=0.0,
        
        # Credibility Filtering
        credibility_filtered_results=[],
        
        # Spec Extraction
        structured_products=[],
        
        # RSS Retrieval
        rss_results=[],
        rss_structured_products=[],
        
        # Final Results
        ranked_products=[],
        
        # Execution Tracking
        agent_steps=[],
        total_cost_usd=0.0,
        execution_time_ms=0,
        
        # Error Handling
        errors=[],
        warnings=[],
        
        # Optional WebSocket
        websocket_manager=websocket_manager,
        job_id=job_id
    )


def validate_state_transition(
    state: SmartShopperWorkflowState,
    agent_name: str,
    required_fields: List[str],
    optional_fields: List[str] = None
) -> bool:
    """
    Validate that a state object has the required fields for a given agent.
    
    Args:
        state: The state object to validate
        agent_name: Name of the agent requesting validation
        required_fields: List of field names that must be present and non-empty
        optional_fields: List of field names that are nice to have but not required
    
    Returns:
        bool: True if validation passes, False otherwise
    
    Raises:
        ValueError: If required fields are missing or invalid
    """
    missing_fields = []
    
    for field in required_fields:
        if field not in state:
            missing_fields.append(f"{field} (missing)")
        elif state[field] is None:
            missing_fields.append(f"{field} (None)")
        elif isinstance(state[field], (list, dict)) and len(state[field]) == 0:
            missing_fields.append(f"{field} (empty)")
    
    if missing_fields:
        error_msg = f"{agent_name} validation failed. Missing required fields: {', '.join(missing_fields)}"
        raise ValueError(error_msg)
    
    return True


def add_agent_step(
    state: SmartShopperWorkflowState,
    agent_name: str,
    status: str,
    execution_time_ms: int,
    items_processed: int = 0,
    cost_usd: float = 0.0,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Add an agent execution step to the state tracking.
    
    Args:
        state: The state object to update
        agent_name: Name of the agent
        status: Execution status ("success", "error", "skipped")
        execution_time_ms: Time taken in milliseconds
        items_processed: Number of items processed
        cost_usd: Cost in USD
        error_message: Optional error message
        metadata: Optional additional metadata
    """
    step = AgentStepResult(
        agent_name=agent_name,
        status=status,
        execution_time_ms=execution_time_ms,
        items_processed=items_processed,
        cost_usd=cost_usd,
        error_message=error_message,
        metadata=metadata or {}
    )
    
    state["agent_steps"].append(step)
    state["total_cost_usd"] += cost_usd
    state["execution_time_ms"] += execution_time_ms
    
    if status == "error" and error_message:
        state["errors"].append(f"{agent_name}: {error_message}")


def get_state_summary(state: SmartShopperWorkflowState) -> Dict[str, Any]:
    """
    Get a summary of the current state for logging or debugging.
    
    Args:
        state: The state object to summarize
    
    Returns:
        Dict containing state summary
    """
    return {
        "run_id": state["run_id"],
        "query": state["raw_query"],
        "progress": {
            "agents_completed": len([s for s in state["agent_steps"] if s.status == "success"]),
            "total_cost_usd": state["total_cost_usd"],
            "execution_time_ms": state["execution_time_ms"],
            "errors": len(state["errors"]),
            "warnings": len(state["warnings"])
        },
        "results": {
            "raw_search_results": len(state["raw_search_results"]),
            "extracted_content": len(state["extracted_content"]),
            "credibility_filtered_results": len(state["credibility_filtered_results"]),
            "structured_products": len(state["structured_products"]),
            "ranked_products": len(state["ranked_products"]),
            "coverage_score": state["coverage_score"]
        }
    }
