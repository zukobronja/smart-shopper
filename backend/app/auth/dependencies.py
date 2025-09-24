"""
FastAPI authentication dependencies
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from app.auth.security import verify_token
from app.db.client import mongo_client
from app.db.models import User, UserStatus
from bson import ObjectId

security = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """
    Get current user from JWT token in Authorization header or cookies
    Returns None if no valid token found (for optional authentication)
    """
    token = None
    
    # Try Authorization header first
    if credentials:
        token = credentials.credentials
    else:
        # Try cookies
        token = request.cookies.get("access_token")
    
    if not token:
        return None
    
    # Verify token
    payload = verify_token(token, "access")
    if not payload:
        return None
    
    # Get user from database
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    try:
        user_doc = await mongo_client.database.users.find_one({"_id": ObjectId(user_id)})
        if not user_doc:
            return None
        
        # Convert ObjectId to string for Pydantic compatibility
        user_doc["_id"] = str(user_doc["_id"])
        return User(**user_doc)
    except Exception:
        return None

async def require_user(current_user: Optional[User] = Depends(get_current_user)) -> User:
    """
    Require authenticated user (raises 401 if not authenticated)
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user

async def require_active_user(current_user: User = Depends(require_user)) -> User:
    """Require active user (raises 403 if user is not active)."""
    status_value = current_user.status
    if isinstance(status_value, UserStatus):
        status_value = status_value.value

    if status_value != UserStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not active"
        )
    return current_user
