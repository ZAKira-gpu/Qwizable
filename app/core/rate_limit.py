from fastapi import Request, HTTPException
from app.core.cache import cache_client
import time
from typing import Tuple

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
        """Returns True if user has reached the 80% soft limit warning threshold."""
        cache_key = f"usage:user:{user_id}:today"
        count = await cache_client.redis.get(cache_key)
        count = int(count) if count else 0
        
        if count >= max_daily_quizzes:
            raise HTTPException(status_code=429, detail="Daily limit reached")
            
        return count >= (0.8 * max_daily_quizzes)
        
rate_limiter = RateLimiter(requests=100, window=60)
