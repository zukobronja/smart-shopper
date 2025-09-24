"""
SmartShopper Graph Configuration Management

Centralized configuration for LangGraph pipeline execution with support for
development and production modes, cost controls, and quality thresholds.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ExecutionMode(str, Enum):
    """Execution mode for different environments"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class TavilyConfig(BaseModel):
    """Tavily API configuration"""
    # API Settings
    api_key: str
    max_tokens: int = 4000
    search_depth: str = "basic"  # "basic" or "advanced"
    include_answer: bool = False
    include_raw_content: bool = False
    
    # Cost Optimization (from Phase 4.1)
    batch_size: int = 20
    max_requests_per_minute: int = 60
    enable_intelligent_filtering: bool = True
    quality_threshold: float = 0.4  # Minimum quality score for URLs
    
    # Coverage and Fallback
    min_coverage_threshold: float = 0.6
    enable_crawl_fallback: bool = True
    max_fallback_attempts: int = 3


class QualityConfig(BaseModel):
    """Quality thresholds and validation settings"""
    # Credibility Scoring
    min_credibility_score: float = 0.3
    domain_reputation_weight: float = 0.4
    recency_weight: float = 0.2
    extractability_weight: float = 0.2
    consensus_weight: float = 0.1
    affiliate_penalty: float = 0.05
    duplicate_domain_penalty: float = 0.05
    
    # Content Quality
    min_spec_fields_required: int = 3  # For laptops/phones/cameras
    require_price_info: bool = True
    min_review_length: int = 100  # characters
    
    # Coverage Requirements
    min_ecom_sources: int = 4
    min_review_sources: int = 2
    max_sources_per_domain: int = 3


class ExecutionLimits(BaseModel):
    """Execution limits and timeouts"""
    # Time Limits
    max_execution_time_s: int = 300  # 5 minutes total
    max_agent_time_s: int = 60      # 1 minute per agent
    parallel_timeout_s: int = 120    # 2 minutes for parallel operations
    
    # Cost Controls
    max_cost_usd: float = 5.0
    cost_warning_threshold: float = 3.0
    emergency_stop_threshold: float = 4.5
    
    # Resource Limits
    max_urls_total: int = 50
    max_urls_per_source: int = 20
    max_urls_per_domain: int = 5
    max_parallel_requests: int = 10
    
    # Result Limits
    max_products_returned: int = 10
    max_listings_per_product: int = 15
    max_reviews_per_product: int = 10


class RetrieverConfig(BaseModel):
    """Configuration for retriever agents"""
    # Whitelist Domains
    ecommerce_domains: List[str] = Field(default_factory=lambda: [
        "amazon.com", "bestbuy.com", "walmart.com", "target.com",
        "bhphotovideo.com", "microcenter.com", "newegg.com",
        "mediamarkt.de", "saturn.de", "pcpartpicker.com"
    ])
    
    review_domains: List[str] = Field(default_factory=lambda: [
        "wirecutter.com", "cnet.com", "techradar.com", "laptopmag.com",
        "tomshardware.com", "digitaltrends.com", "pcmag.com",
        "theverge.com", "engadget.com"
    ])
    
    # Retrieval Strategy
    prefer_whitelist: bool = True
    whitelist_first_ratio: float = 0.7  # 70% whitelist, 30% Tavily discovery
    enable_discovery_mode: bool = True
    
    # Request Settings
    request_timeout_s: int = 30
    max_retries: int = 3
    retry_delay_s: float = 1.0


class RankingConfig(BaseModel):
    """Configuration for product ranking algorithm"""
    # Scoring Weights (must sum to 1.0)
    spec_fitness_weight: float = 0.35
    sentiment_weight: float = 0.25
    price_value_weight: float = 0.30
    availability_weight: float = 0.05
    risk_penalty_weight: float = 0.05
    
    # Scoring Parameters
    budget_match_bonus: float = 0.1
    brand_preference_bonus: float = 0.05
    recent_review_bonus: float = 0.03
    multiple_source_bonus: float = 0.02
    
    # Risk Flags
    risk_flags: List[str] = Field(default_factory=lambda: [
        "outdated_info", "low_credibility", "price_anomaly",
        "limited_availability", "negative_sentiment"
    ])


