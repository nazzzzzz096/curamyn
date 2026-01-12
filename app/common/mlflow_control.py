import os
from contextlib import nullcontext
import mlflow


def mlflow_context():
    """
    Enable MLflow only outside test environment.
    """
    if os.getenv("CURAMYN_ENV") == "test":
        return nullcontext()
    return mlflow.start_run(nested=True)


def mlflow_safe(func, *args, **kwargs):
    """
    Call MLflow functions safely (no-op in tests).
    """
    if os.getenv("CURAMYN_ENV") != "test":
        func(*args, **kwargs)
