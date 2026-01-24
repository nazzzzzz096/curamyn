"""
MongoDB connection utilities.

Provides a centralized MongoDB client and collection accessor
with connection validation and detailed error logging.
"""

import os
import time
from typing import Any
import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import (
    PyMongoError,
    ConnectionFailure,
    ServerSelectionTimeoutError,
    ConfigurationError,
    OperationFailure,
)

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)

load_dotenv()

MONGO_URI = os.getenv("CURAMYN_MONGO_URI")
MONGO_DB = os.getenv("CURAMYN_MONGO_DB", "app_db")

if not MONGO_URI:
    logger.critical("MONGO_URI not set in environment variables")
    raise RuntimeError("MONGO_URI is required to connect to MongoDB")

_client = None
_database = None


def _parse_mongo_uri(uri: str) -> dict:
    """
    Parse MongoDB URI to extract connection details for logging.

    Args:
        uri: MongoDB connection string

    Returns:
        Dictionary with parsed connection details
    """
    try:
        # Extract basic info without exposing credentials
        if "mongodb://" in uri or "mongodb+srv://" in uri:
            # Extract host info (without credentials)
            if "@" in uri:
                parts = uri.split("@")
                host_part = parts[1].split("/")[0] if len(parts) > 1 else "unknown"
            else:
                host_part = (
                    uri.replace("mongodb://", "")
                    .replace("mongodb+srv://", "")
                    .split("/")[0]
                )

            is_atlas = "mongodb.net" in uri
            is_srv = "mongodb+srv://" in uri

            return {
                "host": host_part,
                "is_atlas": is_atlas,
                "is_srv": is_srv,
                "protocol": "mongodb+srv" if is_srv else "mongodb",
            }
    except Exception:
        logger.warning("Failed to parse MongoDB URI details")

    return {
        "host": "unknown",
        "is_atlas": False,
        "is_srv": False,
        "protocol": "unknown",
    }


def _validate_connection(client: MongoClient) -> bool:
    """
    Validate MongoDB connection by attempting to ping the server.

    Args:
        client: MongoDB client instance

    Returns:
        True if connection is valid, False otherwise
    """
    try:
        # Attempt to ping the server (with timeout)
        client.admin.command("ping", serverSelectionTimeoutMS=5000)
        logger.info("✅ MongoDB connection validated successfully")
        return True

    except ServerSelectionTimeoutError as exc:
        logger.error(
            "❌ MongoDB server selection timeout - possible causes:",
            extra={
                "error": str(exc),
                "possible_causes": [
                    "Invalid IP address or hostname",
                    "Firewall blocking connection",
                    "Network connectivity issues",
                    "MongoDB server is down",
                    "IP not whitelisted in MongoDB Atlas",
                ],
            },
        )
        return False

    except ConnectionFailure as exc:
        logger.error(
            "❌ MongoDB connection failure - unable to connect to server",
            extra={
                "error": str(exc),
                "possible_causes": [
                    "Incorrect connection string",
                    "Authentication failed",
                    "SSL/TLS certificate issues",
                    "DNS resolution failure",
                ],
            },
        )
        return False

    except OperationFailure as exc:
        logger.error(
            "❌ MongoDB operation failure - authentication or permission issue",
            extra={
                "error": str(exc),
                "possible_causes": [
                    "Invalid credentials",
                    "Insufficient permissions",
                    "Database access denied",
                ],
            },
        )
        return False

    except ConfigurationError as exc:
        logger.error(
            "❌ MongoDB configuration error - invalid connection settings",
            extra={
                "error": str(exc),
                "possible_causes": [
                    "Malformed connection string",
                    "Invalid connection options",
                    "Missing required parameters",
                ],
            },
        )
        return False

    except Exception as exc:
        logger.error(
            "❌ Unexpected MongoDB connection error", extra={"error": str(exc)}
        )
        return False