class GraphConfig(BaseModel):
    """Main configuration class for SmartShopper graph execution"""
    # Environment
    mode: ExecutionMode = ExecutionMode.DEVELOPMENT
    enable_websocket_updates: bool = True
    enable_detailed_logging: bool = True
    log_level: str = "INFO"
    
    # Component Configurations
    tavily: TavilyConfig
    quality: QualityConfig = Field(default_factory=QualityConfig)
    limits: ExecutionLimits = Field(default_factory=ExecutionLimits)
    retrievers: RetrieverConfig = Field(default_factory=RetrieverConfig)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    
    # Workflow Settings
    enable_parallel_retrieval: bool = True
    enable_credibility_filtering: bool = True
    enable_spec_extraction: bool = True
    enable_review_sentiment: bool = True
    
    # Development Features
    save_intermediate_results: bool = False
    enable_debug_mode: bool = False
    mock_external_apis: bool = False
    
    class Config:
        use_enum_values = True

    def __post_init__(self):
        """Validate configuration after initialization"""
        self._validate_config()
    
    def _validate_config(self):
        """Validate configuration values"""
        # Validate ranking weights
        total_weight = (
            self.ranking.spec_fitness_weight +
            self.ranking.sentiment_weight +
            self.ranking.price_value_weight +
            self.ranking.availability_weight +
            self.ranking.risk_penalty_weight
        )
        
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Ranking weights must sum to 1.0, got {total_weight}")
        
        # Validate cost limits
        if self.limits.cost_warning_threshold >= self.limits.max_cost_usd:
            raise ValueError("Cost warning threshold must be less than max cost")
        
        if self.limits.emergency_stop_threshold >= self.limits.max_cost_usd:
            raise ValueError("Emergency stop threshold must be less than max cost")
        
        # Validate quality thresholds
        if not (0.0 <= self.quality.min_credibility_score <= 1.0):
            raise ValueError("Credibility score must be between 0.0 and 1.0")
        
        if not (0.0 <= self.tavily.min_coverage_threshold <= 1.0):
            raise ValueError("Coverage threshold must be between 0.0 and 1.0")


def create_development_config(tavily_api_key: str) -> GraphConfig:
    """
    Create a configuration optimized for development.
    Lower limits, more logging, faster execution.
    """
    return GraphConfig(
        mode=ExecutionMode.DEVELOPMENT,
        enable_detailed_logging=True,
        enable_debug_mode=True,
        save_intermediate_results=True,
        
        tavily=TavilyConfig(
            api_key=tavily_api_key,
            batch_size=10,  # Smaller batches for testing
            max_requests_per_minute=30,
            search_depth="basic"
        ),
        
        limits=ExecutionLimits(
            max_cost_usd=1.0,  # Lower cost limit
            max_execution_time_s=120,  # 2 minutes
            max_urls_total=20,  # Fewer URLs
            max_products_returned=5
        ),
        
        quality=QualityConfig(
            min_credibility_score=0.2,  # More lenient
            min_ecom_sources=2,
            min_review_sources=1
        )
    )


def create_testing_config(tavily_api_key: str) -> GraphConfig:
    """
    Create a configuration optimized for testing.
    Predictable behavior, moderate limits.
    """
    return GraphConfig(
        mode=ExecutionMode.TESTING,
        enable_detailed_logging=True,
        enable_debug_mode=False,
        save_intermediate_results=True,
        mock_external_apis=False,  # Use real APIs for integration tests
        
        tavily=TavilyConfig(
            api_key=tavily_api_key,
            batch_size=15,
            search_depth="basic"
        ),
        
        limits=ExecutionLimits(
            max_cost_usd=2.0,
            max_execution_time_s=180,  # 3 minutes
            max_urls_total=30
        ),
        
        quality=QualityConfig(
            min_credibility_score=0.25,
            min_ecom_sources=3,
            min_review_sources=2
        )
    )


def create_production_config(tavily_api_key: str) -> GraphConfig:
    """
    Create a configuration optimized for production.
    Higher limits, performance optimized, comprehensive coverage.
    """
    return GraphConfig(
        mode=ExecutionMode.PRODUCTION,
        enable_detailed_logging=False,
        enable_debug_mode=False,
        save_intermediate_results=False,
        
        tavily=TavilyConfig(
            api_key=tavily_api_key,
            batch_size=20,  # Full batch size
            max_requests_per_minute=60,
            search_depth="advanced",  # More comprehensive search
            enable_intelligent_filtering=True
        ),
        
        limits=ExecutionLimits(
            max_cost_usd=5.0,  # Full cost allowance
            max_execution_time_s=300,  # 5 minutes
            max_urls_total=50,
            max_products_returned=10
        ),
        
        quality=QualityConfig(
            min_credibility_score=0.3,  # Higher quality bar
            min_ecom_sources=4,
            min_review_sources=2,
            require_price_info=True
        )
    )


def get_config_for_environment(
    environment: str,
    tavily_api_key: str,
    **overrides
) -> GraphConfig:
    """
    Get configuration for a specific environment with optional overrides.
    
    Args:
        environment: "development", "testing", or "production"
        tavily_api_key: Tavily API key
        **overrides: Configuration overrides
    
    Returns:
        GraphConfig: Configured graph config
    """
    config_creators = {
        "development": create_development_config,
        "testing": create_testing_config,
        "production": create_production_config
    }
    
    if environment not in config_creators:
        raise ValueError(f"Unknown environment: {environment}")
    
    config = config_creators[environment](tavily_api_key)
    
    # Apply overrides
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)
        else:
            # Handle nested overrides (e.g., "limits.max_cost_usd")
            if "." in key:
                parts = key.split(".", 1)
                section = getattr(config, parts[0])
                setattr(section, parts[1], value)
    
    config._validate_config()
    return config