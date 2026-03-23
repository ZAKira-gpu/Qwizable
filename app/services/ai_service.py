import httpx
import asyncio
import time
from app.core.config import settings
from app.core.logger import logger
from typing import Optional

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0
        
    def is_open(self) -> bool:
        if self.failures >= self.failure_threshold:
            time_since_failure = time.time() - self.last_failure_time
            if time_since_failure > self.recovery_timeout:
                return False
            return True
        return False
        
    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        
    def record_success(self):
        self.failures = 0

cb = CircuitBreaker()

async def call_novita_api(prompt: str) -> Optional[str]:
    if cb.is_open():
        logger.warning("Circuit breaker is OPEN. Fast-failing AI call.")
        return None
        
    max_retries = 3
    base_url = "https://api.novita.ai/v3/openai/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.NOVITA_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta-llama/llama-3-8b-instruct",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        for attempt in range(max_retries):
            try:
                response = await client.post(base_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                
                cb.record_success()
                return data["choices"][0]["message"]["content"]
                
            except httpx.HTTPError as e:
                logger.error(f"Novita AI call failed (Attempt {attempt+1}/{max_retries}): {e}")
                cb.record_failure()
                await asyncio.sleep(2 ** attempt)
        return None

async def warmup_ai():
    """Cold Start Optimization executed on application startup."""
    logger.info("Warming up AI service...")
    await call_novita_api("ping")
