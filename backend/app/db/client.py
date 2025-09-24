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
    """Create database connection with SSL fallback handling"""
    logger.info("Connecting to MongoDB...")
    
    # First attempt: Full SSL configuration for AWS compatibility
    try:
        mongo_client.client = AsyncMongoClient(
            settings.mongodb_url,
            tls=True,
            tlsCAFile='/etc/ssl/certs/ca-certificates.crt',
            serverSelectionTimeoutMS=30000,
            socketTimeoutMS=20000,
            connectTimeoutMS=20000,
            maxIdleTimeMS=45000,
            heartbeatFrequencyMS=10000,
            retryWrites=True
        )
        mongo_client.database = mongo_client.client[settings.DATABASE_NAME]
        
        # Test connection
        await mongo_client.client.admin.command('ping')
        logger.info("Successfully connected to MongoDB with full SSL configuration")
        
    except Exception as ssl_error:
        logger.warning(f"Full SSL connection failed: {ssl_error}")
        logger.info("Attempting fallback connection with minimal SSL settings...")
        
        # Fallback attempt: Minimal SSL configuration
        try:
            if mongo_client.client:
                await mongo_client.client.close()
                
            mongo_client.client = AsyncMongoClient(
                settings.mongodb_url,
                tls=True,
                serverSelectionTimeoutMS=30000,
                socketTimeoutMS=20000,
                connectTimeoutMS=20000,
                retryWrites=True
            )
            mongo_client.database = mongo_client.client[settings.DATABASE_NAME]
            
            # Test connection
            await mongo_client.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB with fallback SSL configuration")
            
        except Exception as fallback_error:
            logger.error(f"Both SSL connection attempts failed. Full SSL error: {ssl_error}, Fallback error: {fallback_error}")
            raise fallback_error
    
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
