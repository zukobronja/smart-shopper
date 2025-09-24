"""
Pydantic models for MongoDB documents
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from enum import Enum

class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic v2"""
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        from pydantic_core import core_schema
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")

class UserStatus(str, Enum):
    """User account status"""
    PENDING = "pending"  # Email not verified
    ACTIVE = "active"    # Normal active user
    SUSPENDED = "suspended"  # Temporarily disabled
    DELETED = "deleted"  # Soft deleted

class AuthProvider(str, Enum):
    """Authentication provider"""
    EMAIL = "email"
    GOOGLE = "google"


class RSSFeedStatus(str, Enum):
    """Lifecycle status for an RSS feed"""
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"

class MongoBaseModel(BaseModel):
    """Base model with MongoDB ObjectId support"""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }

class User(MongoBaseModel):
    """User document model"""
    email: str
    password_hash: Optional[str] = None  # None for OAuth users
    full_name: str
    auth_provider: AuthProvider = AuthProvider.EMAIL
    provider_id: Optional[str] = None  # Google user ID
    status: UserStatus = UserStatus.PENDING
    email_verified: bool = False
    profile_picture: Optional[str] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)
    email_verification_token_hash: Optional[str] = None
    email_verification_sent_at: Optional[datetime] = None
    
    # Usage tracking
    total_searches: int = 0
    last_login: Optional[datetime] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "user@example.com",
                "full_name": "John Doe",
                "auth_provider": "email",
                "status": "active",
                "email_verified": True
            }
        }
    }

class UserCreate(BaseModel):
    """User creation model (request)"""
    email: str
    password: str
    full_name: str
    
class UserResponse(BaseModel):
    """User response model (without sensitive data)"""
    id: str
    email: str
    full_name: str
    auth_provider: str
    status: str
    email_verified: bool
    profile_picture: Optional[str] = None
    total_searches: int
    created_at: datetime
    last_login: Optional[datetime] = None


class RSSFeed(MongoBaseModel):
    """Registered RSS feed metadata"""
    name: str
    url: str
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    poll_interval_minutes: int = Field(default=10, ge=1)
    next_poll_at: Optional[datetime] = None
    last_polled_at: Optional[datetime] = None
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    status: RSSFeedStatus = RSSFeedStatus.ACTIVE
    error_streak: int = 0
    health_score: float = Field(default=1.0, ge=0.0, le=1.0)
    last_error: Optional[str] = None


class RSSFeedCreate(BaseModel):
    """Payload for registering a new RSS feed"""
    name: str
    url: str
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    poll_interval_minutes: int = Field(default=10, ge=1)


class RSSFeedUpdate(BaseModel):
    """Update payload for RSS feed configuration"""
    name: Optional[str] = None
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    poll_interval_minutes: Optional[int] = Field(default=None, ge=1)
    status: Optional[RSSFeedStatus] = None


class RSSFeedResponse(BaseModel):
    """Serialized RSS feed for API responses"""
    id: str
    name: str
    url: str
    categories: List[str]
    tags: List[str]
    poll_interval_minutes: int
    next_poll_at: Optional[datetime] = None
    last_polled_at: Optional[datetime] = None
    status: RSSFeedStatus
    error_streak: int
    health_score: float
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, feed: RSSFeed) -> "RSSFeedResponse":
        return cls(
            id=str(feed.id),
            name=feed.name,
            url=feed.url,
            categories=feed.categories,
            tags=feed.tags,
            poll_interval_minutes=feed.poll_interval_minutes,
            next_poll_at=feed.next_poll_at,
            last_polled_at=feed.last_polled_at,
            status=feed.status,
            error_streak=feed.error_streak,
            health_score=feed.health_score,
            last_error=feed.last_error,
            created_at=feed.created_at,
            updated_at=feed.updated_at,
        )


