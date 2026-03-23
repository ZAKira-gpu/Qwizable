import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logger import logger

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        logger.info(f"[{request_id}] Started {request.method} {request.url.path}")
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        logger.info(f"[{request_id}] Completed {response.status_code}")
        return response
