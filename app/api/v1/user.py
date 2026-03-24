from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.db.session import get_db
from app.models.user import User
from app.models.usage import Usage
from app.schemas.user import UserCreate, UserResponse, UsageResponse
from app.core.dependencies import get_current_user_token_payload
from app.services.user_service import get_or_create_daily_usage
from app.core.rate_limit import rate_limiter

router = APIRouter()

async def get_current_user(token_sub: str = Depends(get_current_user_token_payload), db: AsyncSession = Depends(get_db)) -> User:
    user = await db.get(User, int(token_sub))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return {"success": True, "data": current_user, "error": None}

@router.get("/me/usage")
async def get_user_usage(
    current_user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    query = select(Usage).where(Usage.user_id == current_user.id).order_by(Usage.created_at.desc())
    usage = await db.scalar(query)
    
    tokens = usage.tokens_used if usage else 0
    quizzes = usage.quizzes_generated if usage else 0
    
    est_cost = (tokens / 1000) * 0.0015 # Assuming $0.0015 per 1K Llama 3 8B
    
    return {
        "success": True, 
        "data": {
            "tokens_used_today": tokens,
            "quizzes_today": quizzes,
            "estimated_cost_usd": round(est_cost, 4),
            "plan": current_user.plan
        }, 
        "error": None
    }

@router.get("/usage", response_model=UsageResponse)
async def get_my_usage(request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    usage = await get_or_create_daily_usage(db, current_user.id)
    
    max_quizzes = {"free": 5, "pro": 100}.get(current_user.plan, 5)
    soft_limit = await rate_limiter.check_user_limit_soft(str(current_user.id), max_quizzes)
    
    return UsageResponse(
        quizzes_generated=usage.quizzes_generated,
        tokens_used=usage.tokens_used,
        soft_limit_warning=soft_limit
    )