def _initialize_connection() -> tuple[MongoClient, Any]:
    """
    Initialize MongoDB connection with comprehensive validation and logging.

    Returns:
        Tuple of (client, database)

    Raises:
        RuntimeError: If connection cannot be established
    """
    # Parse URI for logging (without exposing credentials)
    uri_info = _parse_mongo_uri(MONGO_URI)

    logger.info(
        "🔄 Initializing MongoDB connection",
        extra={
            "database": MONGO_DB,
            "protocol": uri_info["protocol"],
            "host": uri_info["host"],
            "is_atlas": uri_info["is_atlas"],
        },
    )

    start_time = time.time()

    try:
        # Create MongoDB client with connection settings
        client = MongoClient(
            MONGO_URI,
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000,  # 10 second timeout
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
        )

        # Validate the connection
        if not _validate_connection(client):
            raise RuntimeError(
                "MongoDB connection validation failed. Please check:\n"
                "1. Your IP address is whitelisted in MongoDB Atlas\n"
                "2. Connection string is correct\n"
                "3. Network connectivity to MongoDB server\n"
                "4. Firewall settings allow MongoDB connections"
            )

        # Access database
        database = client[MONGO_DB]

        # Log successful connection
        elapsed_time = time.time() - start_time
        logger.info(
            "✅ MongoDB connection established successfully",
            extra={
                "database": MONGO_DB,
                "host": uri_info["host"],
                "connection_time_ms": round(elapsed_time * 1000, 2),
                "is_atlas": uri_info["is_atlas"],
            },
        )

        # Log additional connection info
        try:
            server_info = client.server_info()
            logger.info(
                "📊 MongoDB server information",
                extra={
                    "version": server_info.get("version"),
                    "max_bson_size": server_info.get("maxBsonObjectSize"),
                },
            )
        except Exception:
            logger.debug("Could not retrieve server information")

        return client, database

    except ServerSelectionTimeoutError as exc:
        logger.critical(
            "❌ CRITICAL: MongoDB server selection timeout",
            extra={
                "error": str(exc),
                "database": MONGO_DB,
                "host": uri_info["host"],
                "suggestions": [
                    "Check if your current IP address is whitelisted in MongoDB Atlas",
                    "Verify the connection string is correct",
                    "Ensure MongoDB server is running",
                    "Check network connectivity",
                    "Verify firewall settings",
                ],
            },
        )
        raise RuntimeError(
            f"Failed to connect to MongoDB: Server selection timeout. "
            f"Your IP may not be whitelisted or the server is unreachable."
        ) from exc

    except ConnectionFailure as exc:
        logger.critical(
            "❌ CRITICAL: MongoDB connection failure",
            extra={
                "error": str(exc),
                "database": MONGO_DB,
                "host": uri_info["host"],
                "suggestions": [
                    "Verify the MongoDB URI is correct",
                    "Check authentication credentials",
                    "Ensure SSL/TLS certificates are valid",
                    "Check DNS resolution for the hostname",
                ],
            },
        )
        raise RuntimeError(
            f"Failed to connect to MongoDB: Connection failure. "
            f"Please verify your connection string and credentials."
        ) from exc

    except OperationFailure as exc:
        logger.critical(
            "❌ CRITICAL: MongoDB authentication failed",
            extra={
                "error": str(exc),
                "database": MONGO_DB,
                "suggestions": [
                    "Verify database username and password",
                    "Check user permissions for the database",
                    "Ensure user has required roles",
                ],
            },
        )
        raise RuntimeError(f"Failed to authenticate with MongoDB: {str(exc)}") from exc

    except ConfigurationError as exc:
        logger.critical(
            "❌ CRITICAL: MongoDB configuration error",
            extra={
                "error": str(exc),
                "suggestions": [
                    "Check the MongoDB URI format",
                    "Verify connection options are valid",
                    "Ensure all required parameters are present",
                ],
            },
        )
        raise RuntimeError(f"MongoDB configuration error: {str(exc)}") from exc

    except PyMongoError as exc:
        logger.critical(
            "❌ CRITICAL: MongoDB error",
            extra={
                "error": str(exc),
                "database": MONGO_DB,
            },
        )
        raise RuntimeError(f"Database connection failed: {str(exc)}") from exc

    except Exception as exc:
        logger.critical(
            "❌ CRITICAL: Unexpected error during MongoDB connection",
            extra={
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )
        raise RuntimeError(
            f"Unexpected error connecting to MongoDB: {str(exc)}"
        ) from exc


# Initialize connection on module import
try:
    _client, _database = _initialize_connection()
except Exception as exc:
    logger.critical(
        "💥 FATAL: Failed to initialize MongoDB connection on startup",
        extra={"error": str(exc)},
    )
    # Re-raise to prevent application from starting with broken DB
    raise


def get_collection(collection_name: str) -> Collection[Any]:
    """
    Retrieve a MongoDB collection by name.

    Args:
        collection_name (str): Name of the MongoDB collection.

    Returns:
        Collection: MongoDB collection instance.

    Raises:
        RuntimeError: If collection access fails or connection is not initialized.
    """
    if _database is None:
        logger.error(
            "❌ Database connection not initialized",
            extra={"collection": collection_name},
        )
        raise RuntimeError(
            "Database connection not initialized. "
            "MongoDB may have failed to connect on startup."
        )

    try:
        logger.debug(
            "Accessing MongoDB collection",
            extra={"collection": collection_name, "database": MONGO_DB},
        )
        return _database[collection_name]

    except PyMongoError as exc:
        logger.error(
            "❌ Failed to access MongoDB collection",
            extra={
                "collection": collection_name,
                "database": MONGO_DB,
                "error": str(exc),
            },
        )
        raise RuntimeError(f"Unable to access collection: {collection_name}") from exc


def check_connection_health() -> dict:
    """
    Check the health of the MongoDB connection.

    Returns:
        Dictionary with connection health status
    """
    if _client is None:
        return {"status": "disconnected", "message": "MongoDB client not initialized"}

    try:
        # Ping the database
        _client.admin.command("ping")

        # Get server status
        server_status = _client.admin.command("serverStatus")

        return {
            "status": "connected",
            "database": MONGO_DB,
            "uptime_seconds": server_status.get("uptime"),
            "connections": server_status.get("connections", {}).get("current"),
            "version": server_status.get("version"),
        }

    except Exception as exc:
        logger.warning("⚠️ MongoDB health check failed", extra={"error": str(exc)})
        return {"status": "unhealthy", "error": str(exc)}


# Export health check for monitoring endpoints
__all__ = ["get_collection", "check_connection_health"]
