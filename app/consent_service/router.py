"""
Consent management API routes.

Handles user consent preferences for data usage.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.chat_service.utils.logger import get_logger
from app.consent_service.schemas import ConsentCreate, ConsentResponse
from app.consent_service.service import (
    create_or_update_consent,
    get_user_consent,
)
from app.core.dependencies import get_current_user

logger = get_logger(__name__)

router = APIRouter(
    prefix="/consent",
    tags=["Consent"],
)


@router.get(
    "/status",
    response_model=ConsentResponse,
)
def read_consent(
    current_user: dict = Depends(get_current_user),
) -> ConsentResponse:
    """
    Retrieve the current user's consent settings.

    Args:
        current_user (dict): Authenticated user context.

    Returns:
        ConsentResponse: User consent preferences.
    """
    user_id = current_user["sub"]

    try:
        logger.info(
            "Fetching consent status",
            extra={"user_id": user_id},
        )
        return get_user_consent(user_id)

    except Exception as exc:
        logger.exception(
            "Failed to retrieve consent status",
            extra={"user_id": user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve consent status",
        ) from exc


@router.post(
    "/update",
    response_model=ConsentResponse,
    status_code=status.HTTP_200_OK,
)
def update_consent(
    payload: ConsentCreate,
    current_user: dict = Depends(get_current_user),
) -> ConsentResponse:
    """
    Create or update user consent preferences.

    Args:
        payload (ConsentCreate): Consent flags.
        current_user (dict): Authenticated user context.

    Returns:
        ConsentResponse: Updated consent state.
    """
    user_id = current_user["sub"]

    try:
        logger.info(
            "Updating consent preferences",
            extra={
                "user_id": user_id,
                "consent": payload.model_dump(),
            },
        )

        return create_or_update_consent(
            user_id,
            payload.model_dump(),
        )

    except Exception as exc:
        logger.exception(
            "Failed to update consent preferences",
            extra={"user_id": user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update consent preferences",
        ) from exc
