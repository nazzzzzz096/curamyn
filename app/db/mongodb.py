"""
MongoDB connection utilities.

Provides a centralized MongoDB client and collection accessor.
"""

import os
from typing import Any
import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

load_dotenv()

MONGO_URI = os.getenv("CURAMYN_MONGO_URI")
MONGO_DB = os.getenv("CURAMYN_MONGO_DB", "app_db")

if not MONGO_URI:
    logger.critical("MONGO_URI not set in environment variables")
    raise RuntimeError("MONGO_URI is required to connect to MongoDB")


try:
    logger.info("Initializing MongoDB client")
    _client = MongoClient(MONGO_URI,tls=True,tlsCAFile=certifi.where(),)
    _database = _client[MONGO_DB]
    logger.info(
        "MongoDB connection established",
        extra={"database": MONGO_DB},
    )

except PyMongoError as exc:
    logger.critical("Failed to connect to MongoDB", extra={"error": str(exc)})
    raise RuntimeError("Database connection failed") from exc


def get_collection(collection_name: str) -> Collection[Any]:
    """
    Retrieve a MongoDB collection by name.

    Args:
        collection_name (str): Name of the MongoDB collection.

    Returns:
        Collection: MongoDB collection instance.

    Raises:
        RuntimeError: If collection access fails.
    """
    try:
        logger.debug(
            "Accessing MongoDB collection",
            extra={"collection": collection_name},
        )
        return _database[collection_name]

    except PyMongoError as exc:
        logger.error(
            "Failed to access MongoDB collection",
            extra={"collection": collection_name, "error": str(exc)},
        )
        raise RuntimeError(
            f"Unable to access collection: {collection_name}"
        ) from exc

