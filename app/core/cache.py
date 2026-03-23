import redis.asyncio as redis
from app.core.config import settings
import json
from typing import Any, Optional

class CacheClient:
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def get(self, key: str) -> Optional[Any]:
        val = await self.redis.get(key)
        if val:
            return json.loads(val)
        return None

    async def set(self, key: str, value: Any, expire: int = 3600):
        await self.redis.set(key, json.dumps(value), ex=expire)

cache_client = CacheClient()
