from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from app.models.usage import Usage
from app.models.user import User

async def get_or_create_daily_usage(db: AsyncSession, user_id: int) -> Usage:
    today = datetime.utcnow().date()
    
    result = await db.execute(
        select(Usage)
        .where(Usage.user_id == user_id)
        .where(func.date(Usage.created_at) == today)
    )
    usage = result.scalars().first()
    
    if not usage:
        usage = Usage(user_id=user_id, quizzes_generated=0, tokens_used=0)
        db.add(usage)
        await db.commit()
        await db.refresh(usage)
        
    return usage

async def increment_usage(db: AsyncSession, user_id: int):
    usage = await get_or_create_daily_usage(db, user_id)
    usage.quizzes_generated += 1
    await db.commit()
