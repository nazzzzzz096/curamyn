from typing import Optional

from pydantic import BaseModel


class QuestionResponse(BaseModel):
    question_key: Optional[str]
    question_text: Optional[str]
    completed: bool


class AnswerRequest(BaseModel):
    question_key: str
    answer: str

