"""
SmartShopper Multi-Agent System

LangGraph-based pipeline for intelligent product search and comparison.
Integrates Tavily web discovery, hybrid extraction, credibility scoring,
and multi-factor ranking for optimal product recommendations.
"""

from .state import (
    SmartShopperWorkflowState,
    SearchQuery,
    AgentStepResult,
    create_initial_state,
    validate_state_transition,
    add_agent_step,
    get_state_summary
)

from .config import (
    GraphConfig,
    ExecutionMode,
    TavilyConfig,
    QualityConfig,
    ExecutionLimits,
    RetrieverConfig,
    RankingConfig,
    create_development_config,
    create_testing_config,
    create_production_config,
    get_config_for_environment
)

# from .graph import SmartShopperGraph

__all__ = [
    # State management
    "SmartShopperWorkflowState",
    "SearchQuery",
    "AgentStepResult",
    "create_initial_state",
    "validate_state_transition",
    "add_agent_step",
    "get_state_summary",
    
    # Configuration
    "GraphConfig",
    "ExecutionMode",
    "TavilyConfig",
    "QualityConfig", 
    "ExecutionLimits",
    "RetrieverConfig",
    "RankingConfig",
    "create_development_config",
    "create_testing_config",
    "create_production_config",
    "get_config_for_environment",
    
    # Core graph
    # "SmartShopperGraph"
]