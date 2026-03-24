from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime

class QuizRequest(BaseModel):
    topic: str
    difficulty: str
    num_questions: int = 5
    thread_id: Optional[str] = None
    instructions: Optional[str] = None

class QuestionResponse(BaseModel):
    id: int
    question_text: str
    options: Dict[str, str]

class QuizResponse(BaseModel):
    id: int
    topic: str
    difficulty: str
    thread_id: Optional[str] = None
    created_at: datetime
    questions: Optional[List[QuestionResponse]] = []
    
    class Config:
        from_attributes = True

class QuizPaginatedResponse(BaseModel):
    items: List[QuizResponse]
    total: int
    page: int
    size: int

class UserAnswerSubmit(BaseModel):
    question_id: int
    user_answer: str

class QuizSubmitRequest(BaseModel):
    answers: List[UserAnswerSubmit]

class ResultResponse(BaseModel):
    id: int
    quiz_id: int
    score: float
    weak_areas: Dict[str, str]
    feedback: str
    
    class Config:
        from_attributes = True
