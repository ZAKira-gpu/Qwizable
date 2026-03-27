from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.user import User
from app.models.chat import ChatMessage
from app.schemas.ai import TutorRequest, TutorResponse
from app.api.v1.user import get_current_user
from app.services.ai_service import call_novita_api
from typing import List
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class ChatHistoryItem(BaseModel):
    id: int
    role: str
    message: str
    quiz_context_id: int | None
    created_at: datetime
    
    class Config:
        from_attributes = True

@router.post("/chat", response_model=TutorResponse)
async def ai_tutor_chat(
    request: TutorRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Persist the user's message
    user_msg = ChatMessage(
        user_id=current_user.id,
        quiz_context_id=request.quiz_context_id if request.quiz_context_id else None,
        role="user",
        message=request.message
    )
    db.add(user_msg)
    await db.flush()  # flush so AI call doesn't block the transaction

    prompt = f"User asked: {request.message} related to Quiz context ID {request.quiz_context_id}. Provide a helpful, educational response."
    response = await call_novita_api(prompt)
    
    if not response:
        response = "I'm sorry, I cannot process this right now. Please try again later."

    # Persist the AI's reply
    ai_msg = ChatMessage(
        user_id=current_user.id,
        quiz_context_id=request.quiz_context_id if request.quiz_context_id else None,
        role="assistant",
        message=response
    )
    db.add(ai_msg)
    await db.commit()

    return TutorResponse(reply=response)


@router.get("/chat/history", response_model=List[ChatHistoryItem])
async def get_chat_history(
    quiz_context_id: int | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve cloud-synced AI tutor chat history for the current user."""
    query = select(ChatMessage).where(ChatMessage.user_id == current_user.id)
    if quiz_context_id is not None:
        query = query.where(ChatMessage.quiz_context_id == quiz_context_id)
    query = query.order_by(ChatMessage.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
