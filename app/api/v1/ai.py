from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai import TutorRequest, TutorResponse
from app.api.v1.user import get_current_user
from app.services.ai_service import call_novita_api

router = APIRouter()

@router.post("/chat", response_model=TutorResponse)
async def ai_tutor_chat(
    request: TutorRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    prompt = f"User asked: {request.message} related to Quiz context ID {request.quiz_context_id}. Provide a helpful, educational response."
    response = await call_novita_api(prompt)
    if not response:
        return TutorResponse(reply="I'm sorry, I cannot process this right now. Please try again later.")
        
    return TutorResponse(reply=response)
