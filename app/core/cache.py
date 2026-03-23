import redis.asyncio as redis
from app.core.config import settings
from app.core.logger import logger
import json
from typing import Any, Optional

class CacheClient:
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.available = True

    async def _safe_execute(self, func, *args, **kwargs):
        if not self.available:
            try:
                await self.redis.ping()
                self.available = True
                logger.info("Redis connection recovered.")
            except Exception:
                return None
                
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Redis operation failed: {e}. Falling back to DB/bypass mode.")
            self.available = False
            return None

    async def get(self, key: str) -> Optional[Any]:
        val = await self._safe_execute(self.redis.get, key)
        return json.loads(val) if val else None

    async def set(self, key: str, value: Any, expire: int = 3600):
        await self._safe_execute(self.redis.set, key, json.dumps(value), ex=expire)

    async def incr(self, key: str) -> int:
        val = await self._safe_execute(self.redis.incr, key)
        return val if val is not None else 1

    async def expire(self, key: str, seconds: int):
        await self._safe_execute(self.redis.expire, key, seconds)

cache_client = CacheClient()
