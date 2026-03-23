from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UsageResponse
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
    return current_user

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
