"""RSS feed registry persistence helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from bson import ObjectId

from app.config import settings
from app.db.client import mongo_client
from app.db.models import (
    RSSFeed,
    RSSFeedCreate,
    RSSFeedResponse,
    RSSFeedStatus,
    RSSFeedUpdate,
)


def _ensure_connection():
    if mongo_client.database is None:
        raise RuntimeError("MongoDB not initialized. Call connect_to_mongo() first.")


def _calculate_next_poll(interval_minutes: int) -> datetime:
    now = datetime.now(timezone.utc)
    return now + timedelta(minutes=interval_minutes)


async def list_feeds(
    *,
    status: Optional[RSSFeedStatus] = None,
    limit: int = 50,
) -> List[RSSFeed]:
    """Return registered feeds sorted by next poll time."""
    _ensure_connection()
    query = {}
    if status:
        query["status"] = status.value

    cursor = (
        mongo_client.database.rss_feeds
        .find(query)
        .sort("next_poll_at", 1)
        .limit(limit)
    )
    feeds = []
    async for doc in cursor:
        # Convert ObjectId to string for Pydantic
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        feeds.append(RSSFeed(**doc))
    return feeds


async def create_feed(payload: RSSFeedCreate) -> RSSFeed:
    """Register a new RSS feed. Raises ValueError if URL already exists."""
    _ensure_connection()

    existing = await mongo_client.database.rss_feeds.find_one({"url": payload.url})
    if existing:
        raise ValueError("Feed with this URL already exists")

    interval = payload.poll_interval_minutes or settings.RSS_DEFAULT_POLL_MINUTES
    now = datetime.now(timezone.utc)
    doc = {
        "name": payload.name,
        "url": payload.url,
        "categories": payload.categories,
        "tags": payload.tags,
        "poll_interval_minutes": interval,
        "next_poll_at": now,
        "last_polled_at": None,
        "etag": None,
        "last_modified": None,
        "status": RSSFeedStatus.ACTIVE.value,
        "error_streak": 0,
        "health_score": 1.0,
        "last_error": None,
        "created_at": now,
        "updated_at": now,
    }

    result = await mongo_client.database.rss_feeds.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return RSSFeed(**doc)


async def update_feed(feed_id: str, payload: RSSFeedUpdate) -> RSSFeed:
    """Update feed metadata/settings."""
    _ensure_connection()
    if not ObjectId.is_valid(feed_id):
        raise ValueError("Invalid feed id")

    update_doc = {}
    if payload.name is not None:
        update_doc["name"] = payload.name
    if payload.categories is not None:
        update_doc["categories"] = payload.categories
    if payload.tags is not None:
        update_doc["tags"] = payload.tags
    if payload.poll_interval_minutes is not None:
        update_doc["poll_interval_minutes"] = payload.poll_interval_minutes
        update_doc["next_poll_at"] = _calculate_next_poll(payload.poll_interval_minutes)
    if payload.status is not None:
        update_doc["status"] = payload.status.value

    if not update_doc:
        raise ValueError("Nothing to update")

    update_doc["updated_at"] = datetime.now(timezone.utc)

    result = await mongo_client.database.rss_feeds.find_one_and_update(
        {"_id": ObjectId(feed_id)},
        {"$set": update_doc},
        return_document=True,
    )
    if not result:
        raise ValueError("Feed not found")
    result["_id"] = str(result["_id"])
    return RSSFeed(**result)


async def delete_feed(feed_id: str) -> None:
    """Delete a feed and leave existing items intact."""
    _ensure_connection()
    if not ObjectId.is_valid(feed_id):
        raise ValueError("Invalid feed id")

    await mongo_client.database.rss_feeds.delete_one({"_id": ObjectId(feed_id)})


def serialize_feeds(feeds: List[RSSFeed]) -> List[RSSFeedResponse]:
    """Helper to produce API responses."""
    return [RSSFeedResponse.from_model(feed) for feed in feeds]


def serialize_feed(feed: RSSFeed) -> RSSFeedResponse:
    return RSSFeedResponse.from_model(feed)
