from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.core.config import settings
from app.core.middleware import RequestIDMiddleware
from app.services.ai_service import warmup_ai
import logging
from sqlalchemy import text
from app.db.session import engine
from app.core.cache import cache_client
from prometheus_fastapi_instrumentator import Instrumentator

import asyncio
from app.db.session import async_session
from sqlalchemy import select
from app.models.task import BackgroundTask
from app.services.quiz_service import generate_quiz_task
from app.services.subscription_service import check_expired_subscriptions

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestIDMiddleware)

# Prometheus Observability Metrics
Instrumentator().instrument(app).expose(app)

async def recover_tasks():
    """Background Worker for Task Recovery"""
    try:
        async with async_session() as db:
            query = select(BackgroundTask).where(BackgroundTask.status.in_(["pending", "processing"]))
            result = await db.execute(query)
            stuck_tasks = result.scalars().all()
            for task in stuck_tasks:
                if task.job_name.startswith("generate_quiz"):
                    meta = task.task_metadata or {}
                    logging.info(f"Recovering background task: {task.id}")
                    asyncio.create_task(
                        generate_quiz_task(
                            db, task.id, 
                            meta.get("user_id"), 
                            meta.get("topic"), 
                            meta.get("difficulty", "medium"), 
                            meta.get("num_questions", 5)
                        )
                    )
    except Exception as e:
        logging.error(f"Task recovery failed: {e}")

@app.on_event("startup")
async def startup_event():
    # Cold Start Optimization
    if settings.FEATURES.get("ai_tutor"):
        await warmup_ai()
        
    # Subscription Expirations Sweep
    async with async_session() as db:
        await check_expired_subscriptions(db)
        
    # Queue Persistence Recovery
    await recover_tasks()

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/ready")
async def readiness_check():
    db_status = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "failed"
        
    redis_status = "ok"
    if not cache_client.available:
        redis_status = "failed"
        
    return {
        "status": "ready" if db_status == "ok" else "degraded",
        "database": db_status,
        "redis": redis_status
    }
