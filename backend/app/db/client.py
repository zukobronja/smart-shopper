"""
MongoDB client using async pymongo with AWS EB compatibility
Uses proven certifi approach from working AWS Beanstalk demo
"""
from pymongo.asynchronous.mongo_client import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from app.config import settings
from app.db.indexes import ensure_common_indexes, ensure_vector_search_indexes
import logging
import certifi

logger = logging.getLogger(__name__)

class MongoClient:
    client: AsyncMongoClient = None
    database: AsyncDatabase = None

mongo_client = MongoClient()

async def connect_to_mongo():
    """Simple, reliable MongoDB connection using proven certifi approach"""
    logger.info("Connecting to MongoDB...")
    
    try:
        # Use the proven approach from working AWS Beanstalk demo
        # Simple TLS connection with certifi CA certificates
        mongo_client.client = AsyncMongoClient(
            settings.mongodb_url,
            tls=True,
            tlsCAFile=certifi.where(),  # Use certifi CA bundle - this is the key!
            serverSelectionTimeoutMS=30000,
            socketTimeoutMS=20000,
            connectTimeoutMS=20000,
            retryWrites=True
        )
        
        mongo_client.database = mongo_client.client[settings.DATABASE_NAME]
        
        # Test connection with ping
        await mongo_client.client.admin.command('ping')
        logger.info("✅ MongoDB connection successful using certifi CA bundle")
        
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        # Log the MongoDB URL pattern (without credentials) for debugging
        url_pattern = settings.mongodb_url.split('@')[1] if '@' in settings.mongodb_url else settings.mongodb_url
        logger.error(f"Connection URL pattern: mongodb://***@{url_pattern}")
        raise
    
    try:
        # Ensure required indexes exist
        await ensure_common_indexes(mongo_client.database)
        
        # Verify vector search indexes for RSS functionality
        await ensure_vector_search_indexes(mongo_client.database)
        
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

async def close_mongo_connection():
    """Close database connection"""
    logger.info("Closing MongoDB connection...")
    if mongo_client.client:
        await mongo_client.client.close()
