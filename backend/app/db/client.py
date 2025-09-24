"""
MongoDB client using async pymongo with AWS EB compatibility
"""
from pymongo.asynchronous.mongo_client import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from app.config import settings
from app.db.indexes import ensure_common_indexes, ensure_vector_search_indexes
import logging
import ssl
import os

logger = logging.getLogger(__name__)

class MongoClient:
    client: AsyncMongoClient = None
    database: AsyncDatabase = None

mongo_client = MongoClient()

def create_aws_compatible_ssl_context():
    """Create SSL context compatible with AWS Elastic Beanstalk"""
    try:
        # Create SSL context with maximum AWS EB compatibility
        ssl_context = ssl.create_default_context()
        
        # Disable all SSL verification for AWS EB compatibility
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Allow weak protocols and ciphers for maximum compatibility
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.maximum_version = ssl.TLSVersion.TLSv1_3
        
        # Set the most permissive cipher suites
        try:
            ssl_context.set_ciphers('ALL:!aNULL:!eNULL')
        except ssl.SSLError:
            # Fallback to default ciphers if the above fails
            logger.warning("Failed to set permissive ciphers, using defaults")
        
        # Disable certificate revocation checks
        ssl_context.check_hostname = False
        
        logger.info("Created AWS EB compatible SSL context")
        return ssl_context
    except Exception as e:
        logger.warning(f"Failed to create custom SSL context: {e}")
        return None

async def connect_to_mongo():
    """Create database connection with AWS EB SSL compatibility"""
    logger.info("Connecting to MongoDB...")
    
    # Detect if we're in AWS EB environment (multiple detection methods)
    is_aws_eb = (
        os.getenv('ENVIRONMENT', '').lower() == 'production' or 
        os.path.exists('/opt/elasticbeanstalk') or 
        os.path.exists('/var/app') or
        'elasticbeanstalk' in os.getenv('PATH', '').lower()
    )
    
    logger.info(f"Environment detection - ENVIRONMENT: {os.getenv('ENVIRONMENT')}, AWS EB detected: {is_aws_eb}")
    
    if is_aws_eb:
        logger.info("AWS EB environment detected - using maximum SSL compatibility mode")
        
    connection_attempts = [
        # Attempt 1: AWS EB compatible - completely bypass SSL verification
        {
            "name": "AWS EB Compatible (No SSL Verification)",
            "params": {
                "tls": True,
                "tlsInsecure": True,
                "tlsAllowInvalidCertificates": True,
                "tlsAllowInvalidHostnames": True,
                "tlsDisableOCSPEndpointCheck": True,
                "serverSelectionTimeoutMS": 45000,
                "socketTimeoutMS": 45000,
                "connectTimeoutMS": 45000,
                "maxIdleTimeMS": 60000,
                "retryWrites": True,
                "retryReads": True
            }
        },
        # Attempt 2: AWS EB with basic SSL bypass
        {
            "name": "AWS EB Basic SSL Bypass",
            "params": {
                "tls": True,
                "tlsAllowInvalidCertificates": True,
                "tlsAllowInvalidHostnames": True,
                "serverSelectionTimeoutMS": 60000,
                "socketTimeoutMS": 60000,
                "connectTimeoutMS": 60000,
                "retryWrites": True,
                "retryReads": True
            }
        },
        # Attempt 3: Standard SSL with longer timeouts
        {
            "name": "Standard SSL Extended Timeouts",
            "params": {
                "tls": True,
                "serverSelectionTimeoutMS": 90000,
                "socketTimeoutMS": 90000,
                "connectTimeoutMS": 90000,
                "retryWrites": True
            }
        },
        # Attempt 4: Try regular mongodb:// instead of mongodb+srv://
        {
            "name": "Regular MongoDB Protocol",
            "params": {
                "tls": True,
                "tlsAllowInvalidCertificates": True,
                "serverSelectionTimeoutMS": 45000,
                "socketTimeoutMS": 45000,
                "connectTimeoutMS": 45000,
                "retryWrites": True
            },
            "custom_url": True  # This will modify the URL
        },
        # Attempt 5: Connection string with SSL parameters inline
        {
            "name": "Inline SSL Parameters",
            "params": {
                "serverSelectionTimeoutMS": 45000,
                "socketTimeoutMS": 45000,
                "connectTimeoutMS": 45000
            },
            "inline_ssl_url": True  # This will add SSL params to URL
        }
    ]
    
    last_error = None
    
    for i, attempt in enumerate(connection_attempts, 1):
        if i > 2 and not is_aws_eb and settings.ENVIRONMENT != "development":
            # Skip insecure attempts in non-AWS, non-development environments
            continue
            
        try:
            logger.info(f"Connection attempt {i}: {attempt['name']}")
            
            # Close existing connection if any
            if mongo_client.client:
                await mongo_client.client.close()
            
            # Determine connection URL
            connection_url = settings.mongodb_url
            if attempt.get('custom_url') and 'mongodb+srv://' in connection_url:
                # Convert mongodb+srv to regular mongodb for this attempt
                connection_url = connection_url.replace('mongodb+srv://', 'mongodb://')
                connection_url = connection_url.replace(':27017', '')  # Remove port from SRV
                if ':27017' not in connection_url:
                    connection_url = connection_url.replace('@', ':27017/@')  # Add default port
                logger.info(f"Using custom URL format: mongodb://...")
            elif attempt.get('inline_ssl_url'):
                # Add SSL parameters directly to the URL
                ssl_params = "&tls=true&tlsAllowInvalidCertificates=true&tlsAllowInvalidHostnames=true&tlsInsecure=true"
                if '?' in connection_url:
                    connection_url += ssl_params
                else:
                    connection_url += '?' + ssl_params[1:]  # Remove first &
                logger.info(f"Using inline SSL parameters in URL")
            
            # Create new connection
            params = attempt['params'].copy()
            params.pop('custom_url', None)  # Remove non-MongoDB parameters
            params.pop('inline_ssl_url', None)
            
            mongo_client.client = AsyncMongoClient(
                connection_url,
                **params
            )
            mongo_client.database = mongo_client.client[settings.DATABASE_NAME]
            
            # Test connection
            await mongo_client.client.admin.command('ping')
            logger.info(f"Successfully connected to MongoDB using: {attempt['name']}")
            break
            
        except Exception as e:
            logger.warning(f"Connection attempt {i} failed ({attempt['name']}): {str(e)[:200]}...")
            last_error = e
            
            # Add specific handling for SSL errors
            if "SSL" in str(e) or "TLS" in str(e):
                logger.error(f"SSL/TLS Error detected in attempt {i}. This is common in AWS EB environments.")
            
            continue
    else:
        # All attempts failed
        logger.error(f"All MongoDB connection attempts failed. Last error: {last_error}")
        raise last_error
    
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