class RSSItem(MongoBaseModel):
    """Normalized RSS item persisted for retrieval"""
    feed_id: PyObjectId
    feed_url: str
    source_domain: str
    title: str
    summary: Optional[str] = None
    link: str
    guid: Optional[str] = None
    published_at: Optional[datetime] = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    dedupe_hash: str
    content_hash: Optional[str] = None
    price_amount: Optional[float] = None
    price_currency: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    product_refs: List[str] = Field(default_factory=list)
    summary_vec_minilm_384: Optional[List[float]] = None
    summary_vec_openai_1536: Optional[List[float]] = None
    coverage_score: Optional[float] = None


class RSSItemUpsert(BaseModel):
    """Helper model for inserting/updating RSS items"""
    feed_id: PyObjectId
    feed_url: str
    source_domain: str
    title: str
    summary: Optional[str] = None
    link: str
    guid: Optional[str] = None
    published_at: Optional[datetime] = None
    dedupe_hash: str
    content_hash: Optional[str] = None
    price_amount: Optional[float] = None
    price_currency: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    product_refs: List[str] = Field(default_factory=list)
    summary_vec_minilm_384: Optional[List[float]] = None
    summary_vec_openai_1536: Optional[List[float]] = None
    coverage_score: Optional[float] = None


# Search and Product Models for Persistence

class SearchRunStatus(str, Enum):
    """Search execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class SearchRun(MongoBaseModel):
    """Search run history and results"""
    user_id: Optional[PyObjectId] = None  # None for anonymous searches
    raw_query: str
    normalized_query: Optional[str] = None
    intent: Optional[str] = None
    
    # Execution metadata
    status: SearchRunStatus = SearchRunStatus.PENDING
    execution_time_ms: int = 0
    total_cost_usd: float = 0.0
    coverage_score: float = 0.0
    
    # Results
    results_count: int = 0
    results: List[Dict[str, Any]] = Field(default_factory=list)
    top_result_title: Optional[str] = None
    top_result_url: Optional[str] = None
    top_result_price: Optional[float] = None
    top_result_currency: Optional[str] = None
    top_result_score: Optional[float] = None

    # Agent execution tracking
    agent_steps: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    # Metadata
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class Product(MongoBaseModel):
    """Canonical product record (shared across users)"""
    title: str
    brand: Optional[str] = None
    model: Optional[str] = None
    category: Optional[str] = None
    
    # Specifications
    specs: Dict[str, Any] = Field(default_factory=dict)
    
    # Embeddings for search
    title_vec_openai_1536: Optional[List[float]] = None
    title_vec_minilm_384: Optional[List[float]] = None
    specs_vec_openai_1536: Optional[List[float]] = None
    specs_vec_minilm_384: Optional[List[float]] = None
    
    # Entity resolution
    aliases: List[str] = Field(default_factory=list)
    canonical_id: Optional[str] = None
    
    # Metadata
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

class ProductListing(MongoBaseModel):
    """Individual product offer/price"""
    product_id: PyObjectId
    
    # Source information
    url: str
    domain: str
    source_type: str = "tavily"  # "tavily", "rss", "manual"
    
    # Offer details
    price: Optional[float] = None
    currency: str = "USD"
    was_price: Optional[float] = None
    availability: Optional[str] = None
    
    # Seller information
    seller: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    
    # Metadata
    promo_text: Optional[str] = None
    delivery_eta: Optional[str] = None
    shipping_cost: Optional[float] = None
    credibility_score: float = 0.0
    content_hash: Optional[str] = None
    
    # Lifecycle
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)

class SearchRunResponse(BaseModel):
    """Search run response for API"""
    id: str
    user_id: Optional[str] = None
    raw_query: str
    intent: Optional[str] = None
    status: str
    execution_time_ms: int
    total_cost_usd: float
    coverage_score: float
    results_count: int
    created_at: datetime
    top_result_title: Optional[str] = None
    top_result_url: Optional[str] = None
    top_result_price: Optional[float] = None
    top_result_currency: Optional[str] = None
    top_result_score: Optional[float] = None
    results: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    @classmethod
    def from_model(cls, run: SearchRun) -> "SearchRunResponse":
        return cls(
            id=str(run.id),
            user_id=str(run.user_id) if run.user_id else None,
            raw_query=run.raw_query,
            intent=run.intent,
            status=run.status,
            execution_time_ms=run.execution_time_ms,
            total_cost_usd=run.total_cost_usd,
            coverage_score=run.coverage_score,
            results_count=run.results_count,
            created_at=run.created_at,
            top_result_title=run.top_result_title,
            top_result_url=run.top_result_url,
            top_result_price=run.top_result_price,
            top_result_currency=run.top_result_currency,
            top_result_score=run.top_result_score,
            results=run.results,
            warnings=run.warnings,
            errors=run.errors,
        )


class FavoriteProduct(MongoBaseModel):
    """User's favorite products"""
    user_id: PyObjectId  # Required - links to user
    
    # Product information (copied from search result)
    title: str
    brand: Optional[str] = None
    url: Optional[str] = None
    domain: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = "USD"
    image_url: Optional[str] = None
    
    # Product specifications and details
    specs: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None
    
    # Favoriting metadata
    original_search_query: Optional[str] = None  # What search led to this favorite
    search_run_id: Optional[PyObjectId] = None  # Original search run
    notes: Optional[str] = None  # User's personal notes
    tags: List[str] = Field(default_factory=list)  # User's custom tags
    
    # Tracking and alerts
    price_alert_enabled: bool = False
    price_alert_threshold: Optional[float] = None  # Alert when price drops below this
    availability_alert_enabled: bool = False
    
    # Metadata
    favorited_at: datetime = Field(default_factory=datetime.utcnow)
    last_checked: Optional[datetime] = None
    is_available: Optional[bool] = None


