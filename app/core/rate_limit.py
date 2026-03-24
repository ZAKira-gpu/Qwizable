from fastapi import Request, HTTPException
from app.core.cache import cache_client
import time
from typing import Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import datetime, timedelta
from app.models.usage import Usage

class RateLimiter:
    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window

    async def _check_limit(self, key: str, max_requests: int) -> Tuple[bool, int]:
        current = int(time.time())
        window_start = current - self.window
        
        cache_key = f"rate_limit:{key}:{current // self.window}"
        
        count = await cache_client.redis.incr(cache_key)
        if count == 1:
            await cache_client.redis.expire(cache_key, self.window)
            
        return count <= max_requests, count

    async def check_ip_limit(self, request: Request):
        ip = request.client.host
        allowed, count = await self._check_limit(f"ip:{ip}", self.requests)
        if not allowed:
            raise HTTPException(status_code=429, detail="Too Many Requests")

    async def check_user_limit_soft(self, user_id: str, max_daily_quizzes: int) -> bool:
        cache_key = f"usage:user:{user_id}:today"
        count = await cache_client.redis.get(cache_key)
        count = int(count) if count else 0
        
        if count >= max_daily_quizzes:
            raise HTTPException(status_code=429, detail="Daily limit reached")
            
        return count >= (0.8 * max_daily_quizzes)
        
    async def check_ai_cost_hard_limit(self, user_id: str, max_tokens_per_day: int) -> bool:
        cache_key = f"usage:user:{user_id}:tokens_today"
        count = await cache_client.redis.get(cache_key)
        count = int(count) if count else 0
        
        if count >= max_tokens_per_day:
            raise HTTPException(status_code=402, detail="GPU Token Limit Exhausted. Please upgrade plan.")
        return False
        
    async def check_upload_limits(self, db: AsyncSession, user_id: int, plan: str, file_size_bytes: int) -> dict:
        """Enforces Free Tier: 3 documents / 7 days and 5MB cap."""
        if plan != "free":
            return {"remaining": "unlimited", "allowed": True}
            
        file_size_mb = file_size_bytes / (1024 * 1024)
        if file_size_mb > 5.0:
            raise HTTPException(status_code=413, detail="Free tier limit: 5MB maximum file size.")
            
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        query = select(func.sum(Usage.docs_uploaded)).where(
            and_(Usage.user_id == user_id, Usage.created_at >= seven_days_ago)
        )
        
        docs_last_7_days = await db.scalar(query)
        docs_last_7_days = int(docs_last_7_days) if docs_last_7_days else 0
        
        if docs_last_7_days >= 3:
            raise HTTPException(status_code=403, detail="Free tier limit: 3 documents per 7 days. Please upgrade.")
            
        return {"remaining": max(0, 3 - docs_last_7_days - 1), "allowed": True}
        
rate_limiter = RateLimiter(requests=100, window=60)
