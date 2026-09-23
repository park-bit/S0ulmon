import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from src.utils.logger import logger

_client = None

def get_db():
    """Get the MongoDB database instance."""
    global _client
    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        logger.error("MONGO_URI environment variable is missing.")
        raise ValueError("MONGO_URI is required.")
        
    if _client is None:
        try:
            _client = MongoClient(mongo_uri)
            # Ping to verify connection
            _client.admin.command('ping')
            logger.info("Successfully connected to MongoDB.")
        except ConnectionFailure as e:
            logger.error(f"Could not connect to MongoDB: {e}")
            raise
            
    # Assuming the default db is extracted from the URI or we use a fallback name
    # We will use a database named 'solar_monitor'
    db = _client.get_database("solar_monitor")
    return db

def init_db():
    """Initialize database indexes if they don't exist."""
    try:
        db = get_db()
        # Ensure emails are unique
        db.users.create_index("email", unique=True)
        logger.info("MongoDB indexes verified.")
    except Exception as e:
        logger.error(f"Failed to initialize database indexes: {e}")

if __name__ == "__main__":
    init_db()
