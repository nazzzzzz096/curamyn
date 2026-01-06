"""
Centralized logging utility.

Provides a consistent, structured logger across the application.
"""

import logging
import os
from typing import Optional

# Read log level from environment (default: INFO)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Create or retrieve a configured logger instance.

    Args:
        name (Optional[str]): Logger name (usually __name__).

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    # Prevent duplicate handlers (important with FastAPI/Uvicorn reloads)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Prevent log propagation to root logger (avoids duplicates)
    logger.propagate = False

    return logger

