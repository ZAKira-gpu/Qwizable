from fastapi import APIRouter
from app.api.v1 import auth, user, quiz, ai, payment

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user.router, prefix="/users", tags=["users"])
api_router.include_router(quiz.router, prefix="/quizzes", tags=["quizzes"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(payment.router, prefix="/payments", tags=["payments"])
