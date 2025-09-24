"""
MongoDB client using async pymongo
"""
from pymongo.asynchronous.mongo_client import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from app.config import settings
from app.db.indexes import ensure_common_indexes, ensure_vector_search_indexes
import logging

logger = logging.getLogger(__name__)

class MongoClient:
    client: AsyncMongoClient = None
    database: AsyncDatabase = None

mongo_client = MongoClient()

async def connect_to_mongo():
    """Create database connection"""
    logger.info("Connecting to MongoDB...")
    mongo_client.client = AsyncMongoClient(settings.mongodb_url)
    mongo_client.database = mongo_client.client[settings.DATABASE_NAME]
    
    # Test connection
    try:
        await mongo_client.client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")

        # Ensure required indexes exist
        await ensure_common_indexes(mongo_client.database)
        
        # Verify vector search indexes for RSS functionality
        await ensure_vector_search_indexes(mongo_client.database)
        
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise

async def close_mongo_connection():
    """Close database connection"""
    logger.info("Closing MongoDB connection...")
    if mongo_client.client:
        await mongo_client.client.close()
