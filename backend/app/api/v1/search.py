"""
V1 Search API endpoints
"""
import time
from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.auth.dependencies import get_current_user
from app.db.models import User, SearchRun, SearchRunStatus, SearchRunResponse
from app.db.client import mongo_client
from app.agents.smart_shopper_workflow import execute_search_workflow

router = APIRouter(prefix="/v1", tags=["search"])

class SearchRequest(BaseModel):
    """Search request model"""
    query: str = Field(..., min_length=2, max_length=500, description="Search query")
    max_results: Optional[int] = Field(10, ge=1, le=50, description="Maximum number of results")
    price_min: Optional[float] = Field(None, ge=0, description="Minimum price filter")
    price_max: Optional[float] = Field(None, ge=0, description="Maximum price filter")
    categories: Optional[List[str]] = Field(None, description="Category filters")

class ProductResult(BaseModel):
    """Individual product result"""
    title: str
    brand: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    url: Optional[str] = None
    domain: Optional[str] = None
    specs: Dict[str, Any] = Field(default_factory=dict)
    final_score: float = 0.0
    explanation: Optional[str] = None
    credibility_score: float = 0.0

class ExecutionMetrics(BaseModel):
    """Execution performance metrics"""
    total_time_ms: int
    agent_steps: List[Dict[str, Any]]
    total_cost_usd: float
    coverage_score: float

class SearchResponse(BaseModel):
    """Search response model"""
    run_id: str
    query: str
    intent: Optional[str] = None
    results: List[ProductResult]
    results_count: int
    execution_metrics: ExecutionMetrics
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

