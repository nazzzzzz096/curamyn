"""
Onboarding question API routes.

Manages progressive question flow during user onboarding.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.chat_service.utils.logger import get_logger
from app.core.dependencies import get_current_user
from app.question_service.schemas import AnswerRequest, QuestionResponse
from app.question_service.service import get_next_question, save_answer

logger = get_logger(__name__)

router = APIRouter(
    prefix="/questions",
    tags=["Onboarding Questions"],
)


@router.get(
    "/next",
    response_model=QuestionResponse,
)
def next_question(
    current_user: dict = Depends(get_current_user),
) -> QuestionResponse:
    """
    Fetch the next unanswered onboarding question.

    Args:
        current_user (dict): Authenticated user context.

    Returns:
        QuestionResponse: Next question or completion status.
    """
    user_id = current_user["sub"]

    try:
        logger.info(
            "Fetching next onboarding question",
            extra={"user_id": user_id},
        )
        return get_next_question(user_id)

    except Exception as exc:
        logger.exception(
            "Failed to fetch next onboarding question",
            extra={"user_id": user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch next question",
        ) from exc


@router.post(
    "/answer",
    response_model=QuestionResponse,
)
def answer_question(
    payload: AnswerRequest,
    current_user: dict = Depends(get_current_user),
) -> QuestionResponse:
    """
    Save user's answer (or skip) and return next question.

    Args:
        payload (AnswerRequest): User answer payload.
        current_user (dict): Authenticated user context.

    Returns:
        QuestionResponse: Next question or completion status.
    """
    user_id = current_user["sub"]

    try:
        logger.info(
            "Saving onboarding answer",
            extra={
                "user_id": user_id,
                "question_key": payload.question_key,
            },
        )

        return save_answer(
            user_id,
            payload.question_key,
            payload.answer,
        )

    except ValueError as exc:
        logger.warning(
            "Invalid onboarding answer",
            extra={
                "user_id": user_id,
                "question_key": payload.question_key,
                "reason": str(exc),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "Failed to save onboarding answer",
            extra={"user_id": user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save answer",
        ) from exc
