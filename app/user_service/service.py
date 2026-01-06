"""
User service business logic.

Handles user creation and authentication.
"""

import uuid
from datetime import datetime
from typing import Dict

from passlib.context import CryptContext

from app.chat_service.utils.logger import get_logger
from app.db.mongodb import get_collection

logger = get_logger(__name__)

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """
    Hash a plain-text password.

    Args:
        password (str): Raw user password.

    Returns:
        str: Secure hashed password.
    """
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        password (str): Plain-text password.
        hashed_password (str): Stored hash.

    Returns:
        bool: True if password matches.
    """
    return pwd_context.verify(password, hashed_password)


def create_user(email: str, password: str) -> Dict:
    """
    Create a new user account.

    Args:
        email (str): User email.
        password (str): Plain-text password.

    Returns:
        Dict: Created user data.

    Raises:
        ValueError: If user already exists.
    """
    users = get_collection("users")

    logger.info("Creating user", extra={"email": email})

    if users.find_one({"email": email}):
        logger.warning("User already exists", extra={"email": email})
        raise ValueError("User already exists")

    user_data = {
        "user_id": str(uuid.uuid4()),
        "email": email,
        "hashed_password": hash_password(password),
        "created_at": datetime.utcnow(),
    }

    users.insert_one(user_data)

    logger.info("User created", extra={"email": email})

    user_data.pop("hashed_password")
    return user_data


def authenticate_user(email: str, password: str) -> Dict:
    """
    Authenticate a user by credentials.

    Args:
        email (str): User email.
        password (str): Plain-text password.

    Returns:
        Dict: Authenticated user data.

    Raises:
        ValueError: If authentication fails.
    """
    users = get_collection("users")

    logger.info("Authenticating user", extra={"email": email})

    user = users.find_one({"email": email})
    if not user:
        logger.warning("User not found", extra={"email": email})
        raise ValueError("Invalid email or password")

    if not verify_password(password, user["hashed_password"]):
        logger.warning("Invalid password", extra={"email": email})
        raise ValueError("Invalid email or password")

    logger.info("Authentication successful", extra={"email": email})

    user.pop("hashed_password")
    return user