@router.post("/search", response_model=SearchResponse)
async def search_products(
    request: SearchRequest,
    req: Request,
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Product search endpoint integrated with LangGraph workflow
    
    Executes the complete 5-agent SmartShopper pipeline:
    QueryOrchestrator → TavilyRetriever → CredibilityFilter → SpecExtractor → ResultsRanker
    """
    start_time = time.time()
    
    # Basic validation
    if not request.query or len(request.query.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query must be at least 2 characters long"
        )
    
    # Create initial search run record
    search_run = SearchRun(
        user_id=str(current_user.id) if current_user else None,
        raw_query=request.query.strip(),
        status=SearchRunStatus.RUNNING,
        ip_address=req.client.host if req.client else None,
        user_agent=req.headers.get("user-agent")
    )
    
    try:
        # Save initial search run to database
        result = await mongo_client.database.search_runs.insert_one(search_run.model_dump(by_alias=True))
        search_run_id = str(result.inserted_id)
        
        # Get user ID if authenticated
        user_id = str(current_user.id) if current_user else None
        
        # Execute the LangGraph workflow
        final_state = await execute_search_workflow(
            raw_query=request.query.strip(),
            user_id=user_id
        )
        
        # Transform workflow results to API response format
        products = []
        for product in final_state.get("ranked_products", []):
            products.append(ProductResult(
                title=product.get("title", "Unknown Product"),
                brand=product.get("brand"),
                price=product.get("price"),
                currency=product.get("currency", "USD"),
                url=product.get("url"),
                domain=product.get("domain"),
                specs=product.get("specs", {}),
                final_score=product.get("final_score", 0.0),
                explanation=product.get("explanation"),
                credibility_score=product.get("credibility_score", 0.0)
            ))
        
        # Limit results based on request
        if request.max_results:
            products = products[:request.max_results]
        
        # Apply price filters if specified
        if request.price_min is not None or request.price_max is not None:
            filtered_products = []
            for product in products:
                if product.price is not None:
                    if request.price_min is not None and product.price < request.price_min:
                        continue
                    if request.price_max is not None and product.price > request.price_max:
                        continue
                filtered_products.append(product)
            products = filtered_products
        
        # Build execution metrics
        execution_metrics = ExecutionMetrics(
            total_time_ms=final_state.get("execution_time_ms", int((time.time() - start_time) * 1000)),
            agent_steps=[step.model_dump() if hasattr(step, 'model_dump') else step for step in final_state.get("agent_steps", [])],
            total_cost_usd=final_state.get("total_cost_usd", 0.0),
            coverage_score=final_state.get("coverage_score", 0.0)
        )
        
        # Extract intent from search query if available
        search_query = final_state.get("search_query")
        intent = search_query.intent if search_query else None
        
        # Update search run in database with results
        top_product = products[0] if products else None
        await mongo_client.database.search_runs.update_one(
            {"_id": result.inserted_id},
            {
                "$set": {
                    "status": SearchRunStatus.COMPLETED,
                    "normalized_query": search_query.normalized_query if search_query else None,
                    "intent": intent,
                    "execution_time_ms": execution_metrics.total_time_ms,
                    "total_cost_usd": execution_metrics.total_cost_usd,
                    "coverage_score": execution_metrics.coverage_score,
                    "results_count": len(products),
                    "results": [product.model_dump() for product in products],
                    "agent_steps": execution_metrics.agent_steps,
                    "errors": final_state.get("errors", []),
                    "warnings": final_state.get("warnings", []),
                    "top_result_title": top_product.title if top_product else None,
                    "top_result_url": top_product.url if top_product else None,
                    "top_result_price": top_product.price if top_product else None,
                    "top_result_currency": top_product.currency if top_product else None,
                    "top_result_score": top_product.final_score if top_product else None,
                }
            }
        )
        
        # Update user search count if authenticated
        if current_user:
            await mongo_client.database.users.update_one(
                {"_id": current_user.id},
                {"$inc": {"total_searches": 1}}
            )
        
        return SearchResponse(
            run_id=search_run_id,
            query=request.query,
            intent=intent,
            results=products,
            results_count=len(products),
            execution_metrics=execution_metrics,
            errors=final_state.get("errors", []),
            warnings=final_state.get("warnings", [])
        )
        
    except Exception as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Search workflow failed: {str(e)}", exc_info=True)
        
        # Update search run with error status if we have the ID
        if 'result' in locals():
            await mongo_client.database.search_runs.update_one(
                {"_id": result.inserted_id},
                {
                    "$set": {
                        "status": SearchRunStatus.FAILED,
                        "execution_time_ms": int((time.time() - start_time) * 1000),
                        "errors": [str(e)]
                    }
                }
            )
        
        # Return error response
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search workflow failed: {str(e)}"
        )

@router.get("/search/history", response_model=List[SearchRunResponse])
async def get_search_history(
    current_user: User = Depends(get_current_user),
    limit: int = 20,
    skip: int = 0
):
    """
    Get user's search history
    Requires authentication
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Query user's search runs
    cursor = mongo_client.database.search_runs.find(
        {"user_id": str(current_user.id)}
    ).sort("created_at", -1).skip(skip).limit(limit)
    
    search_runs = []
    async for doc in cursor:
        search_run = SearchRun(**doc)
        search_runs.append(SearchRunResponse.from_model(search_run))
    
    return search_runs

@router.get("/search/{run_id}", response_model=SearchResponse)
async def get_search_run(
    run_id: str,
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Get details of a specific search run
    Public endpoint for anonymous searches, authentication required for user searches
    """
    from bson import ObjectId
    
    try:
        object_id = ObjectId(run_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid run ID format"
        )
    
    # Find the search run
    doc = await mongo_client.database.search_runs.find_one({"_id": object_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search run not found"
        )
    
    search_run = SearchRun(**doc)
    
    # Check authorization - user searches require authentication
    if search_run.user_id and (not current_user or search_run.user_id != str(current_user.id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Convert to response format
    products = []
    for result_data in search_run.results:
        products.append(ProductResult(**result_data))
    
    execution_metrics = ExecutionMetrics(
        total_time_ms=search_run.execution_time_ms,
        agent_steps=search_run.agent_steps,
        total_cost_usd=search_run.total_cost_usd,
        coverage_score=search_run.coverage_score
    )
    
    return SearchResponse(
        run_id=str(search_run.id),
        query=search_run.raw_query,
        intent=search_run.intent,
        results=products,
        results_count=search_run.results_count,
        execution_metrics=execution_metrics,
        errors=search_run.errors,
        warnings=search_run.warnings
    )