from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from app.db.session import get_db
from app.models.user import User
from app.models.quiz import Quiz, Question
from app.models.task import BackgroundTask
from app.schemas.quiz import QuizRequest, QuizPaginatedResponse, QuizResponse, QuestionResponse, QuizSubmitRequest, ResultResponse
from app.api.v1.user import get_current_user
from app.services.quiz_service import generate_quiz_task
from app.services.evaluation_service import evaluate_answers
from app.services.user_service import increment_usage

router = APIRouter()

@router.post("/generate", status_code=202)
async def generate_quiz(
    request: QuizRequest, 
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    await increment_usage(db, current_user.id)
    
    task = BackgroundTask(job_name=f"generate_quiz_{current_user.id}_{request.topic}")
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    background_tasks.add_task(
        generate_quiz_task, db, task.id, current_user.id, request.topic, request.difficulty, request.num_questions
    )
    return {
        "success": True, 
        "data": {"message": "Quiz generation started.", "task_id": task.id}, 
        "error": None
    }

@router.get("/", response_model=QuizPaginatedResponse)
async def get_quizzes(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * size
    
    total_query = select(func.count(Quiz.id)).where(Quiz.user_id == current_user.id).where(Quiz.deleted_at.is_(None))
    total = await db.scalar(total_query)
    
    query = select(Quiz).where(Quiz.user_id == current_user.id).where(Quiz.deleted_at.is_(None)).order_by(Quiz.created_at.desc()).offset(offset).limit(size)
    result = await db.execute(query)
    quizzes = result.scalars().all()
    
    return QuizPaginatedResponse(items=quizzes, total=total, page=page, size=size)

@router.post("/{quiz_id}/submit")
async def submit_quiz(
    quiz_id: int,
    submission: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    quiz = await db.get(Quiz, quiz_id)
    if not quiz or quiz.user_id != current_user.id or quiz.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quiz not found")
        
    result = await evaluate_answers(db, quiz_id, submission.answers)
    return {"success": True, "data": result, "error": None}
