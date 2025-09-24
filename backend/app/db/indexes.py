"""Common MongoDB index management"""
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError, OperationFailure
from pymongo.asynchronous.database import AsyncDatabase
import logging

logger = logging.getLogger(__name__)


async def ensure_common_indexes(database: AsyncDatabase) -> None:
    """Create MongoDB indexes required by the application."""
    try:
        # Users
        await database.users.create_index("email", unique=True)

        # RSS feeds
        await database.rss_feeds.create_index("url", unique=True)
        await database.rss_feeds.create_index([("next_poll_at", ASCENDING)])
        await database.rss_feeds.create_index([("status", ASCENDING)])
        await database.rss_feeds.create_index([("categories", ASCENDING)])
        await database.rss_feeds.create_index([("error_streak", ASCENDING)])

        # RSS items
        await database.rss_items.create_index([("dedupe_hash", ASCENDING)], unique=True)
        await database.rss_items.create_index([("feed_id", ASCENDING), ("published_at", DESCENDING)])
        await database.rss_items.create_index([("published_at", DESCENDING)])
        await database.rss_items.create_index([("tags", ASCENDING), ("published_at", DESCENDING)])
        await database.rss_items.create_index([("categories", ASCENDING), ("published_at", DESCENDING)])

        # Search runs
        await database.search_runs.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        await database.search_runs.create_index([("created_at", DESCENDING)])  # For admin analytics
        await database.search_runs.create_index([("status", ASCENDING)])
        await database.search_runs.create_index([("raw_query", ASCENDING)])  # For query analysis

        # Products (shared collection)
        await database.products.create_index([("title", ASCENDING)])
        await database.products.create_index([("brand", ASCENDING), ("model", ASCENDING)])
        await database.products.create_index([("category", ASCENDING)])
        await database.products.create_index([("canonical_id", ASCENDING)])

        # Product listings
        await database.product_listings.create_index([("product_id", ASCENDING)])
        await database.product_listings.create_index([("url", ASCENDING)], unique=True)
        await database.product_listings.create_index([("domain", ASCENDING), ("price", ASCENDING)])
        await database.product_listings.create_index([("last_seen", DESCENDING)])

        # Sources (for audit trail)
        await database.sources.create_index([("url", ASCENDING)], unique=True)
        await database.sources.create_index([("domain", ASCENDING), ("credibility_score", DESCENDING)])
        await database.sources.create_index([("page_type", ASCENDING)])

        # Favorites (user-specific)
        await database.favorites.create_index([("user_id", ASCENDING), ("favorited_at", DESCENDING)])
        await database.favorites.create_index([("user_id", ASCENDING), ("url", ASCENDING)])  # Check duplicates
        await database.favorites.create_index([("user_id", ASCENDING), ("title", ASCENDING), ("brand", ASCENDING)])  # Alt duplicate check
        await database.favorites.create_index([("user_id", ASCENDING), ("tags", ASCENDING)])  # Filter by tags
        await database.favorites.create_index([("user_id", ASCENDING), ("price_alert_enabled", ASCENDING)])  # Price alerts
        await database.favorites.create_index([("price_alert_enabled", ASCENDING), ("price_alert_threshold", ASCENDING)])  # Global price monitoring

        logger.info("MongoDB indexes ensured successfully")
    except PyMongoError as exc:
        logger.error("Failed to ensure MongoDB indexes", exc_info=exc)
        raise


VECTOR_INDEX_DEFINITIONS = (
    {
        "name": "rss_summary_minilm_idx",
        "field": "summary_vec_minilm_384",
        "dimensions": 384,
        "similarity": "cosine",
    },
    {
        "name": "rss_summary_openai_idx",
        "field": "summary_vec_openai_1536",
        "dimensions": 1536,
        "similarity": "cosine",
    },
)


async def ensure_vector_search_indexes(database: AsyncDatabase) -> None:
    """Verify Atlas Search vector indexes for RSS retrieval.

    Note: Vector indexes should be created manually via MongoDB Compass or Atlas console.
    This function only verifies their existence for informational purposes.
    The RSS vector retriever gracefully degrades when indexes are not available.
    """

    try:
        existing = await database.command({"listSearchIndexes": "rss_items"})
        existing_names = {idx.get("name") for idx in existing.get("indexes", [])}
        
        # Check which indexes exist
        expected_indexes = {defn["name"] for defn in VECTOR_INDEX_DEFINITIONS}
        found_indexes = expected_indexes.intersection(existing_names)
        missing_indexes = expected_indexes - existing_names
        
        if found_indexes:
            logger.info(f"Found vector search indexes: {list(found_indexes)}")
        if missing_indexes:
            logger.warning(f"Missing vector search indexes: {list(missing_indexes)} - Create manually via MongoDB Compass")
            
    except OperationFailure:
        # Atlas Search not available - this is normal for local development or M0 clusters
        logger.info("Atlas Search not available - RSS vector search will use Tavily-only mode")
        logger.info("For vector search functionality, create indexes manually via MongoDB Compass")
        return
