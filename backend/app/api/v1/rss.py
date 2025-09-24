"""RSS admin and inspection endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional

from app.auth.dependencies import require_active_user
from app.db.models import (
    RSSFeedCreate,
    RSSFeedResponse,
    RSSFeedStatus,
    RSSFeedUpdate,
    User,
)
from app.rss import feed_service

router = APIRouter(prefix="/v1/rss", tags=["rss"])


@router.get("/feeds", response_model=List[RSSFeedResponse])
async def list_rss_feeds(
    status: Optional[RSSFeedStatus] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    _user: User = Depends(require_active_user),
):
    feeds = await feed_service.list_feeds(status=status, limit=limit)
    return feed_service.serialize_feeds(feeds)


@router.post("/feeds", response_model=RSSFeedResponse, status_code=status.HTTP_201_CREATED)
async def create_rss_feed(
    payload: RSSFeedCreate,
    _user: User = Depends(require_active_user),
):
    try:
        feed = await feed_service.create_feed(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return feed_service.serialize_feed(feed)


@router.patch("/feeds/{feed_id}", response_model=RSSFeedResponse)
async def update_rss_feed(
    feed_id: str,
    payload: RSSFeedUpdate,
    _user: User = Depends(require_active_user),
):
    try:
        feed = await feed_service.update_feed(feed_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return feed_service.serialize_feed(feed)


@router.delete("/feeds/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rss_feed(
    feed_id: str,
    _user: User = Depends(require_active_user),
):
    try:
        await feed_service.delete_feed(feed_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return None
