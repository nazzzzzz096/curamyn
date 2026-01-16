import os
import mlflow
from typing import Any, Callable, Optional
from contextlib import contextmanager

from app.chat_service.utils.logger import get_logger

logger = get_logger(__name__)


logger = get_logger(__name__)


@contextmanager
def mlflow_context(run_name: str | None = None):
    """
    Proper MLflow run lifecycle handler.

    This context manager ensures that:
    - An MLflow run is started if none is active
    - Existing active runs are reused (no improper nesting)
    - Runs started here are always ended cleanly
    - MLflow failures do not crash application flow
    - Useful lifecycle events are logged for debugging

    Args:
        run_name (str | None):
            Optional MLflow run name for easier identification in the UI.
    """

    # Disable MLflow entirely in test environment
    if os.getenv("CURAMYN_ENV") == "test":
        logger.debug("MLflow disabled (test environment)")
        yield
        return

    started_here = False
    run = None

    try:
        active_run = mlflow.active_run()

        if active_run is None:
            run = mlflow.start_run(run_name=run_name)
            started_here = True
            logger.info(
                "MLflow run started",
                extra={
                    "run_id": run.info.run_id,
                    "experiment_id": run.info.experiment_id,
                    "run_name": run_name,
                },
            )
        else:
            run = active_run
            logger.debug(
                "Reusing existing MLflow run",
                extra={
                    "run_id": run.info.run_id,
                    "experiment_id": run.info.experiment_id,
                },
            )

        yield run

    except Exception:
        logger.exception("Exception inside MLflow context")
        raise

    finally:
        if started_here:
            try:
                if mlflow.active_run():
                    mlflow.end_run()
                    logger.info(
                        "MLflow run ended",
                        extra={"run_id": run.info.run_id if run else None},
                    )
            except Exception:
                logger.exception("Failed to end MLflow run")


def mlflow_safe(
    func: Callable[..., Any],
    *args: Any,
    swallow: bool = True,
    **kwargs: Any,
) -> Optional[Any]:
    """
    Safely execute an MLflow function call.

    This helper ensures that MLflow logging failures NEVER break
    application execution, while still providing visibility into
    what went wrong.

    Behavior:
    - No-op when running in test environment (CURAMYN_ENV == "test")
    - Executes the given MLflow function with provided arguments
    - Catches and logs all MLflow-related exceptions
    - Optionally re-raises exceptions (for debugging or strict mode)

    Args:
        func (Callable[..., Any]):
            The MLflow function to execute
            (e.g., mlflow.log_metric, mlflow.set_tag).

        *args (Any):
            Positional arguments for the MLflow function.

        swallow (bool, optional):
            If True (default), exceptions are logged and suppressed.
            If False, exceptions are re-raised after logging.
            Useful for debugging MLflow issues.

        **kwargs (Any):
            Keyword arguments for the MLflow function.

    Returns:
        Optional[Any]:
            The return value of the MLflow function, if any.
            Returns None when execution is skipped or an error occurs.

    Design rationale:
    - MLflow is an observability dependency, not a core dependency.
    - Application correctness must not depend on MLflow availability.
    - Failures are logged for audit/debug without impacting users.
    """

    # Disable MLflow calls entirely during tests
    if os.getenv("CURAMYN_ENV") == "test":
        return None

    try:
        return func(*args, **kwargs)

    except Exception as exc:
        logger.warning(
            "MLflow call failed: %s | args=%s kwargs=%s",
            func.__name__,
            args,
            kwargs,
            exc_info=True,
        )

        if not swallow:
            raise

        return None
