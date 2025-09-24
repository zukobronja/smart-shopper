"""
V1 Health and system status endpoints
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
from app.config import settings

router = APIRouter(prefix="/v1", tags=["health"])

@router.get("/health")
async def health_check():
    """Detailed health check for V1 API"""
    return {
        "status": "healthy",
        "service": "smartshopper-api",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/health/workflow")
async def workflow_health_check():
    """Check if LangGraph workflow is properly initialized"""
    try:
        from app.agents.smart_shopper_workflow import get_workflow
        
        # Try to get the workflow instance
        workflow = get_workflow()
        
        # Check if agents are initialized
        agents_status = {
            "orchestrator": bool(workflow.orchestrator),
            "retriever": bool(workflow.retriever), 
            "rss_retriever": bool(workflow.rss_retriever),
            "credibility_filter": bool(workflow.credibility_filter),
            "spec_extractor": bool(workflow.spec_extractor),
            "ranker": bool(workflow.ranker),
            "graph_compiled": bool(workflow.app)
        }
        
        all_healthy = all(agents_status.values())
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "service": "langgraph-workflow",
            "agents": agents_status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "service": "langgraph-workflow", 
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }