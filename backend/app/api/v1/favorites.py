"""
V1 Favorites API endpoints
"""
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends, Query
from bson import ObjectId
import logging
from pydantic import ValidationError
from app.auth.dependencies import require_user
from app.db.models import (
    User, 
    FavoriteProduct, 
    FavoriteProductCreate, 
    FavoriteProductUpdate, 
    FavoriteProductResponse
)
from app.db.client import mongo_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/favorites", tags=["favorites"])

@router.get("", response_model=List[FavoriteProductResponse])
async def get_user_favorites(
    current_user: User = Depends(require_user),
    limit: int = Query(20, ge=1, le=100, description="Number of favorites to return"),
    skip: int = Query(0, ge=0, description="Number of favorites to skip"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)")
):
    """
    Get user's favorite products with optional filtering
    """
    query_filter = {"user_id": ObjectId(current_user.id)}
    
    # Add tag filtering if provided
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        if tag_list:
            query_filter["tags"] = {"$in": tag_list}
    
    # Query favorites
    cursor = mongo_client.database.favorites.find(query_filter).sort("favorited_at", -1).skip(skip).limit(limit)
    
    favorites = []
    async for doc in cursor:
        # Convert ObjectIds to strings for Pydantic compatibility
        doc["_id"] = str(doc["_id"])
        doc["user_id"] = str(doc["user_id"])
        if doc.get("search_run_id"):
            doc["search_run_id"] = str(doc["search_run_id"])
        
        favorite = FavoriteProduct(**doc)
        favorites.append(FavoriteProductResponse.from_model(favorite))
    
    return favorites

@router.post("", response_model=FavoriteProductResponse, status_code=status.HTTP_201_CREATED)
async def create_favorite(
    favorite_data: FavoriteProductCreate,
    current_user: User = Depends(require_user)
):
    """
    Add a product to user's favorites
    """
    try:
        logger.info(f"Creating favorite for user {current_user.id}")
        logger.info(f"Favorite data received: {favorite_data.model_dump()}")
        
        # Check if product is already favorited (based on URL or title+brand)
        existing_query = {"user_id": ObjectId(current_user.id)}
        
        if favorite_data.url:
            existing_query["url"] = favorite_data.url
        else:
            # If no URL, check by title and brand combination
            existing_query["title"] = favorite_data.title
            if favorite_data.brand:
                existing_query["brand"] = favorite_data.brand
        
        existing_favorite = await mongo_client.database.favorites.find_one(existing_query)
        if existing_favorite:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Product already in favorites"
            )
        
        # Create favorite document
        favorite_doc = {
            "user_id": ObjectId(current_user.id),
            "title": favorite_data.title,
            "brand": favorite_data.brand,
            "url": favorite_data.url,
            "domain": favorite_data.domain,
            "price": favorite_data.price,
            "currency": favorite_data.currency,
            "image_url": favorite_data.image_url,
            "specs": favorite_data.specs,
            "description": favorite_data.description,
            "original_search_query": favorite_data.original_search_query,
            "search_run_id": ObjectId(favorite_data.search_run_id) if favorite_data.search_run_id else None,
            "notes": favorite_data.notes,
            "tags": favorite_data.tags,
            "price_alert_enabled": favorite_data.price_alert_enabled,
            "price_alert_threshold": favorite_data.price_alert_threshold,
            "availability_alert_enabled": favorite_data.availability_alert_enabled,
        }
        
        logger.info(f"Favorite document to insert: {favorite_doc}")
        
        # Insert into database
        result = await mongo_client.database.favorites.insert_one(favorite_doc)
        favorite_doc["_id"] = result.inserted_id
        
        logger.info(f"Favorite inserted with ID: {result.inserted_id}")
        
        # Convert ObjectIds to strings for Pydantic compatibility
        favorite_doc["_id"] = str(favorite_doc["_id"])
        favorite_doc["user_id"] = str(favorite_doc["user_id"])
        if favorite_doc["search_run_id"]:
            favorite_doc["search_run_id"] = str(favorite_doc["search_run_id"])
        
        favorite = FavoriteProduct(**favorite_doc)
        return FavoriteProductResponse.from_model(favorite)
        
    except ValidationError as e:
        logger.error(f"Validation error creating favorite: {e}")
        logger.error(f"Validation errors: {e.errors()}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {e.errors()}"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating favorite: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create favorite"
        )

@router.get("/{favorite_id}", response_model=FavoriteProductResponse)
async def get_favorite(
    favorite_id: str,
    current_user: User = Depends(require_user)
):
    """
    Get a specific favorite by ID
    """
    try:
        object_id = ObjectId(favorite_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid favorite ID format"
        )
    
    # Find favorite and verify ownership
    doc = await mongo_client.database.favorites.find_one({
        "_id": object_id,
        "user_id": ObjectId(current_user.id)
    })
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found"
        )
    
    # Convert ObjectIds to strings for Pydantic compatibility
    doc["_id"] = str(doc["_id"])
    doc["user_id"] = str(doc["user_id"])
    if doc.get("search_run_id"):
        doc["search_run_id"] = str(doc["search_run_id"])
    
    favorite = FavoriteProduct(**doc)
    return FavoriteProductResponse.from_model(favorite)

@router.put("/{favorite_id}", response_model=FavoriteProductResponse)
async def update_favorite(
    favorite_id: str,
    update_data: FavoriteProductUpdate,
    current_user: User = Depends(require_user)
):
    """
    Update a favorite product's metadata (notes, tags, alerts)
    """
    try:
        object_id = ObjectId(favorite_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid favorite ID format"
        )
    
    # Build update document
    update_doc = {}
    if update_data.notes is not None:
        update_doc["notes"] = update_data.notes
    if update_data.tags is not None:
        update_doc["tags"] = update_data.tags
    if update_data.price_alert_enabled is not None:
        update_doc["price_alert_enabled"] = update_data.price_alert_enabled
    if update_data.price_alert_threshold is not None:
        update_doc["price_alert_threshold"] = update_data.price_alert_threshold
    if update_data.availability_alert_enabled is not None:
        update_doc["availability_alert_enabled"] = update_data.availability_alert_enabled
    
    if not update_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No update data provided"
        )
    
    update_doc["updated_at"] = datetime.now(timezone.utc)
    
    # Update favorite and verify ownership
    result = await mongo_client.database.favorites.update_one(
        {"_id": object_id, "user_id": ObjectId(current_user.id)},
        {"$set": update_doc}
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found"
        )
    
    # Return updated favorite
    doc = await mongo_client.database.favorites.find_one({
        "_id": object_id,
        "user_id": ObjectId(current_user.id)
    })
    
    # Convert ObjectIds to strings for Pydantic compatibility
    doc["_id"] = str(doc["_id"])
    doc["user_id"] = str(doc["user_id"])
    if doc.get("search_run_id"):
        doc["search_run_id"] = str(doc["search_run_id"])
    
    favorite = FavoriteProduct(**doc)
    return FavoriteProductResponse.from_model(favorite)

@router.delete("/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_favorite(
    favorite_id: str,
    current_user: User = Depends(require_user)
):
    """
    Remove a product from user's favorites
    """
    try:
        object_id = ObjectId(favorite_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid favorite ID format"
        )
    
    # Delete favorite and verify ownership
    result = await mongo_client.database.favorites.delete_one({
        "_id": object_id,
        "user_id": ObjectId(current_user.id)
    })
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found"
        )

@router.get("/check/{url_hash}", response_model=dict)
async def check_favorite_status(
    url_hash: str,
    current_user: User = Depends(require_user)
):
    """
    Check if a product (by URL hash) is already favorited
    Used by frontend to show favorite status on search results
    """
    # For now, we'll check by URL directly
    # In production, you might want to hash URLs for privacy
    existing = await mongo_client.database.favorites.find_one({
        "user_id": ObjectId(current_user.id),
        "url": {"$regex": url_hash}
    })
    
    return {
        "is_favorited": existing is not None,
        "favorite_id": str(existing["_id"]) if existing else None
    }

@router.get("/tags", response_model=List[str])
async def get_user_favorite_tags(
    current_user: User = Depends(require_user)
):
    """
    Get all unique tags used in user's favorites
    """
    try:
        logger.info(f"Getting favorite tags for user {current_user.id}")
        
        # First check if user has any favorites at all
        favorites_count = await mongo_client.database.favorites.count_documents({
            "user_id": ObjectId(current_user.id)
        })
        
        logger.info(f"User has {favorites_count} favorites")
        
        if favorites_count == 0:
            logger.info("No favorites found, returning empty tags list")
            return []
        
        # Use simpler approach: get all favorites and extract unique tags
        cursor = mongo_client.database.favorites.find(
            {"user_id": ObjectId(current_user.id)},
            {"tags": 1}  # Only fetch tags field
        )
        
        all_tags = set()
        async for doc in cursor:
            if doc.get("tags") and isinstance(doc["tags"], list):
                for tag in doc["tags"]:
                    if tag and isinstance(tag, str) and tag.strip():
                        all_tags.add(tag.strip())
        
        tags_list = sorted(list(all_tags))
        logger.info(f"Found {len(tags_list)} unique tags: {tags_list}")
        
        return tags_list
        
    except Exception as e:
        logger.error(f"Error getting favorite tags: {e}")
        return []  # Return empty list if any error occurs