class FavoriteProductCreate(BaseModel):
    """Create favorite product request"""
    title: str
    brand: Optional[str] = None
    url: Optional[str] = None
    domain: Optional[str] = None
    price: Optional[float] = None
    currency: str = "USD"
    image_url: Optional[str] = None
    specs: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None
    original_search_query: Optional[str] = None
    search_run_id: Optional[str] = None  # String version for API
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    price_alert_enabled: bool = False
    price_alert_threshold: Optional[float] = None
    availability_alert_enabled: bool = False


class FavoriteProductUpdate(BaseModel):
    """Update favorite product request"""
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    price_alert_enabled: Optional[bool] = None
    price_alert_threshold: Optional[float] = None
    availability_alert_enabled: Optional[bool] = None


class FavoriteProductResponse(BaseModel):
    """Favorite product response for API"""
    id: str
    title: str
    brand: Optional[str] = None
    url: Optional[str] = None
    domain: Optional[str] = None
    price: Optional[float] = None
    currency: str = "USD"
    image_url: Optional[str] = None
    specs: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None
    original_search_query: Optional[str] = None
    search_run_id: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    price_alert_enabled: bool = False
    price_alert_threshold: Optional[float] = None
    availability_alert_enabled: bool = False
    favorited_at: datetime
    last_checked: Optional[datetime] = None
    is_available: Optional[bool] = None
    
    @classmethod
    def from_model(cls, favorite: FavoriteProduct) -> "FavoriteProductResponse":
        return cls(
            id=str(favorite.id),
            title=favorite.title,
            brand=favorite.brand,
            url=favorite.url,
            domain=favorite.domain,
            price=favorite.price,
            currency=favorite.currency,
            image_url=favorite.image_url,
            specs=favorite.specs,
            description=favorite.description,
            original_search_query=favorite.original_search_query,
            search_run_id=str(favorite.search_run_id) if favorite.search_run_id else None,
            notes=favorite.notes,
            tags=favorite.tags,
            price_alert_enabled=favorite.price_alert_enabled,
            price_alert_threshold=favorite.price_alert_threshold,
            availability_alert_enabled=favorite.availability_alert_enabled,
            favorited_at=favorite.favorited_at,
            last_checked=favorite.last_checked,
            is_available=favorite.is_available,
        )
