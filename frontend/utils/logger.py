import logging
import os

LOG_LEVEL = os.getenv("CURAMYN_FRONTEND_LOG_LEVEL", "INFO").upper()


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    if logger.handlers:
        return logger

    handler = logging.StreamHandler()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | FRONTEND | %(name)s | %(message)s"
    )

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False

    return logger
